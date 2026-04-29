# 03 · Prompt Opinion platform compatibility

PO is a young platform; the canonical `a2a-sdk` is the reference
implementation. Several spec/impl gaps showed up in production. We
solved each one with middleware, Pydantic subclasses, or response
reshaping. The compatibility layer lives at
`agents/shared/src/council_shared/middleware.py`
(`A2APlatformBridgeMiddleware`).

---

### Agent Card missing `supportedInterfaces`

**Symptom:** PO refused the agent registration with a JSON parse error
that mentioned `supportedInterfaces` was required.

**Root cause:** PO parses the **A2A v1** Agent Card schema. The current
`a2a-sdk` (v0.3.x) emits the v0 schema by default, which doesn't include
`supportedInterfaces`.

**Fix:** Subclassed `AgentCard` as `AgentCardV1` with an explicit
`supported_interfaces: list[…]` field; same for `AgentExtensionV1`.
Lives in `agents/shared/src/council_shared/card_factory.py`. Card is
served at both `/.well-known/agent-card.json` (v1, primary) AND
`/.well-known/agent.json` (v0 backcompat — PO walkthrough video uses
the latter).

---

### `securitySchemes` shape mismatch

**Symptom:** PO showed "no auth required" even though we had configured
a `X-API-Key` security scheme. Calls came in with no header validation.

**Root cause:** PO parses the v1 nested-key shape:
```json
"securitySchemes": {
  "apiKey": {
    "apiKeySecurityScheme": {
      "name": "X-API-Key",
      "location": "Header"
    }
  }
}
```

The a2a-sdk default emits the spec form:
```json
"securitySchemes": {
  "apiKey": {
    "name": "X-API-Key",
    "in": "Header"
  }
}
```

Two distinct issues: the nested `apiKeySecurityScheme` wrapper, and
`location` vs `in` for the header location field.

**Fix:** Patched the card factory to emit the v1 nested-key shape with
`location` (not `in`).

---

### JSON-RPC method name mismatch (-32601 "method not found")

**Symptom:** PO sends method names as `SendMessage`, `SendStreamingMessage`,
`GetTask`, `CancelTask`, `TaskResubscribe`. The a2a-sdk only registers
the spec names: `message/send`, `message/stream`, `tasks/get`,
`tasks/cancel`, `tasks/resubscribe`. Result: every PO call returned
`-32601 method not found`.

**Fix:** Bridge middleware rewrites the method on the way in:

```python
_METHOD_ALIASES = {
    "SendMessage": "message/send",
    "SendStreamingMessage": "message/send",  # downgrade — PO can't parse SSE
    "GetTask": "tasks/get",
    "CancelTask": "tasks/cancel",
    "TaskResubscribe": "tasks/resubscribe",
}
```

`SendStreamingMessage` is intentionally downgraded to `message/send`
because PO's parser can't handle SSE-streamed responses.

---

### Role aliasing (`ROLE_USER` / `ROLE_AGENT`)

**Symptom:** Pydantic validation errors on role values.

**Root cause:** PO sends `ROLE_USER`/`ROLE_AGENT` (proto enum form).
SDK expects lowercase `user`/`agent`.

**Fix:** Walks the request body and rewrites role values in-place:
```python
_ROLE_ALIASES = {"ROLE_USER": "user", "ROLE_AGENT": "agent"}
```

---

### FHIR metadata bridging

**Symptom:** Convener's `before_model_callback` (`extract_fhir_context`)
read `params.metadata` per the SHARP spec; PO put the FHIR context at
`params.message.metadata`. Agents started with no patient context.

**Fix:** Middleware copies `params.message.metadata` up to
`params.metadata` if the latter is absent. Lifts the `fhir-context`
extension key into the right slot regardless of where PO put it.

---

### Response envelope reshape (the "did not respond with a Task" loop)

**Symptom:** PO showed "Agent did not respond with a Task" even when
the SDK returned a valid Task object.

**Root cause:** PO's parser expects the v1-flavored response envelope:
```json
{
  "jsonrpc": "2.0",
  "id": ...,
  "result": {
    "task": {
      "id": ...,
      "contextId": ...,
      "status": {"state": "TASK_STATE_COMPLETED"},
      "artifacts": [{"parts": [{"text": "..."}]}]
    }
  }
}
```

The SDK returns the spec form:
```json
{
  "result": {
    "kind": "task",
    "id": ...,
    "status": {"state": "completed"},
    "artifacts": [{"parts": [{"kind": "text", "text": "..."}]}]
  }
}
```

Differences: `kind: "task"` outer wrapper instead of nested `task` key;
state in lowercase instead of `TASK_STATE_*` enum; `parts[].kind` field
that PO's parser doesn't expect.

**Fix:** `_reshape_to_po_envelope()` translates on the way out. State
mapping table:
```python
_STATE_MAP = {
    "completed": "TASK_STATE_COMPLETED",
    "working": "TASK_STATE_WORKING",
    "submitted": "TASK_STATE_SUBMITTED",
    "input-required": "TASK_STATE_INPUT_REQUIRED",
    "failed": "TASK_STATE_FAILED",
    "canceled": "TASK_STATE_CANCELED",
}
```

`kind` field stripped from artifact parts.

---

### Reshape was too greedy — broke peer A2A

**Symptom:** Convener received Pydantic validation errors when calling
specialty agents (peer-to-peer). The errors mentioned 7 fields rejected.

**Root cause:** All 9 agents had the same middleware, all 9 reshaped
responses to the v1-PO envelope. But Convener uses the canonical
a2a-sdk client to call specialty agents, and the SDK rejects the
v1-PO shape — it expects the spec form.

**Fix:** Added a `reshape_response: bool` parameter to the middleware.
True only on the Convener (which PO calls directly). False on all 8
specialty agents (they're called peer-to-peer by the Convener via SDK
and must return spec form).

```python
class A2APlatformBridgeMiddleware:
    def __init__(self, app, valid_keys=(), reshape_response: bool = True):
        ...
```

`agents/shared/src/council_shared/specialty_app.py` passes
`reshape_response_for_po=False`. Convener's app passes True.

**Why this matters:** The middleware looks like a single-purpose
component; in reality it has two distinct duties (PO-facing translation
vs spec-faithful peer-to-peer). The toggle is the cleanest way to express
that.

---

### `streaming=False` required for ADK to_a2a

**Symptom:** Even with method aliasing in place, PO sometimes saw
Message events instead of Task events and complained.

**Root cause:** ADK's `to_a2a()` emits Message events on streaming-enabled
cards and Task events on streaming-disabled cards. PO's parser only
treats Tasks as valid responses.

**Fix:** Hard-coded `card.capabilities.streaming = False` in the card
factory. Test added to verify:
```python
def test_capabilities_streaming_default_off():
    assert card.capabilities.streaming is False
    assert card.capabilities.push_notifications is False
    assert card.capabilities.state_transition_history is False
```

---

### Schema validation: null vs undefined (Obstetrics)

**Symptom:** Obstetrics MCP rejected calls with
`Invalid arguments: focus_problem expected string, received null`.

**Root cause:** Python ADK serializes optional function args as JSON `null`,
not undefined. zod's `.optional()` rejects null. So the lens MCP refused
the call before any logic ran.

**Fix:** Switched the input shape from `.optional()` to `.nullish()`.
Normalized to `undefined` before passing to `runLens`:
```typescript
const lensInputShape = {
  patient_id: z.string().min(1),
  focus_problem: z.string().nullish(),
};
// ...
const focusProblem = input.focus_problem ?? undefined;
```

---

### Empty `X-API-Key` from PO General Chat

**Symptom:** Some PO General Chat requests came in with `X-API-Key`
header set but empty. Auth middleware rejected with 403.

**Root cause:** Same regression as the empty fhirToken — PO occasionally
sends header keys with empty string values.

**Fix:** API-key middleware allows present-but-empty when no `valid_keys`
are configured (open spaces) and treats present-and-mismatch as 403
(closed spaces). Documented in `middleware.py` docstring.

---

### Tool-name typos from Gemini

**Symptom:** Convener task crashed with
`ValueError: Tool 'conven_council' not found. Available tools: convene_council`.

**Root cause:** Gemini occasionally typoed the tool name. Live-observed
typos: `conven_council`, `consult_council`, `council_consult`.

**Fix:** Registered all typo variants as aliases:
```python
async def conven_council(tool_context, patient_id=None, focus_problem=None):
    return await convene_council(tool_context, patient_id, focus_problem)

async def consult_council(...): ...
async def council_consult(...): ...

# build_agent registers all four
tools=[convene_council, conven_council, consult_council, council_consult]
```

**Why this matters:** Defensive engineering against LLM nondeterminism.
Adding alias wrappers is cheap insurance. Same pattern useful for any
ADK agent whose tool names get LLM-typoed.
