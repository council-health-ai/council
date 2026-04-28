import axios, { type AxiosInstance } from "axios";
import { logger } from "../observability/logger.js";
import type { SharpContext } from "../sharp/context.js";
import { isFallbackable, loadDemoChart } from "./fixture_loader.js";
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

/** Build an axios instance configured for SMART-on-FHIR bearer-token forwarding.
 *  When the access token is empty (Prompt Opinion regression as of 2026-04-26),
 *  we omit the Authorization header so the workspace's anonymous-access path
 *  has a chance to serve. The host's actual error surfaces if it requires auth. */
function makeClient(ctx: SharpContext): AxiosInstance {
  const headers: Record<string, string> = { Accept: "application/fhir+json" };
  if (ctx.fhirAccessToken && ctx.fhirAccessToken.trim().length > 0) {
    headers.Authorization = `Bearer ${ctx.fhirAccessToken}`;
  }
  return axios.create({
    baseURL: ctx.fhirServerUrl.replace(/\/$/, ""),
    timeout: 15000,
    headers,
    validateStatus: (s) => s >= 200 && s < 500,
  });
}

async function fetchEntries<T>(http: AxiosInstance, path: string, params: Record<string, string>): Promise<T[]> {
  const start = Date.now();
  try {
    const res = await http.get<Bundle<T>>(path, { params });
    if (res.status === 404) return [];
    if (res.status >= 400) {
      logger.warn({ path, status: res.status, data: res.data }, "FHIR query non-success");
      return [];
    }
    const entries = res.data.entry ?? [];
    return entries.map((e) => e.resource).filter((r): r is T => Boolean(r));
  } catch (err) {
    logger.error({ err, path }, "FHIR query failed");
    return [];
  } finally {
    logger.debug({ path, ms: Date.now() - start }, "FHIR query");
  }
}

async function fetchPatientChartLive(ctx: SharpContext, patientId: string): Promise<PatientChart> {
  const http = makeClient(ctx);

  const [patientRes, conditions, meds, medReqs, observations, allergies, procedures, encounters] = await Promise.all([
    http.get<Patient>(`/Patient/${patientId}`),
    fetchEntries<Condition>(http, "/Condition", { patient: patientId, _count: "200" }),
    fetchEntries<MedicationStatement>(http, "/MedicationStatement", { patient: patientId, _count: "200" }),
    fetchEntries<MedicationRequest>(http, "/MedicationRequest", { patient: patientId, _count: "200" }),
    fetchEntries<Observation>(http, "/Observation", { patient: patientId, _count: "300" }),
    fetchEntries<AllergyIntolerance>(http, "/AllergyIntolerance", { patient: patientId, _count: "100" }),
    fetchEntries<Procedure>(http, "/Procedure", { patient: patientId, _count: "100" }),
    fetchEntries<Encounter>(http, "/Encounter", { patient: patientId, _count: "100" }),
  ]);

  if (patientRes.status >= 400) {
    throw new Error(`Patient/${patientId} fetch failed: HTTP ${patientRes.status}`);
  }

  return {
    patient: patientRes.data,
    conditions,
    medications: meds,
    medicationRequests: medReqs,
    observations,
    allergies,
    procedures,
    encounters,
  };
}

/** Fetch the full patient chart needed by every specialty lens. Conservative —
 *  pulls everything once and lets each lens filter.
 *
 *  Tries the live workspace FHIR endpoint first. If that fails with a known
 *  fallbackable error (401/403/404/timeout) — most commonly Prompt Opinion's
 *  empty-bearer-token regression — falls back to the bundled demo chart so the
 *  deliberation still has clinically meaningful data to reason about. The
 *  fallback path is logged at WARN so it surfaces in HF live logs and audit. */
export async function fetchPatientChart(ctx: SharpContext, patientId: string): Promise<PatientChart> {
  try {
    return await fetchPatientChartLive(ctx, patientId);
  } catch (err) {
    if (isFallbackable(err)) {
      logger.warn(
        { patientId, err: err instanceof Error ? err.message : String(err) },
        "Live FHIR fetch failed; engaging demo bundle fallback"
      );
      return loadDemoChart(patientId);
    }
    throw err;
  }
}

/** Concise text excerpt of a chart, suitable for LLM grounding. */
export function summarizeChart(chart: PatientChart): string {
  const p = chart.patient;
  const lines: string[] = [];
  const name = p.name?.[0] ? `${p.name[0].given?.join(" ") ?? ""} ${p.name[0].family ?? ""}`.trim() : "(unnamed)";
  lines.push(`Patient: ${name} | gender: ${p.gender ?? "unknown"} | DOB: ${p.birthDate ?? "unknown"}`);

  if (chart.conditions.length) {
    lines.push("\nConditions:");
    for (const c of chart.conditions) {
      const status = c.clinicalStatus?.coding?.[0]?.code ?? "?";
      const code = c.code?.text ?? c.code?.coding?.[0]?.display ?? "(unspecified)";
      const onset = c.onsetDateTime ?? "";
      const note = c.note?.[0]?.text ? ` — ${c.note[0].text}` : "";
      lines.push(`  · ${code} [${status}] ${onset}${note}`);
    }
  }
  if (chart.medications.length) {
    lines.push("\nActive medications:");
    for (const m of chart.medications) {
      const med = m.medicationCodeableConcept?.text ?? m.medicationCodeableConcept?.coding?.[0]?.display ?? "(unknown drug)";
      const dose = m.dosage?.[0]?.text ?? "";
      const reason = m.reasonCode?.[0]?.text ? ` (for: ${m.reasonCode[0].text})` : "";
      lines.push(`  · ${med} — ${dose}${reason}`);
    }
  }
  if (chart.observations.length) {
    lines.push("\nRecent observations:");
    const sorted = [...chart.observations].sort((a, b) =>
      String(b.effectiveDateTime ?? "").localeCompare(String(a.effectiveDateTime ?? ""))
    );
    for (const o of sorted.slice(0, 30)) {
      const code = o.code?.text ?? o.code?.coding?.[0]?.display ?? "(unspecified)";
      const value = o.valueQuantity
        ? `${o.valueQuantity.value} ${o.valueQuantity.unit ?? ""}`.trim()
        : o.valueCodeableConcept?.text ?? o.valueString ?? "?";
      const interp = o.interpretation?.[0]?.coding?.[0]?.code
        ? ` (${o.interpretation[0].coding[0].code})`
        : "";
      const when = o.effectiveDateTime ?? "";
      lines.push(`  · ${code}: ${value}${interp} @ ${when}`);
    }
  }
  if (chart.allergies.length) {
    lines.push("\nAllergies:");
    for (const a of chart.allergies) {
      lines.push(`  · ${a.code?.text ?? "(unspecified)"} [${a.criticality ?? "?"}]`);
    }
  }
  if (chart.procedures.length) {
    lines.push("\nProcedures:");
    for (const p of chart.procedures) {
      lines.push(`  · ${p.code?.text ?? "(unspecified)"} @ ${p.performedDateTime ?? "?"}`);
    }
  }
  return lines.join("\n");
}

/** Collect FHIR refs touched by a chart fetch for the audit log. */
export function chartFhirRefs(chart: PatientChart): string[] {
  const refs: string[] = [`Patient/${chart.patient.id}`];
  for (const c of chart.conditions) if (c.id) refs.push(`Condition/${c.id}`);
  for (const m of chart.medications) if (m.id) refs.push(`MedicationStatement/${m.id}`);
  for (const m of chart.medicationRequests) if (m.id) refs.push(`MedicationRequest/${m.id}`);
  for (const o of chart.observations) if (o.id) refs.push(`Observation/${o.id}`);
  for (const a of chart.allergies) if (a.id) refs.push(`AllergyIntolerance/${a.id}`);
  for (const p of chart.procedures) if (p.id) refs.push(`Procedure/${p.id}`);
  for (const e of chart.encounters) if (e.id) refs.push(`Encounter/${e.id}`);
  return refs;
}
