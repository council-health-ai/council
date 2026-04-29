# Journey — building The Council for "Agents Assemble"

This folder documents how The Council got built — the decisions, the dead ends,
the regressions, the pivots, and the reasoning behind every load-bearing
architectural choice. It exists for three readers:

1. **Future me** — when something breaks in production six months from now,
   the doc here explains *why* it was built that way.
2. **The judges** — the Devpost "challenges we ran into" prose lives in
   `DEVPOST-CHALLENGES.md`; the rest is the depth-of-engineering evidence behind it.
3. **Anyone forking this repo** — the SHARP RFC, the Vertex multi-region
   approach, the fire-and-forget A2A pattern, and the FHIR fixture fallback
   are all transferable.

## Index

| File | What it covers |
|---|---|
| [00-overview.md](00-overview.md) | The project at a glance: what it is, what won, what was hard |
| [01-setup-and-infrastructure.md](01-setup-and-infrastructure.md) | Account creation, MCP installs, GitHub auth, Claude Code multi-machine sync |
| [02-llm-vendor-saga.md](02-llm-vendor-saga.md) | Free tier → AI Studio prepayment depletion → Vertex multi-region quota distribution |
| [03-po-platform-compatibility.md](03-po-platform-compatibility.md) | Every shape mismatch between PO and the a2a-sdk we had to bridge |
| [04-a2a-protocol-quirks.md](04-a2a-protocol-quirks.md) | Pydantic discriminated unions, streaming flags, response parsing |
| [05-fhir-and-sharp.md](05-fhir-and-sharp.md) | Empty-bearer-token regression, FHIR fixture fallback, RFC PR upstream |
| [06-audit-pipeline.md](06-audit-pipeline.md) | Silent Supabase FK failures, schema-vs-code drift, role-check constraints |
| [07-the-60s-ceiling.md](07-the-60s-ceiling.md) | The General Chat timeout battle that ended with fire-and-forget |
| [08-hosting-and-quota.md](08-hosting-and-quota.md) | HF Spaces null quota → Cloud Run migration on the GCP trial |
| [09-process-and-strategic.md](09-process-and-strategic.md) | Strategic doc leak to public repo, AI co-author trailer, demo dialogue clinical review |
| [10-architectural-decisions.md](10-architectural-decisions.md) | Locked-in calls: peer A2A vs orchestrator, 5T framing, Mandel framing |
| [DEVPOST-CHALLENGES.md](DEVPOST-CHALLENGES.md) | Devpost "Challenges we ran into" — submission-ready prose |

## How to read this

Each file is self-contained. Each documented episode has the same structure:

```
### Title
**Symptom:** what we observed breaking
**Root cause:** why it was actually broken
**Fix:** what we did
**Why this matters:** the architectural / clinical / strategic implication
```

The Devpost prose pulls from these but condenses; the docs here are the
encyclopedia, the prose is the trailer.
