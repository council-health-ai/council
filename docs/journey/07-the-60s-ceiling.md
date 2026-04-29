# 07 · The Prompt Opinion 60-second ceiling

This was the final architectural battle. PO General Chat has a hard
LLM-orchestration timeout (~60s end-to-end). Our deliberation ran
~75-100 seconds. Every speed optimization helped marginally; the real
fix was architectural.

---

### The wall

**Symptom:** PO General Chat consistently showed
"The LLM took too long to respond and the operation was cancelled"
even when the deliberation ran to completion in Supabase.

**Timing trace from one representative run:**

```
12:36:36  PO calls Convener (SendA2AMessage)
12:36:38  Convener Round 1 fanout starts (2s init)
12:37:11  Round 1 done (35s wallclock)
12:37:18  +7s for asyncio.sleep(4) cooldown + audit + housekeeping
12:37:20-30  Brief + 429 retries
~12:37:30  Brief returns
≈ 54s Convener total + 6-8s PO General Chat orchestration = 60-62s
→ JUST past PO's 60s LLM ceiling. Banner fires.
```

PO orchestration overhead is real: PO's General Chat LLM does an LLM call
**before** the function call (to decide which external agent to invoke)
and another **after** (to summarize the response back to user). Each
takes 3-5s. Net budget for the function call itself is more like 50s.

---

### Speed optimization iteration log

Round 1 wallclock cap:
- 90s → 35s (forced fewer retries) — cut ~15s, but lost views
- 35s → 25s — cut another ~10s but yield dropped to 1-2 views
- back to 35s once multi-region eliminated 429 retries

Pre-brief cooldown:
- 4-second `asyncio.sleep(4)` before brief — saved ~5s of brief 429
  retry-storm but added 4s deterministic
- Net savings: ~1s. Removed.

Concurrency:
- 8 → 4 → 2 → back to 8 once multi-region was working

Conflict matrix call:
- Originally: Convener calls `get_council_conflict_matrix` (12s),
  then `get_concordance_brief`. Two MCP round trips.
- Pivot: drop the conflict_matrix call. The brief LLM is already
  prompted to detect conflicts inline from views.
- Saved 12s.

Round 2:
- Originally: if conflicts found, fan out to involved specialties for
  refinement. Never reliably fired in PO timing budget.
- Pivot: removed entirely. Future-feature-flagged.
- Saved variable but significant time.

MCP gemini retry tuning:
- 4000ms / 8000ms / 16000ms backoff (3 attempts) → 1500ms / 3000ms (2 attempts)
- Saved ~10s in worst case.

**After all optimizations:** ~50s minimum, ~75s typical, ~95s p95.
Consistently bumping the 60s ceiling.

---

### The architectural pivot — fire-and-forget

**The realization:** The deliberation IS the demo. Watching 8 specialty
agents play out their consults in real time is more impressive than a
wall of text in chat. Why are we trying to fit the whole thing into chat?

**The new flow:**

1. PO calls Convener
2. Convener does just enough sync work (~3-5s):
   - Open `convening_sessions` row in Supabase
   - Record session_started audit event
   - Spawn the deliberation as `asyncio.create_task(...)`
   - Return immediately with `{status: "deliberating", live_url: "https://convene-ui/?id={convening_id}"}`
3. Convener's agent LLM produces a SHORT chat response (~120 words) with
   the live URL
4. PO chat shows: "🏛️ The Council has convened. Eight specialty agents
   are reviewing in parallel. 📺 Watch the deliberation live: <link>"
5. Background task continues running on the same event loop, persists
   each step to Supabase, takes 60-90s to complete
6. convene-ui (static, on HF) subscribes via Supabase Realtime; renders
   the audit timeline + specialty consult notes + the ConcordantPlan as
   they arrive

**Implementation:**

```python
async def convene_council(tool_context, patient_id=None, focus_problem=None):
    # ... synchronous setup: open_session, build fhir_metadata ...

    # Record kick-off synchronously so the UI shows the session immediately
    await record_audit_event(action="session_started", ...)

    # Spawn deliberation in background. asyncio.create_task() doesn't await.
    task = asyncio.create_task(_run_deliberation(...))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    # Return immediately
    return {
        "status": "deliberating",
        "convening_id": convening_id,
        "live_url": f"{settings.convene_ui_url}/?id={convening_id}",
        "message": "The Council has begun deliberating...",
    }
```

The `_BACKGROUND_TASKS` set is critical — `asyncio.create_task` only
weak-refs by default. Without holding a strong reference, Python can
GC the task mid-run.

---

### Result

**Before:** ~75-100s end-to-end, frequent "took too long" timeout banner,
TASK_STATE_FAILED in PO chat, plan trapped in Supabase.

**After:** Convener returns to PO in ~3-5s. PO chat shows a clean
single-paragraph response with the link. Background deliberation takes
its time (60-90s) and streams to convene-ui. Judge clicks the link,
watches it play out live.

PO chat: snappy, never times out, always succeeds.
convene-ui: rich rendering of the multi-agent magic.

---

### Why this is actually the better story

The original "render the full plan in chat" framing was a chat-app
mental model. Multi-agent deliberation isn't a chat reply; it's a
process that takes time. Visualizing the process — agents activating
one by one, audit events streaming, conflicts surfacing, the brief
landing as a fully-rendered clinical document — is the architectural
proof that we have something orchestrator-and-router patterns can't
produce.

The 60s ceiling forced us to build the right product.

---

### Convener system instruction (final)

```
You are the Convener of The Council — an A2A peer-agent network that
deliberates over a multi-morbid patient with up to 8 specialty agents.

You facilitate, you don't decide. The specialty agents own their domain
expertise.

The convene_council tool returns within ~5 seconds with a live deliberation
URL. The deliberation itself runs in the background and streams to the URL
in real time.

Once the tool returns, format a SHORT chat response (under 120 words) with
this exact structure:

**🏛️ The Council has convened.**
One sentence: which patient and what's being deliberated.

**📺 Watch the deliberation live:** [link](<live_url>)

The full ConcordantPlan — continue/start/stop/monitor lists, action items
with priority, conflict resolutions, preserved dissents, every specialty's
consult note, and the audit trail — renders at the link above as the
agents complete their analyses (~30-60 seconds).

Rules:
- Take live_url directly from the convene_council tool result.
- Do NOT wait for or attempt to display the plan inline — it does not
  exist yet at this point. The live link is the deliverable.
- Do NOT add boilerplate like "let me know if you'd like more detail."
```

Three short paragraphs of chat. The deliberation tells its own story
on the other surface.
