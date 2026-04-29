# End-to-end submission test runbook

Walk through the full submission as a hackathon judge would. Catches the
"wait, this doesn't actually work for somebody who isn't us" failure mode
that's killed many otherwise-strong submissions.

Run this twice:
1. **48 hours before recording the demo video** — gives time to fix anything broken.
2. **Final dry run, morning of submission** — confirms nothing regressed during marketplace publishing or Devpost editing.

---

## Pre-flight (5 min)

- [ ] Pre-warm all 10 services. Each `/healthz` returns 200.
- [ ] Latest Convener deploy includes the fire-and-forget code (background `asyncio.create_task` pattern).
- [ ] Latest MCP deploy includes per-specialty Vertex region routing.
- [ ] Convene-ui static deployment serves at the public URL.
- [ ] Supabase has at least 2 non-current completed sessions accessible via `?id=…`. (Demo backup if a live deliberation fails.)
- [ ] All 10 Marketplace listings are **published** (not draft).
- [ ] Convener External Agent registration in PO points at the current Convener URL.

---

## Test A — judge experience: discovery (15 min)

A judge browsing the Marketplace, not knowing who built what.

1. **Open the Prompt Opinion Marketplace.**
2. **Search for `council`** or browse the agents/MCPs sections.
   - All 10 listings appear: 1 MCP + 1 Convener + 8 specialty agents.
   - Each listing has a clean tagline + screenshots + tags.
3. **Open the Convener listing.**
   - Description reads as a coherent peer-A2A pitch (not orchestrator-with-router).
   - Cross-references to the SHARP-on-MCP listing.
   - "Try it" or invocation flow visible.
4. **Open the specialty-lens-mcp listing.**
   - SHARP-on-MCP framing clear.
   - 8 lens tools + 2 concordance tools listed.
   - Mention of real 403 enforcement + RFC PR is visible.
5. **Open one specialty agent listing** (e.g., Cardiology).
   - In-scope / out-of-scope statements clear.
   - Mentions cross-peer integrations (cardiology ↔ anesthesia for periop).

**Pass criteria:** A judge browsing for 90 seconds understands what each
piece does and how they fit together, without watching the video first.

---

## Test B — judge experience: invocation (10 min)

The actual demo flow as a judge would experience it.

1. **Sign in to Prompt Opinion** with a fresh-feeling account (or new
   incognito session if the judge's view differs from the developer view).
2. **Open General Chat** with a patient selected. (Mrs. Chen if our
   bundles are uploaded; otherwise PO's default Synthea patient — the
   FHIR fixture fallback handles it.)
3. **Type:** *"Convene the Council on this patient."*
4. **Hit Enter. Stopwatch starts.**

**Expected within 6 seconds:**

- PO chat shows the assistant's short message:
  ```
  🏛️ The Council has convened.
  Eight specialty agents are now reviewing this patient's case in parallel.
  📺 Watch the deliberation live: [link]
  ```
- The link is a `convene-ui.static.hf.space/?id=<uuid>` URL.

**FAIL conditions to catch:**
- Chat shows "The LLM took too long..." banner → Convener didn't return
  in time. Check that fire-and-forget is deployed; check Convener log.
- Chat shows TASK_STATE_FAILED → Convener errored on entry. Check that
  the alias tools (`conven_council`, `consult_council`, etc) are
  registered.
- Chat shows the full plan inline as a wall of text → SYSTEM_INSTRUCTION
  reverted to the verbose format. Re-deploy the Convener.

5. **Click the live link.** Convene-ui loads.

**Expected within 60 seconds of clicking:**
- Specialty status grid shows 4-7 specialties turning green.
- Audit timeline ticks rows.
- Concordant Plan tab count populates with `5` action items.
- Specialty Consults tab populates with the views.

**FAIL conditions:**
- Empty Plan tab "this session ended without a synthesised plan" →
  Round 1 yielded < 2 valid views. Check Convener + MCP logs for
  Vertex 429s; pre-warm and retry.
- Empty Consults tab when Plan rendered → agent_messages aren't
  landing. Check schema role-check constraint + open_session call.

**Pass criteria:** end-to-end flow PO chat → live link → ConcordantPlan
visible in <90 seconds.

---

## Test C — judge experience: artifact review (10 min)

The judge reading the rendered ConcordantPlan.

1. **Brief.** Reads as a clinical summary, not a marketing paragraph.
   - Mentions the patient's specific comorbidities and the pre-op context.
   - Rationale paragraph explains why the plan is what it is.
2. **5T quadrants** (Continue / Start / Stop / Monitor) all populated.
   No "—" empty markers in any quadrant for Mrs. Chen.
3. **Action items.** 5-9 items. Each has owner, due_within, priority pill.
4. **Conflict log.** At least one entry with method pill ("harmonized"
   for Mrs. Chen). Initial positions visible. Resolution paragraph clear.
5. **Preserved dissents.** Section absent for Mrs. Chen (both conflicts
   resolved); for Henderson archetype this section should populate.
6. **Audit timeline** (Live Deliberation tab) shows session_started,
   8 tool_called, 4-7 tool_returned, 1 plan_synthesized, 1 session_ended.
7. **Specialty Consults tab.** 4-7 cards. Each has primary concerns +
   red flags + applicable guidelines + reasoning trace drawer.

**Pass criteria:** A clinician reading the plan would say "this is a
serious clinical-decision-support draft" and not "this is an LLM
hallucinating clinical content."

---

## Test D — Devpost form filling (45 min)

1. **Project name:** Council Health
2. **Tagline:** see `docs/devpost-submission.md` § Project tagline
3. **Built with:** see `docs/devpost-submission.md` § Built with — paste verbatim
4. **Try it links:**
   - Live demo: `https://council-health-ai-convene-ui.static.hf.space/?id=<canonical-session-uuid>`
   - Source code: `https://github.com/council-health-ai/council`
   - Demo video: YouTube Unlisted URL
   - SHARP RFC PR: link
5. **Project story** (the long-form) → paste from `devpost-submission.md`
   (Inspiration → What it does → How we built it → Challenges → Accomplishments → What we learned → What's next).
6. **Demo video URL.** YouTube Unlisted, embeddable.

Final-form review checklist:
- [ ] Tagline ≤140 chars.
- [ ] Demo video plays inline on the Devpost page.
- [ ] All "Try it" links resolve.
- [ ] No mention of `Co-Authored-By: Claude` or any AI co-authorship anywhere.
- [ ] No mention of competitor analysis or specific judge names by category.
- [ ] No leakage of strategy docs (no "demo-script.md", no "judges-by-name.md").

---

## Test E — submitter experience: forking the repo (5 min)

The judge clicks the GitHub link in Devpost and lands on the public repo.

1. **README.md** at root explains what this is in <90 seconds.
   - Architecture diagram visible.
   - Live demo link in first paragraph.
   - Quickstart for the curious developer.
2. **`docs/journey/`** is browsable and readable.
3. **No private docs** in the public repo (no devpost-submission.md
   variants with strategy notes, no judge-by-name beats).
4. **Commits in the public repo have NO `Co-Authored-By: Claude` trailer.**
5. **License is MIT.**

**Pass criteria:** Source code looks like a real submission someone
would deploy at their own institution, not a trade-show demo.

---

## Test F — adversarial: try to break it (15 min)

What if a judge tries to make it fail?

1. **Type a non-Council question** in PO chat after the Convener responds.
   - "What's the weather in Boston?" — Convener should not invoke convene_council.
   - "Tell me a joke." — Same.
2. **Click the live link from a previous session** (any old uuid).
   - Should render correctly even months later (Supabase persistence).
3. **Disable the bearer token** in PO context.
   - The MCP fixture fallback engages, the deliberation completes, the
     audit log says "demo bundle fallback used" — the system is honest
     about what it saw.
4. **Refresh the convene-ui** mid-deliberation.
   - Realtime resubscribes; the partial state renders correctly.
5. **Click the Convener link in the chat** — should open convene-ui in
   the same browser window or new tab (matters for video flow).

**Pass criteria:** The system fails gracefully on edge cases. No 500s,
no infinite loading, no broken page.

---

## Final go / no-go decision

**Greenlight submission if all of:**
- [ ] Test A passes (Marketplace presentable).
- [ ] Test B passes 3 times in a row (PO chat reliable).
- [ ] Test C passes (artifact looks clinical-grade).
- [ ] Test D passes (Devpost form filled, video embedded).
- [ ] Test E passes (public repo professional).
- [ ] Test F passes (graceful failure modes).

**Hold and fix if:** any single test fails. Submitting with a known
broken path is worse than a one-day delay.

**Submit:** click "Submit project" on Devpost before May 11, 11:00 PM EDT.
Take a screenshot of the confirmation. Save the submission URL.

**Post-submit:** drop the submission link in the hackathon Discord
`#showcase` or equivalent channel. Don't @ the judges; let it surface.
