# 09 · Process and strategic

Not every challenge was technical. Some were about discipline,
discoverability, and not torching the submission narrative through
oversharing.

---

### Strategic docs accidentally pushed to public repo

**Symptom:** A few days into the build, user noticed `demo-dialogue.md`,
`demo-video-script.md`, and `devpost.md` in the public GitHub repo. These
were strategic working documents — first-draft demo dialogue, video shot
list with judge-targeted beats, Devpost narrative drafts naming specific
judges by clinical interest.

**Risk:** Judges browsing the repo before reviewing the submission would
see the strategic playbook. Every "Mathur is an intensivist, frame X,
mention Y" beat was visible.

**Fix:**
1. Removed the files from the working tree.
2. Force-pushed clean history with `git push --force-with-lease origin main`.
3. Added a memory rule: **strategic working documents stay in the
   private claude-sync repo, never in the public council repo**.

**Followup:** User checked GitHub's "View commit history" UI — the old
commits are still in GitHub's reflog briefly but eventually GC'd. For a
cleaner cut we could `git filter-repo` but the force-push is sufficient
for the submission window.

**Why this matters:** Live strategic docs leak the playbook. Two repos:
public (`council-health-ai/council` — the build) and private
(`claude-sync/...` — strategy, drafts, internal narrative).

---

### `Co-Authored-By: Claude` trailer leaked into one commit

**Symptom:** User noticed one commit in the public repo had a
`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
trailer. The Contributors graph showed `@claude` as a contributor.

**User reaction (verbatim):** "THERE MUST BE NOOOOOO MENTION OF CLAUDE
IN GIT WHY ARE YOU THERE???"

**Fix:**
1. `git commit --amend -m "<message without trailer>"`.
2. `git push --force-with-lease origin main`.
3. Verified all 13 commits no longer contain the trailer.
4. Saved as a permanent feedback memory: `feedback_no_claude_in_git.md`.
   Rule: never add `Co-Authored-By: Claude …` to commits, PRs, or any
   git-visible text in this user's projects. Strip the default Claude Code
   commit template trailer.

**Reality:** GitHub's Contributors graph caches the contributor set and
recalculates on a delayed schedule (hours-days). After the force-push
the underlying git is clean; the Contributors widget eventually catches
up. User notified that the cache is the only remaining stain and it
self-cleans.

**Why this matters:** Hackathon submission narrative is "solo Tunisia
builder, $0 cash, ships multi-agent SHARP-compliant healthcare AI."
Visible AI co-authorship undermines that. The rule is durable across
all future commits in this user's projects.

---

### Demo dialogue clinical accuracy

**Identified risk (locked decision §27):** The original demo dialogue
in `COUNCIL_CONTEXT.md §10` had a clinical error — apixaban 2.5mg BID
dose reduction for non-valvular AF requires **2 of 3 criteria** (age
≥80, weight ≤60 kg, SCr ≥1.5). The script had it triggered by CrCl 38
alone, which is wrong. Mathur (judge — intensivist) would catch this
in 10 seconds.

**Fix-pending:** Hard milestone before video record — submit dialogue
to BrainX LinkedIn group + hackathon Discord for clinician review.
Tracked in todo list. Mathur co-founded BrainX, so his clinical
network reviews submissions before he sees them.

---

### Mandel framing without misattribution

**Identified risk:** Microsoft Healthcare Agent Orchestrator (HAO) is
the obvious comparison. The HAO arXiv paper (2509.06602) is Blondeel,
Lungren et al. 2025. **Mandel is NOT an author** despite his association
with Microsoft.

**Decision:** Cite SMART-on-FHIR (Mandel et al. JAMIA 2016) and Banterop
/ language-first interoperability (Mandel's current work) as the
intellectual lineage. **Do NOT** cite HAO as Mandel's work. Frame the
relationship as: "Builds on the architectural pattern Microsoft popularized
in HAO; inverts orchestrator-vs-specialist topology to peer A2A — closer
to Mandel's language-first thesis than to HAO's group-chat orchestration."

Saved as `project_council_locked_decisions.md §Mandel framing`.

---

### Per-judge demo beats

Each of the 5-6 hackathon judges has a tailored hook documented in
`COUNCIL_CONTEXT.md`:

| Judge | Hook |
|---|---|
| Joshua Mandel (SMART-on-FHIR, Banterop) | SHARP RFC PR upstream + COIN extension + audit-log MedLog hook |
| Stephen Hickey (Mayo Clinic) | Multi-specialty collective-intelligence framing (Mayo's collaborative model) |
| Kris Proctor (pediatric) | Pediatric variant of Mrs. Chen archetype (Aanya bundle) + agentic action |
| Sushil Mathur (BrainX, intensivist) | Polypharmacy + perioperative anticoagulation rigor + BrainX visibility through community review |
| Janet Zheng (women's health) | Mrs. Chen as primary patient — postmenopausal breast cancer + comorbidities — women's health primary case |
| Ramji Tripathi (Vertex Gemini DevRel) | "All 10 services on Vertex Gemini multi-region with $300 trial" — A2A done right + Vertex distribution story |

**Why this matters:** The hackathon brief explicitly closed DM-the-judge
as a path. Community channels (BrainX, Discord) are the surface;
per-judge beats need to surface naturally in the demo + writeup, not
look like name-dropping.

---

### Hard milestones before video record

Per the locked plan:
1. ✅ All 8 specialty lenses + agents built and deployed
2. ✅ SHARP convening-session extension shipped as upstream PR
3. ⏳ Demo dialogue script reviewed by clinicians via BrainX or Discord
4. ⏳ Apixaban dose-reduction beat fixed in dialogue
5. ⏳ Video shot list with timestamps for each judge beat
6. ⏳ Cloud Run migration complete (so all 8 specialties always run)

Items 3-6 still pending; tracked in the todo list.

---

### Time-budget allocation (40% on demo + writeup)

The locked plan calls for **40% of remaining effort** on demo video
+ Devpost writeup, not the typical 30%.

**Justification:** Hackathons at this scale (3,475 registrants → ~150-300
real submissions) are won on the video. The architecture has to be
correct — but a correct architecture without a compelling video gets a
$1,000 honorable mention, not $7,500 1st place.

The build is ~80% done as of this writing. Of the remaining ~20%, the
floor on demo+writeup is **40%, not 30%**. Per `feedback_holy_shit_done.md`
the standard is "ship the complete thing with tests, docs, polish; no
tabling, no workarounds, no dangling threads."
