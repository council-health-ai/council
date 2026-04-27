# specialty-lens-mcp

SHARP-on-MCP TypeScript server exposing 8 healthcare specialty lenses plus concordance tools for The Council.

## Tools

Per-specialty perspective:

- `get_cardiology_perspective(patient_id, focus_problem?)` → `SpecialtyView`
- `get_oncology_perspective(...)` → `SpecialtyView`
- `get_nephrology_perspective(...)` → `SpecialtyView`
- `get_endocrinology_perspective(...)` → `SpecialtyView`
- `get_obstetrics_perspective(...)` → `SpecialtyView`
- `get_developmental_pediatrics_perspective(...)` → `SpecialtyView`
- `get_psychiatry_perspective(...)` → `SpecialtyView`
- `get_anesthesia_perspective(...)` → `SpecialtyView`

Concordance:

- `get_council_conflict_matrix(views: SpecialtyView[])` → `ConflictMatrix`
- `get_concordance_brief(views, conflicts)` → `ConcordantPlan`

## SHARP-on-MCP compliance

The server advertises **both** capability shapes for maximum interoperability:

```jsonc
{
  "capabilities": {
    "experimental": { "fhir_context_required": { "value": true } },   // SHARP spec form
    "extensions": {
      "ai.promptopinion/fhir-context": {                              // Prompt Opinion impl form
        "scopes": [
          { "name": "patient/Patient.rs", "required": true },
          { "name": "patient/Condition.rs" },
          { "name": "patient/MedicationStatement.rs" },
          { "name": "patient/MedicationRequest.rs" },
          { "name": "patient/Observation.rs" },
          { "name": "patient/AllergyIntolerance.rs" },
          { "name": "patient/Procedure.rs" },
          { "name": "patient/Encounter.rs" }
        ]
      }
    }
  }
}
```

The divergence between spec and reference impl is documented in [docs/sharp-extension-coin-rfc.md](../../docs/sharp-extension-coin-rfc.md).

### 403 enforcement

When `SHARP_ENFORCE_403=true` (the default), `tools/call` requests without the required FHIR context headers receive a **real HTTP 403** at request entry — not a JSON-RPC error after method dispatch. None of the three reference SHARP-on-MCP implementations (TypeScript, Python, .NET in `prompt-opinion/po-community-mcp`) currently do this.

## Headers expected

```
X-FHIR-Server-URL:  https://app.promptopinion.ai/api/workspaces/<id>/fhir
X-FHIR-Access-Token: <bearer token forwarded by the platform>
X-Patient-ID:        <optional; auto-extracted from the JWT `patient` claim if absent>
```

## Run locally

```bash
pnpm install
cp .env.example .env
# fill GEMINI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SENTRY_DSN
pnpm dev
```

Server listens on `:7860/mcp`.

## Deploy

Built and deployed to Hugging Face Spaces (`council-health-ai/specialty-lens-mcp`) via Docker SDK. See the root [README](../../README.md) for the full deployment story.
