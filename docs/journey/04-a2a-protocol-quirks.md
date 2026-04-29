# 04 · A2A SDK quirks

The `a2a-sdk` is solid but has a few rough edges around Pydantic
discriminated unions and response parsing. We hit each one.

---

### The Pydantic walker bug — text_len=0 for hours

**Symptom:** Every peer call returned `response_chunks=1` but our parser
extracted `text_len=0` and `view_extracted=False`. Round 1 yielded 0
valid SpecialtyViews despite all 8 specialty agents responding.

**Investigation:** Walked through the parser. `_scan_for_text` recursively
walked dicts and lists looking for a `"text"` key. It also peeked into
common Pydantic attrs: `text`, `parts`, `result`, `artifact`, `content`.

**Root cause:** A2A's `Task` shape:
```
Task
  artifacts: list[Artifact]
    Artifact
      parts: list[Part]
        Part
          root: TextPart | FilePart | DataPart   # Pydantic discriminated union
            TextPart
              kind: "text"
              text: str
```

Our walker peeked at `text/parts/result/artifact/content` but **never
at `.root`** — the discriminated union wrapper. `Part.text` doesn't
exist; you have to drill through `Part.root.text`. The parser silently
failed to find any text on every chunk.

**Fix:** Switched the walker to dump every chunk via `model_dump()`
first, then walk the resulting plain dict:

```python
def _to_plain(obj):
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(x) for x in obj]
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump(mode="json", exclude_none=True)
        except Exception:
            pass
    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return str(obj)
```

`model_dump(mode="json", exclude_none=True)` flattens the discriminated
union — `Part.root` becomes a sub-dict in the output, and we walk that.

**Smoke-tested locally** with three shapes (Pydantic Task, raw dict, empty)
before deploying. All three parse correctly now.

**Why this matters:** Hours of "every peer is silent, why?" debugging
solved by understanding Pydantic's discriminated-union flattening.
`model_dump()` should always be the first move when reading SDK objects;
attribute walking misses union wrappers.

---

### Strict parser — `"specialty"` key required

**Symptom:** Even after the walker fix, some valid SpecialtyView responses
got rejected. They had primary_concerns, proposed_plan, etc. but Gemini
had paraphrased and dropped the `"specialty"` key from the dict.

**Fix:** Loosened acceptance to "looks like a SpecialtyView" via
signature-key matching. Any 2 of these → accept:
```python
_SPECIALTY_VIEW_SIGNATURE_KEYS = frozenset({
    "specialty", "primary_concerns", "red_flags", "proposed_plan",
    "applicable_guidelines", "reasoning_trace",
})

def _looks_like_view(parsed):
    return (
        isinstance(parsed, dict)
        and len(_SPECIALTY_VIEW_SIGNATURE_KEYS & parsed.keys()) >= 2
    )
```

---

### LLM wrapping JSON in markdown fences and prose

**Symptom:** Some peer responses came back as:
````
Here is my SpecialtyView:
```json
{"specialty": "cardiology", ...}
```
Let me know if you need clarification.
````

`json.loads()` on that fails immediately.

**Fix:** Three-tier JSON extraction in `_extract_view`:
1. Plain `json.loads(text)` — works if Gemini returned bare JSON
2. Markdown-fence tolerance — find `​`​`json … ​`​`​` block, extract
3. Prose-wrapped tolerance — find largest balanced `{ … }` substring, parse

Each tier checks `_looks_like_view(parsed)` before accepting.

---

### Function-response artifacts in the stream

**Discovery:** ADK's A2A stream carries `function_response` events with
the **raw MCP tool output as a structured dict** before the LLM ever
paraphrases it.

**Optimization:** Our `_scan_for_structured_view` now scans the chunk
stream for those structured dicts first. If the raw MCP output is
present in the stream, we use it directly and bypass the LLM's
paraphrase entirely. Faster, more reliable, no parser ambiguity.

**Why this matters:** When the LLM is just shaping a tool result, the
tool result itself is the truth. Scanning for it first is more reliable
than text-parsing whatever the LLM decided to write.

---

### Patient ID hallucination

**Symptom:** `MCP tool get_council_conflict_matrix failed: views span multiple
patients (1c237c73-0152-4250-…, 1c237c73-0152-4220-…)`.

**Root cause:** Nephrology's LLM transposed a digit in the patient_id
when echoing it in its response (4250 → 4220). The conflict-matrix
safety check correctly rejected views from "different patients."

**Fix:** Force-normalize patient_id in the Convener before passing
views downstream:
```python
view = {**r.structured_view, "patient_id": patient_id}  # canonical wins
```

The caller owns the patient_id; the LLM doesn't get a say in identifiers.

**Why this matters:** Defensive identifier handling. Long UUIDs are
typoed by LLMs occasionally. Anywhere an identifier flows from an LLM
back into a database or safety check, force the canonical value.

---

### Streaming response shape mismatch

**Symptom:** ADK to_a2a-emitted Agent Cards advertised
`capabilities.streaming = true` by default. PO's parser then tried to
parse the response as SSE; PO can't actually parse SSE for external
agents, so it errored.

**Fix:** Hardcoded streaming=false on every Agent Card. Documented in
`agents/shared/tests/test_card_factory.py`:
```python
def test_capabilities_streaming_default_off():
    # streaming=False is required for ADK to_a2a to emit Task events
    # instead of Message events; PO's parser only treats Tasks as valid responses.
    card = make_agent_card(...)
    assert card.capabilities.streaming is False
```

---

### Background task lifetime

**Symptom (architecturally important):** When we shifted to fire-and-forget
deliberation (Convener returns in <5s, deliberation runs in background),
we needed to make sure the background task wasn't garbage-collected
before it finished.

**Fix:** Hold strong references in a module-level set:
```python
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()

task = asyncio.create_task(_run_deliberation(...))
_BACKGROUND_TASKS.add(task)
task.add_done_callback(_BACKGROUND_TASKS.discard)
```

`asyncio.create_task` only weak-refs by default. Without the set, Python
can GC the task mid-run if no other reference exists.

**Why this matters:** Subtle gotcha. If you ever fire-and-forget an
asyncio task, you must hold a reference somewhere. The `add_done_callback`
discards the reference after completion so the set doesn't grow unbounded.
