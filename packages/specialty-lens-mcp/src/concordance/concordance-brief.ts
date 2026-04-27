import { callGemini, Type } from "../llm/gemini.js";
import { logger } from "../observability/logger.js";
import type { ConcordantPlan, ConflictMatrix, SpecialtyView } from "../lenses/types.js";

const CONCORDANCE_BRIEF_PROMPT = `You are the Council Convener's concordance synthesizer. You have:

1. SpecialtyViews from each specialty
2. A ConflictMatrix identifying agreements, conflicts, and abstentions

Your job: produce a single ConcordantPlan that maps to the Prompt Opinion 5Ts framework — Template + Table + Task simultaneously:

- TEMPLATE: a concise structured brief (summary, rationale, plan as continue/start/stop/monitor lists, timing notes)
- TABLE: a conflict log capturing each disagreement, the parties, initial positions, the resolution, and how it was reached (harmonized, deferred-to-specialty, guideline-aligned, patient-preference, unresolved)
- TASK: action items for the primary care clinician with explicit owner, due_within timeframe, and priority (urgent / high / routine)

Resolution methods (use 'method' enum):
- harmonized: parties found common ground via discussion (e.g., switch one drug to address another specialty's concern)
- deferred-to-specialty: one specialty owned the decision based on subject-matter authority
- guideline-aligned: a specific guideline (cite by name) tipped the resolution
- patient-preference: patient values noted as the deciding input
- unresolved: flagged for next round; capture as a task with owner=primary-care and explain

Action items must be specific, actionable, time-bounded. "Follow up with cardiology" is too vague. "Repeat eGFR and BMP in 4 weeks before any new renally-cleared agent" is good.

Preserve dissents — if a specialty maintained an alternate position despite the resolution, capture it in dissents with rationale. Don't paper over disagreement.

Cite which specialties were consulted (specialties_consulted array) and provide an audit_summary with rough counts.`;

const concordantPlanSchema = {
  type: Type.OBJECT,
  properties: {
    brief: {
      type: Type.OBJECT,
      properties: {
        summary: { type: Type.STRING },
        rationale: { type: Type.STRING },
        plan: {
          type: Type.OBJECT,
          properties: {
            continue: { type: Type.ARRAY, items: { type: Type.STRING } },
            start: { type: Type.ARRAY, items: { type: Type.STRING } },
            stop: { type: Type.ARRAY, items: { type: Type.STRING } },
            monitor: { type: Type.ARRAY, items: { type: Type.STRING } },
          },
          required: ["continue", "start", "stop", "monitor"],
        },
        timing_notes: { type: Type.ARRAY, items: { type: Type.STRING } },
      },
      required: ["summary", "rationale", "plan", "timing_notes"],
    },
    conflict_log: {
      type: Type.ARRAY,
      items: {
        type: Type.OBJECT,
        properties: {
          topic: { type: Type.STRING },
          parties: { type: Type.ARRAY, items: { type: Type.STRING } },
          initial_positions: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                specialty: { type: Type.STRING },
                position: { type: Type.STRING },
              },
              required: ["specialty", "position"],
            },
          },
          resolution: { type: Type.STRING },
          method: {
            type: Type.STRING,
            enum: ["harmonized", "deferred-to-specialty", "guideline-aligned", "patient-preference", "unresolved"],
          },
        },
        required: ["topic", "parties", "initial_positions", "resolution", "method"],
      },
    },
    action_items: {
      type: Type.ARRAY,
      items: {
        type: Type.OBJECT,
        properties: {
          description: { type: Type.STRING },
          owner: { type: Type.STRING },
          due_within: { type: Type.STRING },
          priority: { type: Type.STRING, enum: ["urgent", "high", "routine"] },
        },
        required: ["description", "owner", "due_within", "priority"],
      },
    },
    dissents: {
      type: Type.ARRAY,
      items: {
        type: Type.OBJECT,
        properties: {
          specialty: { type: Type.STRING },
          position: { type: Type.STRING },
          rationale: { type: Type.STRING },
        },
        required: ["specialty", "position", "rationale"],
      },
    },
  },
  required: ["brief", "conflict_log", "action_items", "dissents"],
};

export interface ConcordanceBriefResult {
  plan: ConcordantPlan;
  latencyMs: number;
}

export async function buildConcordanceBrief(args: {
  views: SpecialtyView[];
  conflicts: ConflictMatrix;
  totalMessages?: number;
  totalRounds?: number;
}): Promise<ConcordanceBriefResult> {
  if (args.views.length === 0) {
    throw new Error("buildConcordanceBrief: at least one SpecialtyView required");
  }

  const patientId = args.views[0]!.patient_id;

  const userPrompt = `Patient ID: ${patientId}

SpecialtyViews:
${args.views.map((v) => `- ${v.specialty}: concerns=[${v.primary_concerns.join("; ")}] red_flags=[${v.red_flags.join("; ")}]`).join("\n")}

ConflictMatrix:
${JSON.stringify(args.conflicts, null, 2)}

Now synthesize the ConcordantPlan as JSON.`;

  logger.info({ patientId, n_views: args.views.length, n_conflicts: args.conflicts.conflicts.length }, "concordance: building brief");

  const { data, latencyMs } = await callGemini<Omit<ConcordantPlan, "patient_id" | "generated_at" | "specialties_consulted" | "audit_summary">>({
    systemInstruction: CONCORDANCE_BRIEF_PROMPT,
    userPrompt,
    responseSchema: concordantPlanSchema,
    temperature: 0.2,
  });

  const fhirRefsTouched = new Set<string>();
  for (const v of args.views) v.fhir_refs.forEach((r) => fhirRefsTouched.add(r));

  const plan: ConcordantPlan = {
    patient_id: patientId,
    generated_at: new Date().toISOString(),
    specialties_consulted: args.views.map((v) => v.specialty),
    audit_summary: {
      total_messages: args.totalMessages ?? 0,
      total_rounds: args.totalRounds ?? 1,
      fhir_resources_touched: fhirRefsTouched.size,
    },
    ...data,
  };

  logger.info(
    {
      patientId,
      n_actions: plan.action_items.length,
      n_dissents: plan.dissents.length,
      latencyMs,
    },
    "concordance: brief complete"
  );

  return { plan, latencyMs };
}
