import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { config } from "../config.js";
import { logger } from "./logger.js";

let client: SupabaseClient | null = null;

function getClient(): SupabaseClient | null {
  if (client) return client;
  if (!config.SUPABASE_URL || !config.SUPABASE_SERVICE_ROLE_KEY) {
    return null;
  }
  client = createClient(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return client;
}

/** Record an MCP tool invocation in Supabase. Non-blocking. */
export async function recordToolCall(args: {
  conveningId?: string | null;
  toolName: string;
  params: unknown;
  result?: unknown;
  status: "success" | "error";
  errorMessage?: string;
  latencyMs: number;
}): Promise<void> {
  const c = getClient();
  if (!c) return;

  const { error } = await c.from("mcp_tool_calls").insert({
    convening_id: args.conveningId ?? null,
    tool_name: args.toolName,
    params: args.params as never,
    result: args.result as never,
    status: args.status,
    error_message: args.errorMessage,
    latency_ms: args.latencyMs,
  });
  if (error) logger.warn({ err: error }, "audit: recordToolCall failed");
}

/** Record a generic audit event. */
export async function recordAuditEvent(args: {
  conveningId?: string | null;
  actor: string;
  action: AuditAction;
  payload?: Record<string, unknown>;
  fhirRefs?: string[];
  roundId?: number;
}): Promise<void> {
  const c = getClient();
  if (!c) return;

  const { error } = await c.from("audit_events").insert({
    convening_id: args.conveningId ?? null,
    actor: args.actor,
    action: args.action,
    payload: (args.payload ?? {}) as never,
    fhir_refs: args.fhirRefs ? (args.fhirRefs as never) : null,
    round_id: args.roundId ?? null,
  });
  if (error) logger.warn({ err: error }, "audit: recordAuditEvent failed");
}

export type AuditAction =
  | "session_started"
  | "session_ended"
  | "message_received"
  | "message_emitted"
  | "reasoning_started"
  | "reasoning_completed"
  | "tool_called"
  | "tool_returned"
  | "fhir_query"
  | "fhir_returned"
  | "conflict_flagged"
  | "conflict_resolved"
  | "plan_synthesized"
  | "guideline_referenced";
