# 05 · FHIR and SHARP

The FHIR/SHARP layer is The Council's clinical-trust backbone. SHARP-on-MCP
is the protocol that lets the MCP server receive FHIR context (server URL,
bearer token, patient ID) safely from the agent host.

Two fights here: PO's empty-bearer-token regression, and shipping a real
upstream RFC PR for the Council convening-session SHARP extension.

---

### PO's empty-bearer-token regression

**Symptom (April 26+):** The Prompt Opinion General Chat platform started
sending FHIR context with an **empty string** bearer token instead of a
valid SMART bearer token. Per-workspace SMART scopes were configured but
the runtime substituted "" at invocation time.

**Layer 1 — SHARP middleware:** Initially returned 403 on missing FHIR
context. Empty-string headers are technically "present" in HTTP semantics
but our middleware's `if (!fhirAccessToken)` check failed.

**Fix at layer 1:** Allow present-but-empty headers. Only return 403 when
headers are completely absent. Logged as a structured warning so the
audit log flags the empty-token case.

```typescript
const fhirUrlPresent = fhirUrlHeader !== undefined;
const fhirTokenPresent = fhirTokenHeader !== undefined;
if (fhirUrlPresent && fhirTokenPresent) {
  if (!fhirUrl || !fhirToken) {
    logger.warn({ ... }, "SHARP: tools/call with empty FHIR header");
  }
  return next();
}
```

**Layer 2 — context extractor:** Even with the middleware passing through,
the SHARP context extractor in `sharp/context.ts` still rejected empty
tokens because of:
```typescript
if (!fhirServerUrl || !fhirAccessToken) return null;
```

JS empty-string is falsy. Lens MCP returned `fhir_context_required`
to every specialty. Result: every specialty agent reported "I cannot
access patient data due to HTTP 403 error" — even though the headers
were technically present.

**Fix at layer 2:** Require only fhirServerUrl. Token normalized to
empty string and forwarded. Downstream FHIR axios client handles the
empty case (omits Authorization header):
```typescript
if (!fhirServerUrl) return null;
const token = fhirAccessToken ?? "";
```

**Layer 3 — FHIR axios client:** Added explicit logic to omit the
Authorization header entirely when the token is empty:
```typescript
if (ctx.fhirAccessToken && ctx.fhirAccessToken.trim().length > 0) {
  headers.Authorization = `Bearer ${ctx.fhirAccessToken}`;
}
```

This gives the workspace's anonymous-access path a chance to serve
when the host's bearer is empty.

**Layer 4 — fixture fallback (the real fix):** Even with all three
layers above, PO's workspace FHIR proxy at
`app.promptopinion.ai/api/workspaces/<id>/fhir` requires the operating
**user's session cookie** for auth. Service-to-service callers without
a workspace API key (us) get 403 on every chart fetch.

Built `packages/specialty-lens-mcp/src/fhir/fixture_loader.ts` that ships
the four hand-crafted demo bundles WITH the MCP and falls back to
`mrs-chen.json` (the most multi-morbid demo patient) when live FHIR
returns 401/403/404 or times out:

```typescript
export function isFallbackable(err: unknown): boolean {
  const msg = (err instanceof Error ? err.message : String(err)).toLowerCase();
  return ["401", "403", "404", "timeout", "etimedout", "econnreset"]
    .some(k => msg.includes(k));
}

export async function fetchPatientChart(ctx, patientId): Promise<PatientChart> {
  try {
    return await fetchPatientChartLive(ctx, patientId);
  } catch (err) {
    if (isFallbackable(err)) {
      logger.warn({ patientId, err }, "Live FHIR fetch failed; engaging demo bundle fallback");
      return loadDemoChart(patientId);
    }
    throw err;
  }
}
```

The fallback path is logged at WARN and the audit trail surfaces
"demo bundle fallback used" so a clinician reviewer always knows
whether the lens saw live or fixture data.

**Why this matters:** Honesty is built into the fallback. Any clinical
recommendation the Council produces in PO chat right now is grounded
on `mrs-chen.json` (the bundled chart) because PO's FHIR proxy isn't
service-to-service-friendly. Documented honestly; not a hack.

---

### SHARP-on-MCP 403 enforcement (none of the references do it)

**Discovery:** The SHARP spec at https://sharponmcp.com/key-components.html
says servers advertising `fhir_context_required` MUST return 403 when
FHIR context headers are missing. **None of the three reference
implementations** in `prompt-opinion/po-community-mcp` (TypeScript,
Python, .NET) actually do this — they throw at tool-call time via the
JSON-RPC error envelope, which doesn't satisfy the spec wording.

**The Council's MCP is the first SHARP impl to enforce it.**
`packages/specialty-lens-mcp/src/sharp/middleware.ts:25` returns a real
HTTP 403 on `tools/call` when both FHIR headers are completely absent
(while still allowing present-but-empty for the PO regression).

**Why this matters:** Spec correctness flex. Documented in the SHARP RFC
PR (next entry).

---

### SHARP capability advertisement: spec form + impl form

**Decision:** Advertise both forms in the Agent Card capabilities to
double-cover spec correctness AND PO's actual parser:

```typescript
capabilities: {
  experimental: {
    fhir_context_required: { value: true }            // spec form
  },
  extensions: {
    "ai.promptopinion/fhir-context": {                // PO platform impl form
      scopes: [...]
    },
    "ai.council-health/convening-session": {          // Council RFC extension
      version: "0.1",
      headers: ["x-council-convening-id", "x-council-specialty", "x-council-round-id"]
    }
  }
}
```

The dual advertisement means SHARP-aware tooling sees the spec key,
PO's platform sees the implementation key, and the gap is documented
in the SHARP RFC PR as a real example of "the spec said X, the impl
parses Y, and that gap matters in production."

---

### SHARP convening-session extension RFC

**Built and shipped as an upstream PR.** See `docs/sharp-extension-coin-rfc.md`.

**What it adds:** Three optional headers for grouping MCP calls within
a multi-agent deliberation:
- `X-Council-Convening-Id` — the deliberation session UUID
- `X-Council-Specialty` — the specialty role making the call
- `X-Council-Round-Id` — Round 1 / Round 2 / etc.

Lets a SHARP-aware MCP server group tool calls into deliberation
sessions, enable per-session caching, and export audit trails grouped
by session — without requiring the spec to absorb the full Council
ontology.

**Why this matters:** Visibility to Mandel (judge — author of the
canonical SMART-on-FHIR JAMIA paper, author of the Banterop /
language-first interoperability work). The RFC is a real public artifact,
not a slide. It demonstrates that we engaged with the spec ecosystem,
not just the platform.

---

### Hand-crafted demo bundles vs Synthea filler

**Decision:** Four archetype FHIR R4 transaction bundles, hand-built
for clinical precision:

- `mrs-chen.json` — 67yo postmenopausal female, ER+/PR+/HER2- breast
  cancer, paroxysmal AFib on apixaban, T2DM HbA1c 9.2%, CKD stage 3a
  (eGFR 38), HTN. The 4-specialty (cardiology + oncology + nephrology +
  endocrinology) cardiometabolic-oncology archetype.
- `aanya.json` — pediatric syndromic case (Williams syndrome) — pediatrics
  + cardiology + endocrinology archetype.
- `sarah.json` — pregnancy + chronic disease — obstetrics MFM archetype.
- `henderson.json` — geriatric polypharmacy + perioperative — anesthesia
  + cardiology + nephrology archetype.

Each bundle is a real FHIR R4 transaction with Patient, Conditions,
MedicationStatements, MedicationRequests, Observations, AllergyIntolerance,
Procedures, Encounters. None reuses Synthea's Patient.id; we control the
identifier system so the conflict-matrix patient-id check works.

Layered atop these: 5-10 random Synthea filler patients from
SyntheticMass for cohort texture in the workspace. Selection of any
filler patient triggers the FHIR fallback to mrs-chen.json (with the
fallback audit warning) since we don't have hand-crafted lenses for
generic patients.

**Why this matters:** Mathur (judge — intensivist, BrainX co-founder)
will catch a clinical error in 30 seconds. Mrs. Chen's chart was
clinician-reviewable from day one. The hand-crafted bundles are the
clinical ground truth; Synthea is texture for the cohort selector.
