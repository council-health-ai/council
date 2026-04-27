import { callGemini, Type } from "../llm/gemini.js";
import { logger } from "../observability/logger.js";
import type { ConflictMatrix, SpecialtyView } from "../lenses/types.js";

const CONFLICT_MATRIX_PROMPT = `You are the Council Convener's conflict-matrix synthesizer. You have received specialty perspectives (SpecialtyViews) from multiple specialty agents on a single multi-morbid patient. Your job is to identify:

1. CONFLICTS — places where specialties' proposed plans directly disagree, where one specialty's recommendation contradicts another's safety constraint, or where guideline applicability is contested.
2. AGREEMENTS — places where multiple specialties independently converge on the same recommendation (a strong signal).
3. ABSTENTIONS — places where a specialty explicitly opted out as out-of-scope.

Conflicts to surface explicitly:
- Drug-drug interactions involving multiple specialties' medications
- Dose adjustments contested across specialties (e.g., renal dosing of a cardiac drug)
- Sequencing conflicts (e.g., timing of chemotherapy vs surgery vs anticoagulation hold)
- Goal-of-care or risk-tolerance differences (rare but real)
- Pregnancy/pediatric-specific contraindications versus general guidance

Output as JSON matching the ConflictMatrix schema. Each conflict has a topic (short string), the parties (specialties) involved, each party's position (1-2 sentences), severity (low/medium/high), and the round in which it should be resolved.

Be specific. "Disagreement on cardiac med" is too vague. "Cardiology recommends apixaban 5 mg BID; Nephrology is monitoring eGFR trend and recommends repeat panel before any dose change" is the right level.

If specialties agree, capture the unified position succinctly.

Do NOT invent conflicts that aren't in the views. Do NOT paper over real conflicts. The Council values conflict surfacing as a feature.`;

const conflictMatrixSchema = {
  type: Type.OBJECT,
  properties: {
    conflicts: {
      type: Type.ARRAY,
      items: {
        type: Type.OBJECT,
        properties: {
          id: { type: Type.STRING },
          topic: { type: Type.STRING },
          parties: { type: Type.ARRAY, items: { type: Type.STRING } },
          positions: {
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
          severity: { type: Type.STRING, enum: ["low", "medium", "high"] },
          resolution_required_by_round: { type: Type.NUMBER },
        },
        required: ["id", "topic", "parties", "positions", "severity"],
      },
    },
    agreements: {
      type: Type.ARRAY,
      items: {
        type: Type.OBJECT,
        properties: {
          topic: { type: Type.STRING },
          parties: { type: Type.ARRAY, items: { type: Type.STRING } },
          unified_position: { type: Type.STRING },
        },
        required: ["topic", "parties", "unified_position"],
      },
    },
    abstentions: {
      type: Type.ARRAY,
      items: {
        type: Type.OBJECT,
        properties: {
          specialty: { type: Type.STRING },
          topic: { type: Type.STRING },
          reason: { type: Type.STRING },
        },
        required: ["specialty", "topic", "reason"],
      },
    },
  },
  required: ["conflicts", "agreements", "abstentions"],
};

export interface ConflictMatrixResult {
  matrix: ConflictMatrix;
  latencyMs: number;
}

export async function buildConflictMatrix(views: SpecialtyView[]): Promise<ConflictMatrixResult> {
  if (views.length === 0) {
    throw new Error("buildConflictMatrix: at least one SpecialtyView required");
  }

  const patientIds = new Set(views.map((v) => v.patient_id));
  if (patientIds.size > 1) {
    throw new Error(`buildConflictMatrix: views span multiple patients (${[...patientIds].join(", ")})`);
  }
  const patientId = views[0]!.patient_id;

  const userPrompt = `Patient ID: ${patientId}\n\nSpecialty views:\n\n${views.map((v) => formatView(v)).join("\n\n---\n\n")}\n\nReturn a ConflictMatrix as JSON.`;

  logger.info({ patientId, n_views: views.length }, "concordance: building conflict matrix");

  const { data, latencyMs } = await callGemini<{
    conflicts: ConflictMatrix["conflicts"];
    agreements: ConflictMatrix["agreements"];
    abstentions: ConflictMatrix["abstentions"];
  }>({
    systemInstruction: CONFLICT_MATRIX_PROMPT,
    userPrompt,
    responseSchema: conflictMatrixSchema,
    temperature: 0.2,
  });

  const matrix: ConflictMatrix = {
    patient_id: patientId,
    specialties: views.map((v) => v.specialty),
    conflicts: data.conflicts,
    agreements: data.agreements,
    abstentions: data.abstentions,
  };

  logger.info(
    { patientId, n_conflicts: matrix.conflicts.length, n_agreements: matrix.agreements.length, latencyMs },
    "concordance: conflict matrix complete"
  );
  return { matrix, latencyMs };
}

function formatView(v: SpecialtyView): string {
  return `## ${v.specialty.toUpperCase()}

Patient excerpt: ${v.patient_summary_excerpt}

Primary concerns:
${v.primary_concerns.map((c) => `  · ${c}`).join("\n")}

Red flags:
${v.red_flags.map((r) => `  · ${r}`).join("\n")}

Proposed plan:
  Continue: ${v.proposed_plan.continue.join("; ") || "(none)"}
  Start:    ${v.proposed_plan.start.join("; ") || "(none)"}
  Stop:     ${v.proposed_plan.stop.join("; ") || "(none)"}
  Monitor:  ${v.proposed_plan.monitor.join("; ") || "(none)"}

Applicable guidelines: ${v.applicable_guidelines.join("; ")}
Confidence notes: ${v.confidence_notes}`;
}
