import type { Request } from "express";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { extractSharpContext } from "../sharp/context.js";
import { runLens } from "../lenses/shared.js";
import { ALL_LENSES, LENS_DESCRIPTIONS } from "../lenses/all.js";
import type { LensSpec } from "../lenses/shared.js";
import { buildConflictMatrix } from "../concordance/conflict-matrix.js";
import { buildConcordanceBrief } from "../concordance/concordance-brief.js";
import { recordToolCall, recordAuditEvent } from "../observability/audit.js";
import { logger } from "../observability/logger.js";
import { Sentry } from "../observability/sentry.js";
import type { ConflictMatrix, ConcordantPlan, Specialty, SpecialtyView } from "../lenses/types.js";

// ─── Schemas (zod runtime, used by MCP for input description) ──────────

const lensInputShape = {
  patient_id: z.string().min(1).describe("FHIR Patient.id to analyze"),
  focus_problem: z.string().optional().describe("Optional clinical question to focus the analysis on"),
};

// SpecialtyView shape — for consumers passing views into concordance tools.
const specialtyViewShape = z.object({
  specialty: z.string(),
  patient_id: z.string(),
  patient_summary_excerpt: z.string(),
  relevant_conditions: z.array(z.string()),
  relevant_medications: z.array(z.string()),
  relevant_observations: z.array(z.string()),
  applicable_guidelines: z.array(z.string()),
  primary_concerns: z.array(z.string()),
  red_flags: z.array(z.string()),
  proposed_plan: z.object({
    continue: z.array(z.string()),
    start: z.array(z.string()),
    stop: z.array(z.string()),
    monitor: z.array(z.string()),
  }),
  confidence_notes: z.string(),
  reasoning_trace: z.array(z.string()),
  fhir_refs: z.array(z.string()),
});

const conflictMatrixShape = z.object({
  patient_id: z.string(),
  specialties: z.array(z.string()),
  conflicts: z.array(z.any()),
  agreements: z.array(z.any()),
  abstentions: z.array(z.any()),
});

interface LensToolWiring {
  toolName: string;
  description: string;
  spec: LensSpec;
}

const PERSPECTIVE_TOOLS: LensToolWiring[] = ALL_LENSES.map((spec) => ({
  toolName: `get_${spec.specialty}_perspective`,
  description: LENS_DESCRIPTIONS[spec.specialty],
  spec,
}));

/** Register all MCP tools on the given server. `req` carries the SHARP context. */
export function registerTools(server: McpServer, req: Request): void {
  for (const wiring of PERSPECTIVE_TOOLS) {
    registerLensTool(server, req, wiring);
  }
  registerConflictMatrixTool(server, req);
  registerConcordanceBriefTool(server, req);
}

// ─── Per-specialty perspective tools ───────────────────────────────────

function registerLensTool(server: McpServer, req: Request, wiring: LensToolWiring): void {
  // The @modelcontextprotocol/sdk's registerTool generic stack depth blows past TS's
  // type-instantiation limit when combined with zod 3.25.x and `noUncheckedIndexedAccess`.
  // Runtime semantics are unaffected; this is a known SDK + zod typegen interaction.
  // @ts-expect-error TS2589: type instantiation is excessively deep
  server.registerTool(
    wiring.toolName,
    {
      title: wiring.toolName,
      description: wiring.description,
      inputSchema: lensInputShape,
    },
    async (input: { patient_id: string; focus_problem?: string }) => {
      const ctx = extractSharpContext(req);
      if (!ctx) {
        return failure("fhir_context_required");
      }

      const start = Date.now();
      const conveningId = ctx.conveningId ?? null;
      const specialty: Specialty = wiring.spec.specialty;

      await recordAuditEvent({
        conveningId,
        actor: `lens-mcp/${specialty}`,
        action: "tool_called",
        payload: { tool: wiring.toolName, patient_id: input.patient_id, focus: input.focus_problem ?? null },
      });

      try {
        const { view, latencyMs } = await runLens(wiring.spec, {
          ctx,
          patientId: input.patient_id,
          focusProblem: input.focus_problem,
        });

        await Promise.all([
          recordToolCall({
            conveningId,
            toolName: wiring.toolName,
            params: input,
            result: { specialty, n_concerns: view.primary_concerns.length, n_red_flags: view.red_flags.length },
            status: "success",
            latencyMs,
          }),
          recordAuditEvent({
            conveningId,
            actor: `lens-mcp/${specialty}`,
            action: "tool_returned",
            payload: { tool: wiring.toolName, primary_concerns: view.primary_concerns, red_flags: view.red_flags },
            fhirRefs: view.fhir_refs,
          }),
        ]);

        return {
          content: [{ type: "text", text: JSON.stringify(view, null, 2) }],
          structuredContent: view as unknown as Record<string, unknown>,
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        logger.error({ err, tool: wiring.toolName }, "lens tool failed");
        Sentry.captureException(err);

        await recordToolCall({
          conveningId,
          toolName: wiring.toolName,
          params: input,
          status: "error",
          errorMessage: message,
          latencyMs: Date.now() - start,
        });

        return failure(message);
      }
    }
  );
}

// ─── Concordance: conflict matrix ──────────────────────────────────────

function registerConflictMatrixTool(server: McpServer, req: Request): void {
  const inputShape = {
    views: z.array(specialtyViewShape).min(2).describe("SpecialtyViews from at least two specialties"),
  };
  server.registerTool(
    "get_council_conflict_matrix",
    {
      title: "get_council_conflict_matrix",
      description:
        "Synthesizes a ConflictMatrix from multiple SpecialtyViews — surfaces conflicts, agreements, and abstentions across specialties for a single patient. Used by the Convener at the end of Round 1.",
      inputSchema: inputShape,
    },
    async (rawInput) => {
      // Zod validates structural shape; we narrow the loose `string` specialty back to the Specialty union.
      const input = rawInput as { views: SpecialtyView[] };
      const ctx = extractSharpContext(req);
      if (!ctx) return failure("fhir_context_required");
      const start = Date.now();
      const conveningId = ctx.conveningId ?? null;

      await recordAuditEvent({
        conveningId,
        actor: "lens-mcp/concordance",
        action: "tool_called",
        payload: { tool: "get_council_conflict_matrix", n_views: input.views.length },
      });

      try {
        const { matrix, latencyMs } = await buildConflictMatrix(input.views);
        await Promise.all([
          recordToolCall({
            conveningId,
            toolName: "get_council_conflict_matrix",
            params: { n_views: input.views.length },
            result: { n_conflicts: matrix.conflicts.length, n_agreements: matrix.agreements.length },
            status: "success",
            latencyMs,
          }),
          recordAuditEvent({
            conveningId,
            actor: "lens-mcp/concordance",
            action: "conflict_flagged",
            payload: { conflicts: matrix.conflicts.map((c) => ({ topic: c.topic, severity: c.severity })) },
          }),
        ]);
        return {
          content: [{ type: "text", text: JSON.stringify(matrix, null, 2) }],
          structuredContent: matrix as unknown as Record<string, unknown>,
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        logger.error({ err }, "conflict matrix tool failed");
        Sentry.captureException(err);
        await recordToolCall({
          conveningId,
          toolName: "get_council_conflict_matrix",
          params: { n_views: input.views.length },
          status: "error",
          errorMessage: message,
          latencyMs: Date.now() - start,
        });
        return failure(message);
      }
    }
  );
}

// ─── Concordance: concordance brief ────────────────────────────────────

function registerConcordanceBriefTool(server: McpServer, req: Request): void {
  const inputShape = {
    views: z.array(specialtyViewShape).min(1),
    conflicts: conflictMatrixShape,
    total_messages: z.number().int().nonnegative().optional(),
    total_rounds: z.number().int().positive().optional(),
  };
  server.registerTool(
    "get_concordance_brief",
    {
      title: "get_concordance_brief",
      description:
        "Synthesizes the final ConcordantPlan artifact (Template + Table + Task in one) from SpecialtyViews and a ConflictMatrix. Used by the Convener after conflict resolution to emit the deliverable.",
      inputSchema: inputShape,
    },
    async (rawInput) => {
      const input = rawInput as {
        views: SpecialtyView[];
        conflicts: ConflictMatrix;
        total_messages?: number;
        total_rounds?: number;
      };
      const ctx = extractSharpContext(req);
      if (!ctx) return failure("fhir_context_required");
      const start = Date.now();
      const conveningId = ctx.conveningId ?? null;

      await recordAuditEvent({
        conveningId,
        actor: "lens-mcp/concordance",
        action: "tool_called",
        payload: { tool: "get_concordance_brief", n_views: input.views.length },
      });

      try {
        const { plan, latencyMs } = await buildConcordanceBrief({
          views: input.views,
          conflicts: input.conflicts,
          totalMessages: input.total_messages,
          totalRounds: input.total_rounds,
        });
        await Promise.all([
          recordToolCall({
            conveningId,
            toolName: "get_concordance_brief",
            params: { n_views: input.views.length, n_conflicts: input.conflicts.conflicts.length },
            result: {
              n_actions: plan.action_items.length,
              n_dissents: plan.dissents.length,
              specialties: plan.specialties_consulted,
            },
            status: "success",
            latencyMs,
          }),
          recordAuditEvent({
            conveningId,
            actor: "lens-mcp/concordance",
            action: "plan_synthesized",
            payload: { specialties: plan.specialties_consulted, n_actions: plan.action_items.length },
          }),
        ]);
        return {
          content: [{ type: "text", text: JSON.stringify(plan, null, 2) }],
          structuredContent: plan as unknown as Record<string, unknown>,
        };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        logger.error({ err }, "concordance brief tool failed");
        Sentry.captureException(err);
        await recordToolCall({
          conveningId,
          toolName: "get_concordance_brief",
          params: { n_views: input.views.length },
          status: "error",
          errorMessage: message,
          latencyMs: Date.now() - start,
        });
        return failure(message);
      }
    }
  );
}

// ─── helpers ───────────────────────────────────────────────────────────

function failure(reason: string) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify({ error: reason }) }],
    isError: true,
  };
}

export type { SpecialtyView, ConflictMatrix, ConcordantPlan };
