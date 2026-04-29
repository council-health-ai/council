# 08 · Hosting and quota

How we landed on Hugging Face Spaces, hit the concurrent-services
ceiling, and migrated to Cloud Run on the existing GCP trial credit.

---

### Why HF Spaces in the first place

Constraint: Tunisia, $0 cash, no international credit card. Most modern
PaaS services (Render, Railway, Fly.io, Cloud Run, AWS, DigitalOcean)
require a card on file.

Survey landed on Hugging Face Spaces with Docker SDK:
- Free tier: 16GB RAM, 2 vCPU, public HTTPS
- No card to deploy
- Multi-Space org → one logical project across many services
- Naming convention reads as a real org+project to ML judges

10 services deployed under `council-health-ai/*`:
- specialty-lens-mcp
- convener
- 8 specialty agents
- convene-ui (static)

URLs: `https://council-health-ai-<service>.hf.space`. Sleep prevention
via GitHub Actions cron pinging `/healthz` every 6 hours. Free for
public repos.

---

### Build-time gotcha: node:22-alpine UID 1000 collision

**Symptom:** First deploy of the MCP TypeScript Space failed at
`COPY --chown=user:user`.

**Root cause:** `node:22-alpine` already ships a user named `node`
with UID/GID 1000. HF Spaces also runs as UID 1000. Trying to create
a new `user` with UID 1000 collides with the existing `node` user.

**Fix:** Use the existing `node` user. Final Dockerfile:

```dockerfile
FROM node:22-alpine
USER node
ENV HOME=/home/node \
    NODE_ENV=production \
    PORT=7860
WORKDIR $HOME/app
COPY --chown=node:node package.json ./
RUN npm install --omit=dev --no-package-lock --no-audit --no-fund \
    && npm install --no-save --no-package-lock --no-audit --no-fund tsx@4.19.2 typescript@5.7.2
COPY --chown=node:node tsconfig.json ./
COPY --chown=node:node src/ ./src/
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO- http://127.0.0.1:7860/healthz || exit 1
CMD ["npx", "tsx", "src/index.ts"]
```

Same pattern for the 9 Python ADK Spaces.

---

### convene-ui Static SDK (zero compute, free forever)

**Decision:** convene-ui is just HTML + JS subscribing to Supabase
Realtime. No need for a Docker container; HF Static SDK is free,
dead simple, perfect.

**Gotcha:** Static SDK serves on `*.static.hf.space` not `*.hf.space`.
The URL pattern is `https://council-health-ai-convene-ui.static.hf.space/`,
which redirects from root to `/index.html`.

**Cleanup:** Added `history.replaceState` so the rendered URL doesn't
show `/index.html`:
```javascript
if (window.location.pathname.endsWith("/index.html")) {
  const cleanPath = window.location.pathname.slice(0, -"/index.html".length) || "/";
  history.replaceState(null, "", cleanPath + window.location.search + window.location.hash);
}
```

---

### The HF concurrent-services ceiling — "null quota"

**Symptom:** After ~10 deploys in a session, restarting paused Spaces
returned:

```
403 Forbidden: You've reached your null quota limit, please upgrade
your account, or pause your previous Spaces to restart this one.
```

**Investigation:** HF free-tier doesn't document a hard concurrent-Space
limit. The "null quota" is a soft cap on aggregate CPU-time across the
account — heavy iterative testing (we'd done ~50 deploys + many warm
calls) tripped it.

**Workaround (working but limiting):** Pause 4 less-relevant specialty
agents for any given demo (the four that abstain on Mrs. Chen — obstetrics,
pediatrics, psychiatry, anesthesia). Run the 6 critical: convener, MCP,
cardiology, oncology, nephrology, endocrinology. For different patients
(Aanya, Sarah, Henderson) rotate which 4 are paused.

**This was the moment we decided to migrate to Cloud Run.**

---

### Cloud Run cost analysis (April 2026 pricing)

**Free tier per month:**
- 2,000,000 requests
- 360,000 GB-seconds memory
- 180,000 vCPU-seconds compute
- 1 GB egress

**Per-unit charges after free tier:**
- vCPU-second: $0.0000240
- GiB-second: $0.0000025
- Request: $0.40 / million

**Realistic usage (April 29 → May 27 = 28 days):**

```
Demo + judging traffic: ~10 deliberations/day × 28 days = 280 total
Each deliberation: ~10 services × ~30s vCPU each = 300 vCPU-sec
Total: 280 × 300 = 84,000 vCPU-sec/month

Free tier: 180,000 vCPU-sec/month
Status: under free tier → $0 cost
```

**Convener with min_instances=1 (always warm for snappy chat):**
```
1 service × 0.5 vCPU × 86,400 sec × 28 days = 1,209,600 vCPU-sec billable
Minus 180,000 free = 1,029,600 vCPU-sec billable
× $0.0000240 = $24.71
+ memory: 0.5 GiB × 86,400 × 28 × $0.0000025 = $3.02
Total: ~$28 for 28 days
```

**All 10 with min_instances=1 (zero cold start anywhere):**
```
~$610/month → trial dies day 14
NOT recommended
```

**Selected config:** Convener `min_instances=1`. Other 9 services
scale-to-zero. Estimated cost: ~$28 of $300 trial. $272 buffer.

---

### Mysterious credits in the GCP billing console

User panicked when the billing console showed:
- $1,000 "Trial credit for GenAI App Builder" (Apr 28 - Apr 28 2027)
- $298.69 "Free Trial" (Apr 16 - Jul 12)
- $300 "Free Trial" expired Apr 16

**None of this is owed money.** All three are Google promotional credits:
- Original $300 trial: standard new-account credit
- $298.69: Google auto-renewed when the first trial ended (common for accounts showing real Vertex usage)
- $1,000 GenAI: auto-promotional when Vertex AI APIs were enabled

Total free credit pool: ~$1,298. Migration cost: ~$28.
Buffer after migration: $1,270.

**Safety net:** Set a $50 budget alarm in GCP Billing →
`firm-plexus-363809` → Budgets. If anything exceeds $50, email
notification fires immediately.

---

### Migration strategy (~5 hours of work)

1. **Enable APIs:** Cloud Run + Artifact Registry + Cloud Build on the
   project (one-time gcloud commands).
2. **Build images:** Cloud Build trigger from the same Dockerfiles.
   Pushed to `gcr.io/firm-plexus-363809/<service>`.
3. **Deploy each service:** `gcloud run deploy` with:
   - `--image gcr.io/.../<service>:latest`
   - `--region <per-service-region>`
   - `--service-account council-vertex@…`
   - `--min-instances 1` for Convener, `0` for others
   - `--max-instances 5`
   - `--memory 1Gi --cpu 1`
   - `--allow-unauthenticated`
   - `--set-env-vars …`
4. **Update env vars:** Agent URLs in the Convener's PEER_URLS env vars
   become `https://<service>-<hash>-<region>.a.run.app` instead of
   `*.hf.space`.
5. **Update PO External Agent registration:** One-time UI step in PO
   to point Convener at the Cloud Run URL.
6. **convene-ui stays on HF Static** — it's just HTML, no compute cost,
   free tier handles it.

**Bonus simplification:** Cloud Run runs WITH the service account
attached natively. No more `GCP_SA_KEY_JSON` materializing to /tmp.
Cleaner architecture story.

---

### Architectural lift from migration

| Aspect | HF Spaces | Cloud Run |
|---|---|---|
| Concurrent services | Soft cap (~6 free tier) | Unlimited (within free tier $0) |
| Cold start | 30s+ on idle Space | 1-3s on warm container |
| Vertex auth | SA key materialized to /tmp | Native runtime SA, no key file |
| Cost | $0 (free tier) | ~$28 for 28 days from $300 trial |
| Scale-to-zero | No | Yes |
| Custom domains | Pro tier ($9/mo card) | Free + free TLS |

The "production-grade Cloud Run with multi-region quota distribution"
story is also a cleaner pitch to judges than "Hugging Face Spaces".
