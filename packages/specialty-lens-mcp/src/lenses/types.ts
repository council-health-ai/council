/** Structured output of a single specialty's perspective on a patient. */
export interface SpecialtyView {
  specialty: Specialty;
  patient_id: string;
  patient_summary_excerpt: string;
  relevant_conditions: string[];
  relevant_medications: string[];
  relevant_observations: string[];
  applicable_guidelines: string[];
  primary_concerns: string[];
  red_flags: string[];
  proposed_plan: {
    continue: string[];
    start: string[];
    stop: string[];
    monitor: string[];
  };
  confidence_notes: string;
  reasoning_trace: string[];
  fhir_refs: string[];
}

export type Specialty =
  | "cardiology"
  | "oncology"
  | "nephrology"
  | "endocrinology"
  | "obstetrics"
  | "developmental_pediatrics"
  | "psychiatry"
  | "anesthesia";

/** Output of get_council_conflict_matrix. */
export interface ConflictMatrix {
  patient_id: string;
  specialties: Specialty[];
  conflicts: Conflict[];
  agreements: Agreement[];
  abstentions: Abstention[];
}

export interface Conflict {
  id: string;
  topic: string;
  parties: Specialty[];
  positions: Array<{ specialty: Specialty; position: string }>;
  severity: "low" | "medium" | "high";
  resolution_required_by_round?: number;
}

export interface Agreement {
  topic: string;
  parties: Specialty[];
  unified_position: string;
}

export interface Abstention {
  specialty: Specialty;
  topic: string;
  reason: string;
}

/** Final ConcordantPlan artifact — Template + Table + Task in one. */
export interface ConcordantPlan {
  patient_id: string;
  generated_at: string;
  specialties_consulted: Specialty[];
  // 5T: Template — the structured concordant brief
  brief: {
    summary: string;
    rationale: string;
    plan: {
      continue: string[];
      start: string[];
      stop: string[];
      monitor: string[];
    };
    timing_notes: string[];
  };
  // 5T: Table — the conflict matrix with resolutions
  conflict_log: Array<{
    topic: string;
    parties: Specialty[];
    initial_positions: Array<{ specialty: Specialty; position: string }>;
    resolution: string;
    method: "harmonized" | "deferred-to-specialty" | "guideline-aligned" | "patient-preference" | "unresolved";
  }>;
  // 5T: Task — clinician action items
  action_items: Array<{
    description: string;
    owner: "primary-care" | Specialty;
    due_within: string;
    priority: "urgent" | "high" | "routine";
  }>;
  // Provenance
  dissents: Array<{ specialty: Specialty; position: string; rationale: string }>;
  audit_summary: {
    total_messages: number;
    total_rounds: number;
    fhir_resources_touched: number;
  };
}
