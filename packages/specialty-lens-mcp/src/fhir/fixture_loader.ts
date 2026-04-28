/**
 * Demo-fixture loader for the Council MCP.
 *
 * The Prompt Opinion workspace FHIR proxy at
 * `app.promptopinion.ai/api/workspaces/<id>/fhir` requires the operating user's
 * session cookie for auth (observed regression as of 2026-04-26: bearer-token /
 * empty-token paths return HTTP 403). Service-to-service callers — like our
 * SHARP-on-MCP server, which holds neither the user session nor a workspace API
 * key — therefore cannot read patient data from PO during deliberation, even
 * though the platform forwarded a SHARP context.
 *
 * Rather than baking workspace cookies into the deploy (insecure, ephemeral)
 * we ship hand-crafted demo FHIR bundles WITH the MCP itself and fall back to
 * them when the live FHIR fetch fails. This keeps the demo path deterministic
 * and self-contained: judges can replay any deliberation without depending on
 * PO's workspace auth state, and the agents still operate over realistic
 * multi-morbid charts.
 *
 * Honesty is built in: the lens output's reasoning_trace surfaces "demo bundle
 * fallback used" so a clinician reviewer always knows whether the agent saw
 * live or fixture data.
 */

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import type {
  AllergyIntolerance,
  Bundle,
  Condition,
  Encounter,
  MedicationRequest,
  MedicationStatement,
  Observation,
  Patient,
  PatientChart,
  Procedure,
} from "./types.js";
import { logger } from "../observability/logger.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FIXTURE_DIR = join(__dirname, "fixtures");

// One canonical multi-morbid demo patient — Mrs. Chen has the richest chart
// (HFrEF, AFib, CKD-3, Type 2 diabetes, breast cancer follow-up). All 8
// specialties have something meaningful to say about her, which is what the
// Council deliberation is designed to showcase.
const DEFAULT_DEMO_BUNDLE = "mrs-chen.json";

interface DemoBundle {
  resourceType: "Bundle";
  type: string;
  entry: Array<{ resource?: { resourceType?: string } & Record<string, unknown> }>;
}

let cachedBundle: DemoBundle | null = null;

async function loadBundle(): Promise<DemoBundle> {
  if (cachedBundle) return cachedBundle;
  const path = join(FIXTURE_DIR, DEFAULT_DEMO_BUNDLE);
  const raw = await readFile(path, "utf8");
  cachedBundle = JSON.parse(raw) as DemoBundle;
  return cachedBundle;
}

function entries<T extends { resourceType?: string }>(
  bundle: DemoBundle,
  resourceType: T["resourceType"]
): T[] {
  const out: T[] = [];
  for (const e of bundle.entry ?? []) {
    if (e.resource?.resourceType === resourceType) out.push(e.resource as unknown as T);
  }
  return out;
}

/** Build a PatientChart from the demo bundle, swapping in the caller's patient_id
 *  so downstream FHIR refs remain consistent with what the platform sees. */
export async function loadDemoChart(callerPatientId: string): Promise<PatientChart> {
  const bundle = await loadBundle();
  const patientFromBundle = entries<Patient>(bundle, "Patient")[0];
  if (!patientFromBundle) {
    throw new Error("demo bundle missing Patient resource");
  }
  // Preserve caller's patient_id on the surfaced Patient so downstream
  // chartFhirRefs and audit logs reference the platform's id, not the bundle's.
  const patient: Patient = { ...patientFromBundle, id: callerPatientId };

  logger.warn(
    { callerPatientId, sourceBundle: DEFAULT_DEMO_BUNDLE },
    "FHIR fallback engaged — using demo bundle (live workspace FHIR was unavailable)"
  );

  return {
    patient,
    conditions: entries<Condition>(bundle, "Condition"),
    medications: entries<MedicationStatement>(bundle, "MedicationStatement"),
    medicationRequests: entries<MedicationRequest>(bundle, "MedicationRequest"),
    observations: entries<Observation>(bundle, "Observation"),
    allergies: entries<AllergyIntolerance>(bundle, "AllergyIntolerance"),
    procedures: entries<Procedure>(bundle, "Procedure"),
    encounters: entries<Encounter>(bundle, "Encounter"),
  };
}

/** True when the live FHIR fetch error is one we'd rather fall back from than
 *  hard-fail. Treat 401/403/404/timeouts as "demo-recoverable" — anything else
 *  is a programming bug we want to surface. */
export function isFallbackable(err: unknown): boolean {
  if (!(err instanceof Error)) return false;
  const message = err.message.toLowerCase();
  return (
    message.includes("401") ||
    message.includes("403") ||
    message.includes("404") ||
    message.includes("timeout") ||
    message.includes("etimedout") ||
    message.includes("econnreset")
  );
}
