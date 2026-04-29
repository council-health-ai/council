# 10 · Architectural decisions (locked)

The decisions below are not re-litigated unless the user explicitly
overrides them. Every entry has the call AND the why, so the next
person to look at this knows which choices were principled vs which
were just first-mover.

---

### Peer A2A, never orchestrator-with-router

**Call:** The Convener is a *facilitator*, not a router. It opens the
session, fans out to specialty agents over A2A, collects views,
synthesizes. It does NOT decide which specialty to call (that's the
deterministic 8-peer fan-out) and it does NOT use Gemini to route
between specialties (which would make it a chatroom-with-LLM-router,
i.e. HAO with extra steps).

**Why it matters:** This is the structural differentiator from
Microsoft Healthcare Agent Orchestrator. HAO's pattern is
"orchestrator agent uses Gemini to pick which expert agent to consult
next, in a group-chat-like sequence." The Council's pattern is
"convener fires deterministic parallel A2A fan-out, agents reason in
parallel, conflicts surface from view comparison, brief synthesizes
from the union."

This is what A2A's protocol was designed for — peer-to-peer agents
with their own AgentCards, their own SHARP context, their own model
choices. HAO uses a single orchestrator that holds the conversation
state and calls "specialist tools." The Council's specialists ARE
agents, with their own URLs, their own logging, their own audit trail.

**How not to break this:** If anyone proposes "let's have the Convener
use Gemini to decide which 4 specialties to consult based on the
patient," that's the slip back into orchestrator-with-router. The
correct answer is "fan out to all 8; the four irrelevant ones abstain
gracefully (developmental_pediatrics on a 67yo: 'falls outside my
scope')." The abstention IS clinical signal. The Council preserves
it; the orchestrator pattern would silently skip them.

---

### 8 specialties (not 4 or 12)

**Call:** Eight specialties, hard-coded:
- Cardiology
- Oncology
- Nephrology
- Endocrinology
- Obstetrics & MFM
- Developmental Pediatrics
- Psychiatry
- Anesthesia & Perioperative

**Why this set:** Maps cleanly to the four hand-built demo bundles:

| Patient archetype | Primary specialties involved |
|---|---|
| Mrs. Chen (cardiometabolic-oncology, lumpectomy, 67yo) | Cardiology, Oncology, Nephrology, Endocrinology, Anesthesia |
| Aanya (pediatric Williams syndrome) | Developmental Pediatrics, Cardiology, Endocrinology, Psychiatry |
| Sarah (pregnancy + chronic disease) | Obstetrics, Cardiology, Endocrinology, Nephrology |
| Henderson (geriatric polypharmacy + perioperative) | Anesthesia, Cardiology, Nephrology, Psychiatry |

Every specialty is load-bearing on at least one demo case. None is
filler.

**How not to break this:** Don't add a 9th specialty without a 5th
patient archetype. Don't drop one to "save quota" — the abstention
behavior is part of the demo (you can't call the abstention "elegant"
if there's nothing to abstain from).

---

### 5T framing for the ConcordantPlan

**Call:** Plan rendered in **Template + Table + Task** simultaneously:
- **Template:** Brief (summary, rationale, plan.continue/start/stop/monitor lists, timing notes)
- **Table:** Conflict log (parties, initial positions, resolution, method)
- **Task:** Action items for the primary clinician with explicit owner, due_within, priority

**Why:** PO's platform documentation explicitly references the 5T
framework. Rendering the ConcordantPlan as "all three at once" is a
direct demonstration of platform-native thinking and clinical workflow
fluency.

**How not to break this:** The ConcordantPlan zod schema in
`packages/specialty-lens-mcp/src/concordance/concordance-brief.ts`
enforces the shape. Don't loosen it.

---

### Brief synthesizes the conflict log inline; no separate Round 2 in the demo path

**Call:** Originally:
```
Round 1 (8 fan-out)
  → conflict_matrix MCP call
  → Round 2 fan-out (only specialties with conflicts)
  → brief MCP call
```

Final demo path:
```
Round 1 (8 fan-out, capped at 35-60s)
  → brief MCP call (synthesizes conflicts inline from views)
```

**Why:** The conflict_matrix call added 12s of latency on the critical
path; the Round 2 fan-out rarely fired in PO's 60s budget anyway. The
brief LLM is already prompted to detect conflicts from views directly,
and produces an equivalent `conflict_log` inline.

The full Round-2 flow stays in the codebase as a future-feature flag
— `_run_deliberation` doesn't currently call it but the agent.py
ROUND_2_PROMPT_TEMPLATE is preserved.

**How not to break this:** Re-enabling Round 2 is fine when we have
post-fire-and-forget time budget (e.g. on Cloud Run with no chat
ceiling). It's just disabled in the demo critical path, not deleted.

---

### Audit log is canonical; chat is ephemeral

**Call:** Every Convener step writes a row to `audit_events`. Every
specialty view writes a row to `agent_messages`. Every MCP tool call
writes a row to `mcp_tool_calls`. The plan persists as
`convening_sessions.plan_artifact` JSON.

The PO chat response is a **derived view** of the audit log, not the
source of truth. If chat times out, the plan still exists — fully —
in Supabase, renderable forever.

**Why:** This is the Mandel/MedLog hook. Audit-trail-native multi-agent
systems are what the SMART-on-FHIR community wants. Real audit logs
beat real-time chat for clinical decision support.

**How not to break this:** Don't move state into chat. The plan goes to
the audit table; chat shows a link. (Already documented in
`07-the-60s-ceiling.md` — the fire-and-forget pivot enforces this.)

---

### convene-ui as a separate static surface

**Call:** convene-ui is its own deploy (`council-health-ai/convene-ui`,
HF Static SDK). Pure HTML + JS. Reads from Supabase via the public anon
key (RLS allows anon read on the audit tables; service-role writes only
from the agents).

**Why:** Three independent reasons:
1. Static deploys are free forever (no compute = no concurrent-services
   limit).
2. Read-only spectator surface: judges can share a deliberation URL
   that anyone can open without auth.
3. Architecturally clean: the audit tables are the API; the UI is one
   consumer; the agents are another.

**How not to break this:** Don't make convene-ui require auth or a
backend. The Supabase anon key is sufficient. RLS policies in the
schema enforce it.

---

### LLM provider: Vertex AI (multi-region) for everything

**Call:** All 10 services use Vertex AI's `gemini-2.5-flash` (with
`gemini-2.5-pro` available via `CONVENER_MODEL` env override).

Each service is wired to a distinct Vertex region:

```
specialty-lens-mcp  → us-central1
convener            → us-east1
cardiology          → us-west1
oncology            → us-east4
nephrology          → us-south1
endocrine           → europe-west1
obstetrics          → europe-west4
pediatrics          → us-east5
psychiatry          → asia-northeast1
anesthesia          → asia-southeast1
```

Same project (`firm-plexus-363809`), same trial credit. Per-region
quotas are independent.

The MCP itself routes lens calls to per-specialty regions; concordance
synthesis routes to its own region. Documented in
`02-llm-vendor-saga.md`.

**Why:** All-Gemini routing has a clean narrative for Tripathi (judge
— Vertex DevRel): "all 10 services on Vertex Gemini, distributed
across 10 regions for quota independence, on the $300 GCP trial — A2A
done right at zero cost."

**How not to break this:** When adding a new service, assign a unique
region from the unused pool. The docs at https://cloud.google.com/vertex-ai/generative-ai/docs/learn/locations
list 30+ regions; we use 10. Plenty of headroom.

---

### Hosting: HF Spaces now → Cloud Run for production demo

**Call (current):** All deployed on HF Spaces, with the convene-ui on
HF Static SDK.

**Call (planned):** Migrate the 10 dynamic services to Cloud Run on the
existing GCP project before final demo. convene-ui stays on HF Static.

**Why:** HF Spaces hit the concurrent-services soft cap during heavy
testing. Cloud Run on the existing $300 trial costs ~$28 over the
4-week judging window. Cleaner Vertex auth (native runtime SA, no
key materialization). Snappier cold starts.

**How not to break this:** When migrating, keep convene-ui on HF Static
(zero compute = free forever). Don't migrate the static UI to Cloud
Run — it'd cost requests-per-month against the free tier for no
benefit.
