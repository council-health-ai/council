# Devpost submission — The Council

Copy-paste-ready content for the Devpost form. Written to be read in
under 4 minutes by a judge.

---

## Project tagline (140 chars)

> Eight specialty agents. One multi-morbid patient. A peer A2A network that surfaces conflict, preserves dissent, and emits a concordant plan.

---

## Inspiration

60% of Medicare patients live with two or more chronic conditions.
Multi-morbidity drives ~$1.5 trillion of U.S. healthcare spend annually.
And yet most clinical AI tooling assumes you're optimizing one disease
at a time — single-LLM RAG over a guideline corpus, or single-condition
decision support.

The hard problem isn't *retrieving* cardiology guidance, oncology guidance,
or nephrology guidance. It's *reasoning across them when they pull in
different directions*. A 67-year-old woman with new ER+ breast cancer,
paroxysmal AF on apixaban, T2DM with HbA1c 9.2%, and CKD stage 3a is
guided in four different directions simultaneously by four different
specialty literatures. Every recommendation a single specialty would make
is reasonable in isolation. The interaction is where harm happens.

Microsoft's Healthcare Agent Orchestrator showed multi-agent collaboration
worked for cancer tumor boards. The Council generalizes the architecture
to multi-morbidity and inverts the topology: **peer-to-peer A2A, not
orchestrator-with-router**. Eight specialty agents reason in parallel
through their own lens, exchange A2A messages, surface their conflicts
explicitly, and synthesize one concordant plan with preserved dissent.

---

## What it does

A primary-care clinician opens General Chat in Prompt Opinion with a
patient selected and types: *"Convene the Council on this patient."*

What happens next:

1. The **Convener** agent (an A2A peer) opens a convening session, fans
   out a Round-1 prompt over A2A to **eight specialty agents** in
   parallel: Cardiology, Oncology, Nephrology, Endocrinology, Obstetrics
   & MFM, Developmental Pediatrics, Psychiatry, Anesthesia & Perioperative.
2. Each specialty agent calls its **SHARP-on-MCP lens tool**
   (`get_<specialty>_perspective`) on the patient. The MCP server fetches
   the FHIR chart, summarizes it through the specialty's clinical lens
   (current guidelines, dose-adjustment rules, contraindications,
   red flags), and returns a **structured SpecialtyView**: primary
   concerns, red flags, applicable guidelines, proposed plan
   (continue / start / stop / monitor), and reasoning trace.
3. The Convener collects the views, calls the MCP's
   `get_concordance_brief` tool, which **detects conflicts inline** and
   synthesizes a **ConcordantPlan** in the Prompt Opinion 5T framework
   (Template + Table + Task simultaneously) — a plain-English brief,
   a continue/start/stop/monitor plan, an action-item table for the
   primary clinician, a conflict log with explicit resolution methods
   (harmonized / deferred-to-specialty / guideline-aligned /
   patient-preference / unresolved), and **preserved dissents** where
   the Council didn't fully converge.
4. Every reasoning step writes a row to a Supabase audit table with
   Realtime publication enabled. A **live deliberation viewer**
   (`convene-ui`) subscribes via Realtime and renders the multi-agent
   deliberation as it plays out — specialty agents activating one by
   one, audit events streaming, the ConcordantPlan landing as a fully
   formatted clinical document.

The Convener's response in PO chat is intentionally short — a single
paragraph plus a live link. The rich rendering happens at convene-ui
where it has its own time budget.

The Council doesn't decide. The clinician does. The Council surfaces
the trade-offs that single-LLM systems hide.

---

## How we built it

**Two tracks, both shipped:**

- **MCP Superpower:** `specialty-lens-mcp` — a TypeScript SHARP-on-MCP
  server (Express 5 + `@modelcontextprotocol/sdk`) exposing eight
  `get_<specialty>_perspective` tools and two concordance tools
  (`get_council_conflict_matrix`, `get_concordance_brief`). First and
  only SHARP impl with **real HTTP 403 enforcement** at the request
  edge — none of the three reference implementations in
  `prompt-opinion/po-community-mcp` (TypeScript, Python, .NET) do this.
- **A2A Agent:** the Convener + 8 specialty agents — Python, Google ADK,
  served via `to_a2a()`, Agent Cards at both `/.well-known/agent-card.json`
  (v1) and `/.well-known/agent.json` (v0 backcompat).

**Architecture, end-to-end:**

```
   Prompt Opinion General Chat
                │
                │ A2A (SendMessage)
                ▼
   ┌──────────────────────┐
   │   Convener (ADK)     │  fire-and-forget: returns in <5s with live URL
   │   us-east1           │
   └─────────┬────────────┘
             │ asyncio background task
             │
             │  parallel A2A fan-out (8 peers)
             ▼
   ┌─────────────────────────────────────────────────────┐
   │  cardiology · us-west1     │  oncology · us-east4   │
   │  nephrology · us-south1    │  endocrine · europe-w1 │
   │  obstetrics · europe-w4    │  peds · us-east5       │
   │  psychiatry · asia-ne1     │  anesthesia · asia-se1 │
   └─────────┬───────────────────────────────────────────┘
             │ each specialty agent calls
             ▼
   ┌──────────────────────────────────────┐
   │  specialty-lens-mcp · us-central1    │
   │  ┌───────────────────────────────┐   │
   │  │ SHARP middleware (403 enforce)│   │
   │  │ FHIR client (R4, axios)       │   │
   │  │ FHIR fixture fallback         │   │
   │  │ Per-specialty Vertex region   │   │
   │  │ Concordance synthesis (Gemini)│   │
   │  └───────────────────────────────┘   │
   └──────────────────────────────────────┘
             │
             │ writes
             ▼
   ┌──────────────────────────────────────┐
   │  Supabase  (Postgres + Realtime)     │
   │  · audit_events                      │
   │  · agent_messages                    │
   │  · mcp_tool_calls                    │
   │  · convening_sessions (plan_artifact)│
   └─────────┬────────────────────────────┘
             │ Realtime publication
             ▼
   ┌──────────────────────────────────────┐
   │  convene-ui (static, HF / Cloud)     │
   │  Live audit timeline                 │
   │  Specialty consult notes             │
   │  ConcordantPlan (5T render)          │
   └──────────────────────────────────────┘
```

**Why peer A2A, not orchestrator-with-router:** The A2A protocol was
designed for peer-to-peer agents with their own AgentCards, their own
SHARP context, their own model choices, their own audit trails. The
Convener fans out deterministically; it does NOT use Gemini to "decide
which expert to consult next" (that's the orchestrator pattern). Each
specialty agent is a real A2A peer with its own URL, security scheme,
and metadata extension. The abstention from a non-relevant specialty
(e.g., Developmental Pediatrics on a 67-year-old) is itself clinical
signal — preserved in the audit log, not silently skipped.

**Why a real audit log:** Healthcare clinical decision support without
a queryable reasoning trail is unshippable. The audit_events +
agent_messages + mcp_tool_calls tables give a clinician the full
provenance of any recommendation, and Supabase Realtime makes it live
and renderable. The Mandel/MedLog vision — every reasoning step
queryable — is realized here as a first-class architectural feature,
not an afterthought.

**Why an upstream RFC:** We ran into a gap in SHARP-on-MCP — there's
no standardized way to group MCP tool calls into a multi-agent
deliberation session. We proposed a SHARP convening-session extension
(three optional headers: `X-Council-Convening-Id`,
`X-Council-Specialty`, `X-Council-Round-Id`), shipped it as a real
PR to `prompt-opinion/po-community-mcp`, and use it in production
right now to group all of a deliberation's MCP calls under one
session for caching, audit grouping, and per-specialty tool
authorization.

---

## Judging axes

### AI Factor

Reasoning across conflicting specialty guidelines under multi-morbidity
is the canonical agent-not-rule-based problem. Single-LLM RAG over a
guideline corpus produces "what does cardiology say about apixaban
holds?" answers, not "given a 67-year-old with eGFR 38 on apixaban
who needs a lumpectomy in 2 weeks AND has uncontrolled diabetes AND
new ER+ breast cancer pending Oncotype DX, what's the coordinated
pre-operative optimization plan?"

The Council's eight specialty agents reason in parallel, each through
its own clinical lens, with its own applicable-guidelines list and
red-flag rules. Round-1 fan-out is deterministic peer A2A. The
concordance brief detects conflicts inline (e.g., nephrology says
*reduce metformin to 500 mg BID immediately at this eGFR*; endocrinology
says *initiate semaglutide first to maintain glycemic momentum given
HbA1c 9.2%, then reduce metformin*). The brief resolves via temporal
sequencing — both safety boundaries honored, conflict logged, no
silent flattening.

When a specialty's expertise doesn't apply (Developmental Pediatrics
on a 67-year-old, Obstetrics on a postmenopausal woman), the agent
abstains explicitly with reasoning. The abstention is captured in the
audit log; it's clinical signal, not a bug.

### Potential Impact

**$1.5 trillion / year** is the conservatively-estimated U.S. cost of
multi-morbidity-driven care. **60%** of Medicare patients have ≥2
chronic conditions. **Polypharmacy adverse-event rates** scale roughly
with the count of prescribers per patient — the more specialists, the
more cross-prescribing tension goes unsurfaced.

The Council is shippable in any FHIR R4 + SMART workspace today. No
PHI dependency (synthetic Synthea + four hand-crafted demo bundles
ship with the MCP). No vendor lock-in (Vertex Gemini behind google-genai
SDK; swap for AI Studio or another provider with one env var). No
custom storage (Supabase free tier handles audit log; Realtime
publication is a single SQL statement).

The first deployment use case is exactly what the demo shows — a
primary-care clinician using a coordinated pre-operative optimization
plan across cardio + onco + nephro + endo + anesthesia for a complex
elective surgery. That's a high-frequency clinical scenario; current
care typically involves the PCP making sequential phone calls across
specialty offices and stitching the answers together by memory.

### Feasibility

We shipped this on **$0 of personal cash** with **no international
credit card** from Tunisia. Every architectural choice respected those
constraints:

- **Hosting:** Hugging Face Spaces (Docker SDK) for the MVP; migrating
  to Cloud Run on the $300 GCP trial credit (estimated cost ~$28 over
  the 4-week judging window with scale-to-zero on 9 of 10 services).
- **LLM:** Vertex AI Gemini 2.5 Flash via service-account JSON, billed
  to the GCP trial. **10 distinct regions** for quota distribution —
  same project, ~10× burst headroom by spreading services across
  independent per-region RPM pools.
- **State:** Supabase Postgres + Realtime, free tier.
- **Observability:** Sentry developer plan, two projects (Node MCP
  server + Python A2A agents).
- **Domain:** none for MVP; HF subdomains read as real org+project to
  ML-aware judges.

Full FHIR R4 + SHARP-on-MCP compliance. Real 403 enforcement at the
MCP edge (the only impl that does this). Upstream RFC for the
convening-session extension shipped as a real PR. Audit trail with
Realtime streaming. Clinician-facing voice throughout — never
patient-facing diagnosis, always a clinical-decision-support draft brief.

---

## Challenges we ran into

(See [council/docs/journey/DEVPOST-CHALLENGES.md](./journey/DEVPOST-CHALLENGES.md)
in the repo for the full ~700-word challenges section.)

Six thematic battles, in chronological order:

1. **The Vertex trial-credit + multi-region quota saga** — eight dead
   API keys before discovering only the Vertex service-account JSON
   path consumes the $300 trial credit. Then per-region RPM ceilings
   were too tight; spreading 10 services across 10 GCP regions gave
   us 10× the burst headroom.
2. **Prompt Opinion / a2a-sdk shape mismatches** — six distinct shape
   bugs (Agent Card v1 fields, securitySchemes shape, JSON-RPC method
   names, role aliasing, FHIR metadata bridging, response envelope
   reshaping, streaming flag). A Starlette middleware bridges them
   transparently.
3. **The Pydantic discriminated-union walker bug** — every peer
   returned `text_len=0` for hours. `Task.artifacts[0].parts[0].root.text`
   — our walker missed `.root`. Fixed by `model_dump()` flattening
   and walking the plain dict.
4. **Empty-bearer-token regression on PO's FHIR proxy** — service-to-service
   calls returned 403. Built a FHIR fixture fallback that ships
   hand-crafted bundles with the MCP, with explicit audit-log
   attribution so reviewers know whether a lens saw live or fixture data.
5. **Audit log silent FK-rejection** — Convener never opened the parent
   `convening_sessions` row, so all child inserts were silently
   FK-rejected for hours. Fixed by `open_session()` at session start.
6. **The 60-second General Chat ceiling** — every speed optimization
   helped marginally; the architectural fix was inversion: Convener
   returns within ~3-5 seconds with a live URL, deliberation runs in
   a background `asyncio.create_task`, and the rich render happens at
   `convene-ui` over Supabase Realtime. Stronger demo than waiting
   for chat text anyway — watching eight agents deliberate in real
   time IS the architectural proof.

---

## Accomplishments that we're proud of

- **Spec-correctness flex:** SHARP-on-MCP `fhir_context_required` 403
  enforcement at the edge — first impl to do this; documented in
  the upstream RFC PR.
- **Convening-session SHARP extension** — RFC contributed upstream.
- **Multi-region Vertex quota distribution** — same project, ~10×
  burst headroom, generalizable pattern for any multi-agent system on
  trial-credit GCP.
- **Fire-and-forget A2A** — Convener returns the live URL in <5s,
  deliberation runs in background, convene-ui renders the multi-agent
  magic via Supabase Realtime. Stronger demo than chat-text-of-doom.
- **Audit-trail-native design** — every reasoning step queryable;
  Mandel/MedLog vision realized as a first-class architectural feature.
- **5T-framed ConcordantPlan** — Template (brief), Table (conflict
  log), Task (action items) all in one artifact, native to PO's
  framework.
- **Honest about FHIR fallback** — when PO's empty-token regression
  forces us to use bundled patient data, the audit log says so.
  Clinician reviewers always know what the agents saw.

---

## What we learned

- **Production multi-agent on a platform constraint is mostly an
  integration problem, not a modeling problem.** The LLM is the easy
  part. Wiring eight specialty agents into a platform that has its
  own LLM-orchestration timeout, its own auth shape, its own envelope
  format, and its own bearer-token regression is where 80% of the
  engineering goes.
- **The 60-second ceiling forced us to build the right product.**
  Once we accepted PO's ceiling as a platform constraint and stopped
  trying to fit a 90-second deliberation into a chat reply, the whole
  story got better. Live multi-agent deliberation playback IS the
  architectural differentiator. The constraint pushed us to the
  better surface.
- **Free-tier multi-region is a real architectural pattern, not a
  hack.** Same project, same trial credit, ~10× the burst quota by
  spreading services across distinct GCP regions whose per-minute
  quotas are independent.
- **The audit log is the architectural differentiator** in healthcare.
  Without queryable reasoning provenance, multi-agent CDS is unshippable.
  With it, you have something orchestrator-and-router patterns
  fundamentally can't produce.
- **Defensive engineering against LLM nondeterminism is cheap insurance.**
  Tool-name typo aliases. Patient-ID force-normalization. `.nullish()`
  schema fields. Three-tier JSON parsing. Each of these saved a
  deliberation that would otherwise have crashed.

---

## What's next for The Council

- **Round 2 reactivated post-fire-and-forget** — when conflicts surface
  in the brief, fan out a refinement round to involved specialties
  with the conflict context. The code already supports it; we disabled
  it for the demo critical path.
- **More patient archetypes.** The four hand-crafted bundles
  (Mrs. Chen — cardiometabolic-oncology; Aanya — pediatric Williams
  syndrome; Sarah — pregnancy + chronic disease; Henderson — geriatric
  polypharmacy + perioperative) cover the major coordination patterns
  but a clinician's panel has more.
- **Specialty agents as standalone Marketplace listings.** Each of the
  8 specialty agents is independently invocable and listed in the
  Marketplace. A workspace can compose its own council from any subset.
- **Council-authorized scopes via SHARP RFC.** The convening-session
  extension already proposes per-session caching and per-specialty
  tool authorization. Future work: granular scope enforcement at
  the MCP layer per specialty role.
- **Real EHR integration beyond demo.** SMART-on-FHIR launch flow
  (we already advertise the right scopes); a workspace can drop the
  Council in and have it work with their real patient cohort.

---

## Built with

`google-adk` 1.25 · `a2a-sdk` 0.3 · `@modelcontextprotocol/sdk` 1.25 ·
TypeScript 5.7 · Python 3.12 · Express 5 · Starlette · Supabase
(Postgres + Realtime) · Vertex AI (Gemini 2.5 Flash) ·
Hugging Face Spaces · Cloud Run · Cloud Build · Artifact Registry ·
FHIR R4 · SMART-on-FHIR scopes · SHARP-on-MCP · Synthea ·
GitHub Actions · `uv` (Python workspace) · Turborepo (TypeScript) ·
Sentry · `pino` / `structlog`

---

## Try it

- **Live demo:** [convene.health link or HF static URL]
- **Source code:** https://github.com/council-health-ai/council
- **SHARP RFC PR:** [link to the upstream PR]
- **Demo video (3 min):** [link]
- **Architecture deep-dive:** [council/docs/journey/](https://github.com/council-health-ai/council/tree/main/docs/journey) — full chronological documentation of every challenge, pivot, and architectural decision behind the build
