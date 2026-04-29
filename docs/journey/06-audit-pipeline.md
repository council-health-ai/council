# 06 · The audit pipeline silent-failure war

The audit log is the Mandel/MedLog hook — every reasoning step queryable,
streamed to the live demo via Supabase Realtime. It became the
architectural differentiator. It also took several hours of head-scratching
to get the inserts to actually land.

---

### The silent FK rejection

**Symptom:** Hours of debugging "why is Round 1 yielding 0 valid SpecialtyViews?"
ended with one query against Supabase:

```sql
SELECT * FROM audit_events;       -- 0 rows
SELECT * FROM agent_messages;     -- 0 rows
SELECT * FROM mcp_tool_calls;     -- 0 rows
```

The audit log was empty for **every run**. Convener was firing
`record_audit_event(...)`, `record_agent_message(...)`, etc. and the
calls weren't raising. We just had no data.

**Investigation:** Inspected the schema:

```sql
create table public.agent_messages (
  id uuid primary key default gen_random_uuid(),
  convening_id uuid not null references public.convening_sessions(id) on delete cascade,
  ...
);
create table public.audit_events (
  id uuid primary key default gen_random_uuid(),
  convening_id uuid references public.convening_sessions(id) on delete cascade,
  ...
);
```

Both tables FK-reference `convening_sessions(id)`. **Convener never
inserted a row into `convening_sessions` first.** It generated a
`convening_id = uuid.uuid4().hex` locally and used that, but no parent
row existed, so every child insert was silently FK-rejected.

The `audit.py` module wrapped each insert in a try/except that logged
the error at WARN level — but the warning was being swallowed by
structlog's default config in production. We had no visibility.

**Fix:** Convener now calls `open_session(...)` at the start of every
deliberation:

```python
convening_id = state.get("convening_id") or await open_session(
    a2a_context_id=a2a_context_id,
    workspace_id=workspace_id,
    patient_id=patient_id,
)
if not convening_id:
    convening_id = uuid.uuid4().hex
    logger.warning("supabase open_session unavailable; running with synthetic convening_id")
```

`open_session` inserts a row into `convening_sessions` and returns the
generated id. All subsequent audit calls FK against a real parent row
and succeed.

**Also added** `close_session(convening_id, plan_artifact)` at session
end, so the plan is persisted on the session row itself for the convene-ui
to render.

**Why this matters:** Lesson — anytime audit/observability is wrapped in
try/except, surface the error count somewhere visible. We had three layers
of "well it didn't actually break anything" and it took querying Supabase
directly to realize nothing was landing.

---

### Schema role-check tripped on canonical specialty names

**Symptom:** Even after the open_session fix, `agent_messages` inserts
for endocrinology and pediatrics agents were still silently failing.
audit_events landed; agent_messages didn't.

**Investigation:** Original schema had a CHECK constraint on
`agent_messages.role`:

```sql
check (role in (
  'convener', 'cardiology', 'oncology', 'nephrology',
  'endocrine',                 -- ❌ but code sends 'endocrinology'
  'obstetrics',
  'pediatrics',                -- ❌ but code sends 'developmental_pediatrics'
  'psychiatry', 'anesthesia', 'general-chat'
))
```

The code uses the canonical specialty names from `Specialty` literal in
`council_shared/models.py`: `"endocrinology"`, `"developmental_pediatrics"`.
The schema constraint allowed the abbreviated forms. Inserts failed
silently with a CHECK violation.

**Fix:** Migration `20260428010000_relax_audit_constraints.sql` drops
the role check entirely. The code's `Specialty` literal is the source
of truth; SQL-level enforcement adds maintenance friction without
real value.

```sql
alter table public.agent_messages
    drop constraint if exists agent_messages_role_check;
```

**Why this matters:** Schema constraints that diverge from runtime
literals are a footgun. The schema was authored in a separate session
from the runtime literal; nobody reviewed the cross-cut. Documented
the principle: validate at the system boundary (the literal type), not
twice in two places.

---

### Diagnostic logging in `_call_one_peer`

Once the audit log was working, we still needed debug visibility into
peer responses to diagnose parser failures. Added per-peer structured
logging that surfaces:

```python
logger.info(
    "peer response parsed",
    specialty=specialty,
    url=url,
    latency_ms=latency_ms,
    response_chunks=len(responses),
    chunk_types=[type(r).__name__ for r in responses],
    first_chunk_dump=json.dumps(_to_plain(responses[0]), default=str)[:800],
    text_len=(len(text) if text else 0),
    text_preview=(text[:400] if text else None),
    structured_view_specialty=structured.get("specialty") if isinstance(structured, dict) else None,
    structured_view_keys=sorted(structured.keys()) if isinstance(structured, dict) else None,
    view_extracted=structured is not None,
)
```

That `first_chunk_dump` field was the single most useful debugging tool
in the project. It showed us:
- Pydantic discriminated union shapes (drove the model_dump fix)
- LLM-paraphrased responses that dropped the `"specialty"` key
- 429 error envelopes wrapped in MCP tool error responses
- Markdown-fenced JSON

When a parser fails, dumping the full raw chunk + the parse outcome
side-by-side beats every other form of debugging.

---

### Realtime publication

Every meaningful table is in the Supabase Realtime publication:

```sql
alter publication supabase_realtime add table public.audit_events;
alter publication supabase_realtime add table public.mcp_tool_calls;
alter publication supabase_realtime add table public.agent_messages;
```

The convene-ui static page subscribes via supabase-js:

```javascript
supabase.channel(`audit-${sessionId}`)
  .on("postgres_changes", {
    event: "INSERT",
    schema: "public",
    table: "audit_events",
    filter: `convening_id=eq.${sessionId}`
  }, payload => {
    state.events.push(payload.new);
    renderTimeline();
  })
  .subscribe();
```

Same for `agent_messages` (specialty views as they arrive) and
`convening_sessions` (the `plan_artifact` UPDATE when the brief lands).

**Why this matters:** This is the architectural differentiator. Live
multi-agent deliberation playback isn't something you can build with
RAG or with a single orchestrator agent. You need:
- A real audit table with a row per reasoning step
- A pub/sub layer that streams those rows
- A UI that renders them as they arrive

We have all three. The demo of multi-agent reasoning playing out in
real time is what closes the architectural-correctness argument with
the judges.
