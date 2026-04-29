# 01 · Setup and infrastructure

The first 24-48 hours weren't about The Council — they were about getting the
build environment, accounts, MCPs, and credentials into a state where the
project could even start.

---

### Supabase MCP wouldn't connect

**Symptom:** Supabase MCP server failed with `error -32000: Connection closed`.

**Root cause:** Wrong key type. Initial attempts used a Supabase project-level
JWT (anon / service_role keys). The Supabase MCP needs a **Personal Access
Token** (`sbp_…`) to talk to the management API — multi-project scope, not
single-project data plane.

**Fix:** Generated a PAT from the Supabase dashboard, re-added the MCP with
the correct env var binding. Caught and flagged the previously-pasted JWT
keys as compromised; rotated the JWT secret and revoked the service key.

**Why this matters:** Supabase has two completely different auth surfaces
(per-project keys for data, account-level PAT for management) and the MCP
requires the latter. The error message gives you nothing useful — you have
to know.

---

### Claude Code CLI wasn't actually installed

**Symptom:** `claude mcp add …` came back "command not found".

**Root cause:** VS Code extension was installed; the standalone CLI binary
wasn't. They share configuration but the CLI is a separate `npm` install.

**Fix:** `npm install -g @anthropic-ai/claude-code` (v2.1.119), then added
all MCPs at user scope (`~/.claude.json`).

---

### MCP scope confusion (project vs user)

**Symptom:** Sentry MCP installed but didn't show up in other Claude Code
sessions on this machine.

**Root cause:** `claude mcp add` defaults to **project scope** unless `-s user`
is passed. Project scope writes to `.claude/.mcp.json` in cwd; user scope
writes to `~/.claude.json` and is global to the account on this machine.

**Fix:** Uninstalled from project scope, re-added with `-s user`. Sentry
and Cloudflare then needed OAuth flows via the `/mcp` slash command.

**Why this matters:** Worth documenting because we hit this twice — once
for Sentry, once for Supabase — before recognizing the pattern.

---

### MCP discovery is genuinely hard

**Symptom:** Asked for "ngrok MCP", "Discord MCP", "Google Cloud MCP".
Half were ambiguous, half didn't exist.

**Reality:**
- ngrok is infrastructure (no standalone MCP).
- Discord has community MCPs of varying quality + the official Channels feature.
- Google has narrow official MCPs (Cloud Run, Firebase, BigQuery) but no umbrella "GCP MCP" — `gcloud` via Bash is the actual right call for full GCP access.

**Fix:** Installed Cloudflare + Sentry + Supabase + Hugging Face MCPs
selectively. Used `gcloud` via Bash for everything GCP. Used `gh` via Bash
for everything GitHub.

**Why this matters:** Listing what we *didn't* install is part of the story
— the toolchain is intentionally minimal so the build stays portable.

---

### GitHub auth: SSH keys vs gh credential helper

**Symptom:** `git push` failed with `SSH publickey denied` even though
`gh repo create` worked fine.

**Root cause:** `gh` uses a stored OAuth token; bare `git` over SSH uses
agent-loaded keys. The SSH key on this machine ("macbook-20260423") wasn't
authorized on the GitHub account.

**Fix:** Configured git to use `gh` as a credential helper:
```bash
gh auth setup-git
```
Now `git push` uses the OAuth token. No SSH config maintenance.

---

### Multi-machine Claude Code sessions wouldn't sync

**Symptom:** User has two Macs (work + personal); two separate Claude Code
accounts; sessions, project memory, and MCPs not synced across machines.

**Root cause:** Native Claude sync is account-scoped — different accounts
can't merge.

**Fix:** Built `claude-sync/` — a git-based atomic sync system with these
commands: `claude-push`, `claude-pull`, `claude-sync`, `claude-status`,
`claude-doctor`, `claude-snapshots`, plus `bootstrap.sh` for new machines.

Internal challenges encountered while building it:
- `info` logging contaminated stdout, breaking `resolve_remote_url` capture
  → redirected logging to stderr.
- "Repo already exists" not handled → added existence check.
- SSH key not authorized on the account → switched to HTTPS via gh helper.
- `doctor` had wrong grep pattern for alias detection → fixed pattern.
- Built: symlink resolver, snapshot system, conflict detector, idempotent
  bootstrap, health audit with remediation hints, Keychain credential
  export/import (with fallback for device-bound creds).

**Outcome:** Fully operational sync. Push from one machine, pull on the other.

**Why this matters:** Side project that became load-bearing — without it
the hackathon work would have been spread across two machines with no
shared state. Documented separately at `claude-sync/README.md`.

---

### Hosting: card-free options narrowed quickly

**Constraint (binding):** Tunisia-resident builder, $0 cash budget, no
international credit card.

**Survey (April 2026):**

| Service | Card required? | Free tier sufficient? | Result |
|---|---|---|---|
| Cloud Run / Render / Fly.io / Railway / Heroku | **Yes** | — | Out |
| AWS / DigitalOcean | **Yes** | — | Out |
| Vercel / Netlify | No | Serverless 10-60s timeout, can't host long-lived agents | Bad fit |
| Cloudflare Workers | No | Python via Pyodide can't run google-adk | Bad fit |
| **Hugging Face Spaces (Docker)** | **No** | 16GB RAM, 2 vCPU, public HTTPS | **Selected** |

**Selected:** HF Spaces with Docker SDK, all under one org `council-health-ai`.
URL pattern: `https://council-health-ai-<service>.hf.space`. Sleep-prevention
via a GitHub Actions cron pinging `/healthz` every 6 hours.

(Later — see `08-hosting-and-quota.md` — we hit the free-tier concurrent-services
ceiling and migrated to Cloud Run on the GCP trial. The user's GCP project is
linked to a $300 free trial credit + $1,000 GenAI promotional credit, neither
of which charges the card on file unless explicitly upgraded out of trial.)

---

### Domain: skipped initially, available as rescue path

**Decision:** No custom domain at MVP. `council-health-ai-cardiology.hf.space`
reads as a real org+project to anyone who knows HF. Saves $11/year and one
DNS configuration step.

**Rescue path documented:** if a Tunisian Carte Technologique becomes
available, register `convene.health`, point CNAMEs at HF Spaces or Cloud Run.
Not blocking.

---

### Sentry: 1 project from MCP, 2 projects needed

**Symptom:** Sentry MCP can list/read projects but can't create them.

**Fix:** User created the second project (`council-agents`, Python platform)
manually via the Sentry UI. The MCP-created project (`council-health`,
Node) was used for the TypeScript MCP server. Two DSNs in `.env.local`,
two SENTRY_DSN_* env vars in deploys.

**Why this matters:** Read-only MCPs are a real category — knowing the
boundary up front saves time hunting for a "create project" tool that
isn't there.
