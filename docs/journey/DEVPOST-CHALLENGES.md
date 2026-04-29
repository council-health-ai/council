# Devpost · "Challenges we ran into" — submission-ready prose

Six paragraphs grouped thematically, ~700 words total, written for
the Devpost submission form. Each maps to material in the journey
docs (00-overview through 10-architectural-decisions) for judges who
follow the GitHub link.

---

## 1. Getting Vertex AI to actually consume the $300 trial

The first 48 hours weren't about The Council — they were about
finding an LLM provider we could afford. We ran through eight Gemini
API keys (mix of free-tier and paid prepayment), all returning
`429 RESOURCE_EXHAUSTED`. Free Gemini Flash on AI Studio caps at
~20 requests/day per key; eight specialty agents in parallel exhaust
that on the first deliberation. The breakthrough came from a Vertex
DevRel comment on Reddit: **AI Studio API keys do not consume the
$300 GCP trial credit. Only Vertex AI service-account JSON does.**
Spent the next morning provisioning a service account, hitting an IAM
propagation race condition (role binding takes ~10 seconds to
activate), discovering that `gemini-2.0-flash` is region-restricted
even though the global endpoint advertises it, and finally landing
on `gemini-2.5-flash` via Vertex SA. Even with that working, the
trial-credit project's per-region RPM ceiling is much tighter than
Vertex's documented 60 RPM, so bursting eight specialty fan-out calls
in <1 second still 429'd half of them. The fix: spread services
across **10 different Vertex regions** (us-central1, us-east1, us-west1,
us-east4, us-south1, europe-west1, europe-west4, us-east5,
asia-northeast1, asia-southeast1). Same project, same trial credit,
~10× the burst headroom because per-region quotas are independent.

## 2. The Prompt Opinion / a2a-sdk shape mismatches

PO is a young platform with its own Agent Card schema; the canonical
`a2a-sdk` is the reference. We hit six distinct shape gaps in
production: PO requires the v1 nested-key `securitySchemes` shape with
`location` instead of `in`; PO sends proto-style PascalCase JSON-RPC
method names (`SendMessage`) where the SDK only registers the spec
form (`message/send`); PO sends `ROLE_USER` where the SDK expects
`user`; PO puts FHIR context at `params.message.metadata` where the
SHARP spec puts it at `params.metadata`; PO's response parser expects
the v1-nested `result.task.{...}` envelope with state as
`TASK_STATE_COMPLETED`, where the SDK emits the spec form
`result.kind:"task"` with state as `completed`; and ADK-emitted Agent
Cards default to `streaming: true`, which makes the platform try to
parse SSE and fail. The fix is a Starlette middleware
(`A2APlatformBridgeMiddleware`) that does method aliasing, role
aliasing, FHIR-metadata bridging, and response reshaping on the way
in and out. Subtle wrinkle: the response reshape can only happen on
the agent PO calls directly (the Convener); applying it to peer-to-peer
calls between Convener and specialty agents breaks the canonical
SDK on the receiving side. The middleware takes a `reshape_response`
toggle: True for the Convener, False for the 8 specialty agents.

## 3. The Pydantic discriminated-union bug — text_len=0 for hours

Every specialty peer was responding with `response_chunks=1` but our
Convener's parser reported `text_len=0` and dropped every view. The
deliberation looked completely broken. The root cause turned out to
be the A2A `Task` shape:
`Task.artifacts[0].parts[0].root.text` — `Part` is a Pydantic
discriminated union over `TextPart | FilePart | DataPart`, with the
real content under `.root`. Our recursive walker peeked at attrs
named `text/parts/result/artifact/content` but never `.root`, so it
silently failed to find any text on every chunk. The fix: dump every
chunk via `model_dump(mode="json", exclude_none=True)` first to flatten
the discriminated union into a plain dict, then walk that.
Smoke-tested with three response shapes (Pydantic Task, raw dict,
empty stream) before redeploying.

## 4. PO's empty-bearer-token regression on the FHIR proxy

PO's General Chat platform started shipping the SHARP fhirToken header
as an empty string instead of a SMART bearer token. Our SHARP middleware
initially rejected (treating empty-string as missing); we relaxed it
to allow present-but-empty. The context extractor one layer down still
rejected the empty token via `if (!fhirAccessToken) return null`
(JS empty-string is falsy); we relaxed that too. With both fixes,
the lens MCP attempted the FHIR call — and got HTTP 403 from PO's
workspace FHIR proxy because that endpoint requires the operating
user's session cookie, not a bearer. Service-to-service callers
without a workspace API key cannot reach it. Rather than baking
ephemeral cookies into the deploy, we built a FHIR fixture fallback:
the MCP ships our four hand-crafted demo bundles (Mrs. Chen, Aanya,
Sarah, Henderson) and falls back to the most multi-morbid bundle
(`mrs-chen.json`) when any 401/403/404/timeout occurs on the live
FHIR call. The fallback is logged at WARN level and the audit trail
flags "demo bundle fallback engaged" so a clinician reviewer always
knows whether the lens saw live or fixture data.

## 5. The audit log silent-FK failure

Hours of debugging "why is Round 1 yielding 0 valid SpecialtyViews?"
ended with one query against Supabase: `SELECT * FROM audit_events`
returned zero rows. Same for `agent_messages`, `mcp_tool_calls`. The
Convener was firing `record_audit_event(...)` and the calls weren't
raising, but **nothing was landing**. Both child tables FK-reference
`convening_sessions(id)` — and the Convener never inserted a row into
`convening_sessions` first. Every child insert was silently FK-rejected.
The `audit.py` module wrapped each insert in a try/except logging at
WARN, but production structlog config swallowed it, leaving us blind.
Fixed by calling `open_session(...)` synchronously at the start of
every deliberation, returning the canonical session UUID, and caching
it on `tool_context.state`. Also caught: SQL CHECK constraint on
`agent_messages.role` allowed `'endocrine'` but the code's `Specialty`
literal sends `'endocrinology'` — silent CHECK violation on every
endocrinology message. Fix: dropped the role-check constraint
(the literal type is the source of truth, SQL-level enforcement was
adding silent failure surface without value).

## 6. The 60-second General Chat ceiling — accepting it as a feature

The final architectural pivot was the cleanest: we couldn't fit a real
multi-agent deliberation (8 specialty fan-out + brief synthesis,
typically 60-90 seconds) inside Prompt Opinion General Chat's ~60s
LLM-orchestration timeout. Every speed optimization helped marginally
— dropping the conflict_matrix MCP call saved 12s, moving from 4 to
8 concurrency saved 5s, multi-region eliminated 429 retry storms —
but we kept bumping the wall. The breakthrough was accepting the
ceiling as a platform constraint and inverting the deliverable: the
Convener now returns within ~3-5 seconds with a **live deliberation
URL**, and the actual deliberation runs in a background `asyncio.create_task`
that streams audit events to Supabase Realtime. A separate static page
(`convene-ui`) subscribes via Realtime and renders the multi-agent
deliberation as it plays out — specialty agents activating one by one,
audit events streaming, the ConcordantPlan landing as a fully-formatted
clinical document with continue/start/stop/monitor cards, action items,
and preserved dissents. The PO chat surface stays snappy and never
times out; the rich rendering happens at convene-ui where it has its
own time budget. This turned out to be the better demo anyway:
**watching eight agents deliberate in real time IS the architectural
proof** that we have something orchestrator-and-router patterns can't
produce. The 60s ceiling forced us to build the right product.
