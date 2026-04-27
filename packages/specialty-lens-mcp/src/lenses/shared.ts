import { callGemini, Type } from "../llm/gemini.js";
import { fetchPatientChart, summarizeChart, chartFhirRefs } from "../fhir/client.js";
import type { SharpContext } from "../sharp/context.js";
import type { SpecialtyView, Specialty } from "./types.js";
import { logger } from "../observability/logger.js";

/** JSON schema (Gemini-flavored) for SpecialtyView output. */
const specialtyViewSchema = {
  type: Type.OBJECT,
  properties: {
    patient_summary_excerpt: { type: Type.STRING },
    relevant_conditions: { type: Type.ARRAY, items: { type: Type.STRING } },
    relevant_medications: { type: Type.ARRAY, items: { type: Type.STRING } },
    relevant_observations: { type: Type.ARRAY, items: { type: Type.STRING } },
    applicable_guidelines: { type: Type.ARRAY, items: { type: Type.STRING } },
    primary_concerns: { type: Type.ARRAY, items: { type: Type.STRING } },
    red_flags: { type: Type.ARRAY, items: { type: Type.STRING } },
    proposed_plan: {
      type: Type.OBJECT,
      properties: {
        continue: { type: Type.ARRAY, items: { type: Type.STRING } },
        start: { type: Type.ARRAY, items: { type: Type.STRING } },
        stop: { type: Type.ARRAY, items: { type: Type.STRING } },
        monitor: { type: Type.ARRAY, items: { type: Type.STRING } },
      },
      required: ["continue", "start", "stop", "monitor"],
    },
    confidence_notes: { type: Type.STRING },
    reasoning_trace: { type: Type.ARRAY, items: { type: Type.STRING } },
  },
  required: [
    "patient_summary_excerpt",
    "relevant_conditions",
    "relevant_medications",
    "relevant_observations",
    "applicable_guidelines",
    "primary_concerns",
    "red_flags",
    "proposed_plan",
    "confidence_notes",
    "reasoning_trace",
  ],
};

/** Common boilerplate appended to every specialty system prompt. */
const COMMON_DIRECTIVES = `
General guidelines:
- This is clinical decision support for a clinician audience. Frame all output as a draft for clinician review, never as a directive to a patient.
- DO NOT quote published guidelines verbatim — paraphrase only. Reference guideline source by name (e.g., "ACC/AHA AFib 2023") when applicable.
- Reason explicitly. Capture each step in reasoning_trace as a short numbered string.
- Flag uncertainty in confidence_notes — say what you'd want clarified or what additional data would change your mind.
- Stay strictly in your specialty. If a question is outside your scope, say so in confidence_notes and abstain rather than speculate.
- The patient_summary_excerpt should be 2-3 sentences focused on what's relevant to YOUR specialty's perspective.
- proposed_plan.continue/start/stop/monitor are concrete, specialty-grounded recommendations. Avoid vague items.
- relevant_* arrays are short labels (e.g. "Apixaban 5mg BID for AFib"), not full FHIR resource dumps.
`;

export interface RunLensArgs {
  ctx: SharpContext;
  patientId: string;
  focusProblem?: string;
}

export interface LensSpec {
  specialty: Specialty;
  systemPrompt: string;
}

/** Run a single specialty lens against a patient. */
export async function runLens(spec: LensSpec, args: RunLensArgs): Promise<{ view: SpecialtyView; latencyMs: number }> {
  logger.info({ specialty: spec.specialty, patientId: args.patientId }, "lens: starting");

  const chart = await fetchPatientChart(args.ctx, args.patientId);
  const summary = summarizeChart(chart);
  const fhirRefs = chartFhirRefs(chart);

  const focusBlock = args.focusProblem ? `\n\nFocus problem (caller-specified): ${args.focusProblem}\n` : "";
  const userPrompt = `Patient chart (synthetic; SHARP-context-bridged from the workspace FHIR server):\n\n${summary}${focusBlock}\n\nProvide your specialty perspective as JSON matching the SpecialtyView schema.`;

  const { data, latencyMs } = await callGemini<Omit<SpecialtyView, "specialty" | "patient_id" | "fhir_refs">>({
    systemInstruction: spec.systemPrompt + "\n" + COMMON_DIRECTIVES,
    userPrompt,
    responseSchema: specialtyViewSchema,
  });

  const view: SpecialtyView = {
    specialty: spec.specialty,
    patient_id: args.patientId,
    fhir_refs: fhirRefs,
    ...data,
  };

  logger.info({ specialty: spec.specialty, patientId: args.patientId, latencyMs }, "lens: complete");
  return { view, latencyMs };
}
