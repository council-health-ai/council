# 02 · The LLM vendor saga

Multiple days of work on this. The summary is: getting Gemini to actually
serve our 8 specialty agents on a reliable, free tier was the single
biggest infrastructure battle of the project.

---

### Eight different API keys, all blocked

**Symptom:** Tried 8 distinct API keys (mix of free-tier and "paid")
across days. Every single one returned `429 RESOURCE_EXHAUSTED`.

**Investigation:**
- Free-tier keys: quota legitimately exhausted. Free Gemini Flash on AI
  Studio: ~20 requests/day per key. 8 specialty agents × 1 deliberation
  consumes the day's quota.
- Two "paid" keys: prepayment credits depleted (no active billing source).
- Two suspended/expired.

**Realization:** AI Studio API keys and Vertex AI service accounts draw
from completely different billing pools. The user had a $300 GCP trial
credit on `firm-plexus-363809` but it was useless to AI Studio keys.

---

### "Why isn't my $300 GCP credit being used?"

**Root cause documented (with citations from a Vertex DevRel rep on Reddit):**

| Path | Source | Counts against $300 trial? |
|---|---|---|
| AI Studio API key | aistudio.google.com | **No** — separate consumer billing |
| Vertex Express API key | console.cloud.google.com (Express) | **No** — separate Express tier |
| **Vertex service account JSON** | console → IAM | **Yes — only path that uses the trial** |

**Fix:** Migrated to a service account.

```
gcloud iam service-accounts create council-vertex \
  --project=firm-plexus-363809 \
  --display-name="Council Vertex AI"

gcloud projects add-iam-policy-binding firm-plexus-363809 \
  --member="serviceAccount:council-vertex@firm-plexus-363809.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud iam service-accounts keys create ~/.config/gcloud/keys/council-vertex.json \
  --iam-account=council-vertex@firm-plexus-363809.iam.gserviceaccount.com
```

Set GOOGLE_APPLICATION_CREDENTIALS, GOOGLE_CLOUD_PROJECT,
GOOGLE_CLOUD_LOCATION=us-central1, GOOGLE_GENAI_USE_VERTEXAI=true. The
google-genai SDK auto-detects Vertex from these.

---

### IAM propagation race conditions

**Symptom:** Just after creating the SA + role binding, first Gemini call
returned `permission denied`.

**Root cause:** IAM bindings have eventual consistency; ~5-15 second
propagation lag. The first call landed before the role was active.

**Fix:** Wait 10-15s after `add-iam-policy-binding`, retry. Worked on
second attempt. Saved as a memory note for re-creation playbook.

---

### Model availability varies by region (the silent footgun)

**Symptom:** `gemini-2.0-flash` listed as available but failed; switching
to `gemini-3.1-flash-lite-preview` worked instantly.

**Root cause:** Vertex generally lists model X as "available in the global
endpoint", but the actual regional deployment is more limited than the
docs imply. `-lite-preview` variants are usually deployable on `global`;
older or larger variants require a specific region.

**Fix:** Hardcoded `gemini-2.5-flash` (later confirmed as the project's
working baseline) and verified against Vertex's region availability docs
before assigning each service to a region.

**Trap we hit later:** Pediatrics agent assigned to `asia-east1` returned
404 "Publisher Model … was not found or your project does not have access
to it". Same model name, same project, different region — not deployed there.
Moved pediatrics to `us-east5`. (See `08-hosting-and-quota.md` for the
multi-region map.)

---

### Vertex was wired in code but never actually engaged

**Symptom:** Errors mentioned "Please go to AI Studio at https://ai.studio/projects".
The URL is the giveaway: AI Studio errors point there; Vertex errors point
to `cloud.google.com/vertex-ai`.

**Investigation:** `agents/shared/.../config.py` had a `_materialize_vertex_sa()`
function that materializes `GCP_SA_KEY_JSON` to `/tmp/gcp-sa.json` and sets
`GOOGLE_GENAI_USE_VERTEXAI=true`. **But the deploy script never set
`GCP_SA_KEY_JSON` as an HF Space secret.** The bootstrap was a no-op; agents
fell back to the API key (`GEMINI_API_KEY`) which routed to AI Studio.

**Fix:** Updated `scripts/deploy_hf_spaces.py` to read
`~/.config/gcloud/keys/council-vertex.json`, set as a Space secret named
`GCP_SA_KEY_JSON`, plus added `GOOGLE_CLOUD_PROJECT`,
`GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI=true` as Space
variables. Removed `GEMINI_API_KEY` from common secrets so google-genai
unambiguously prefers the Vertex path.

Also patched the MCP's `gemini.ts` to detect the Vertex envelope, materialize
the JSON to /tmp, and instantiate `GoogleGenAI({ vertexai, project, location })`
instead of `{ apiKey }` when Vertex is configured.

**Why this matters:** Several days of debugging "why is Gemini hitting AI
Studio quota?" pointed at the wrong layer. The runtime config was correct;
the deploy never wired the secret. Memory rule saved: when the error URL
points to a different vendor than you think you're using, the auth path is
the first thing to check.

---

### Vertex 429 on a single region (the hammer-one-region problem)

**Symptom:** All 9 agents wired correctly to Vertex, but bursting 8
specialty fan-out calls in <1s consistently 429'd half of them. Trial-credit
projects have tighter per-region RPM ceilings than the documented 60 RPM.

**Iteration log:**
1. Throttled fan-out concurrency 8 → 4 → 2. Helped marginally but stretched Round 1 from 30s to 90s.
2. Per-peer 429 retry-with-exponential-backoff (3s/6s/12s, then 5s/10s/20s/40s). Caught some 429s but ate budget.
3. Pre-brief 4-second sleep to drain the rolling-minute window. ~5s saved on the brief.
4. **Real fix: spread services across 10 regions.** Same project, same trial credit, ~10× the burst headroom because each region's per-minute quota is independent.

Region map (verified against Vertex AI region availability docs):
```
specialty-lens-mcp  → us-central1
convener            → us-east1
cardiology          → us-west1
oncology            → us-east4
nephrology          → us-south1
endocrine           → europe-west1
obstetrics          → europe-west4
pediatrics          → us-east5     # asia-east1 had a model availability gap
psychiatry          → asia-northeast1
anesthesia          → asia-southeast1
```

---

### Vertex 429 was STILL happening — inside the MCP

**Symptom:** Even with 10 regions on agents, Round 1 yield was poor. Logs
showed half the specialty lens calls 429'd inside the MCP.

**Root cause:** Specialty agents in 10 regions, but they all called ONE
MCP server (us-central1). Inside the MCP, every lens called Gemini in
us-central1. So 8 simultaneous lens-Gemini calls hit the same region's
quota. Per-agent multi-region was insufficient; the MCP itself had to
spread its lens calls.

**Fix:** Inside the MCP, added a `regionForSpecialty(specialty)` resolver
that returns the per-specialty region. Per-region Vertex client cache
(`Map<region, GoogleGenAI>`). Each `runLens()` call passes
`region=regionForSpecialty(spec.specialty)`. Concordance synthesis
routes to its own region (us-central1). Conflict-matrix tool same.

**Result:** Round 1 yield went from 1-2 views to 5-7 in 25-30 seconds.

---

### Vertex daily quota saw a separate cliff

**Late finding:** Even with multi-region helping per-minute, the **daily
TPM (tokens per minute) and RPM aggregate per project** can still cap. We
hit it once during heavy iterative testing (~80 deliberations in a day).
Solution: spaced testing out, set a Cloud Billing budget alert at $50,
moved to scheduled testing during demo prep. Not a blocker but a known
constraint.

---

### Promotional credit appeared mysteriously

**Symptom (panic moment):** User checked billing console; saw
$1,000 "Trial credit for GenAI App Builder" + $298.69 "Free Trial" +
expired $300 "Free Trial". Total ~$1,298 in credits, no clear cause.

**Explanation:**
- Original $300 trial: standard new-account credit, expired April 16.
- $298.69 "Free Trial": Google auto-renewed/upgraded the trial when the
  first one ended (common behavior for accounts showing real usage).
- $1,000 GenAI App Builder credit: auto-promotional when Vertex AI APIs
  were enabled. Google hands these out.

All free promotional. No card charge incurred. Card remains on file
(required for trial signup) but is never touched until an explicit
"upgrade to paid" click is made.

**Outcome:** Set a $50 budget alarm in GCP Billing → confirmed never
exceeded. Migration to Cloud Run estimated at ~$28 total against this
$1,298 buffer.

**Why this matters:** Documenting the credit accounting is part of the
"feasibility" pitch — Tunisia builder with $0 cash, no card, ships a
multi-region multi-agent platform on free promotional credits.
