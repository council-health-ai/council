/** SHARP-on-MCP header constants — all lowercase to match Express's normalized header keys. */
export const SHARP_HEADERS = {
  FHIR_SERVER_URL: "x-fhir-server-url",
  FHIR_ACCESS_TOKEN: "x-fhir-access-token",
  PATIENT_ID: "x-patient-id",
} as const;

/** Council-specific extension headers (proposed in our SHARP RFC). */
export const COUNCIL_HEADERS = {
  CONVENING_ID: "x-council-convening-id",
  SPECIALTY: "x-council-specialty",
  ROUND_ID: "x-council-round-id",
} as const;

/** SMART scopes that the lens MCP requests on the FHIR server. */
export const SHARP_SCOPES = [
  { name: "patient/Patient.rs", required: true },
  { name: "patient/Condition.rs" },
  { name: "patient/MedicationStatement.rs" },
  { name: "patient/MedicationRequest.rs" },
  { name: "patient/Observation.rs" },
  { name: "patient/AllergyIntolerance.rs" },
  { name: "patient/Procedure.rs" },
  { name: "patient/Encounter.rs" },
];

/** Capability advertisement — covers BOTH the spec form and the Prompt Opinion reference impl form. */
export const SHARP_CAPABILITIES = {
  experimental: {
    // Spec form per https://sharponmcp.com/key-components.html
    fhir_context_required: { value: true },
  },
  extensions: {
    // Implementation form parsed by the Prompt Opinion platform
    "ai.promptopinion/fhir-context": {
      scopes: SHARP_SCOPES,
    },
    // Council Convening Session extension (proposed RFC)
    "ai.council-health/convening-session": {
      version: "0.1",
      headers: ["x-council-convening-id", "x-council-specialty", "x-council-round-id"],
      description:
        "Optional headers used by Council convener+specialty agents to group MCP calls within a single deliberation, enabling per-session caching, audit grouping, and specialty-scoped tool authorization.",
    },
  },
};
