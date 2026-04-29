# Demo video — shot list & voiceover script

**Target:** 3 minutes max (Devpost limit). Aim 2:50 to leave breathing room.
**Format:** screen recording + voiceover. Minimal cuts (1-2 max).
**Patient:** Mrs. Susan Chen, the cardiometabolic-oncology archetype.

The video is the single most important asset in the submission. Per the
locked plan, **40% of remaining effort goes to demo + Devpost writeup**
because hackathons at this scale are won on the video.

---

## The arc (one sentence)

> A primary-care doctor types one sentence into Prompt Opinion, and 60
> seconds later has a coordinated 9-action pre-operative plan from 4
> different specialists with one preserved dissent — surfaced and
> resolved live, with the full audit trail visible.

---

## 0:00 – 0:08 · Hook

**Visual:** Cold open on the convene-ui ConcordantPlan summary card.
Brief paragraph + the four 5T quadrants visible. Camera is still.
Single beat of silence, then voiceover.

**VO:**
> *"Sixty percent of Medicare patients live with two or more chronic
> conditions. Coordinating their care is a $1.5 trillion problem."*

**Why this beat:** Stat-first hook. Establishes problem scale before
the architectural reveal. Judges who skip past the first 8 seconds
of every video know that everyone else opens with "We built ___" —
this one opens with the problem.

---

## 0:08 – 0:18 · The clinical question

**Visual:** Cut to PO General Chat. Mrs. Chen's chart panel visible on
the right. Cursor types the prompt:
> *"Convene the Council on this patient. She's 2 weeks out from her
> lumpectomy and her HbA1c just came back at 9.2%. I want a
> coordinated plan across her four chronic problems before surgery."*

User hits Enter.

**VO:**
> *"This is the kind of consult where four different specialty
> guidelines pull in four different directions. Cardiology, oncology,
> nephrology, endocrinology — and any single specialist's
> recommendation is reasonable in isolation, but the interaction is
> where harm happens."*

---

## 0:18 – 0:28 · The Convener responds

**Visual:** PO chat shows the assistant's short response, three
paragraphs:

> 🏛️ **The Council has convened.**
>
> Eight specialty agents are now reviewing this patient's case in parallel.
>
> 📺 Watch the deliberation live: [convene-ui link]

The cursor hovers over the link, then clicks.

**VO:**
> *"The Convener fires off a peer-A2A fan-out to eight specialty agents
> in parallel and returns this short reply in under five seconds. The
> deliberation itself takes about a minute — too long for a chat
> reply, so it streams to a live deliberation viewer instead."*

**Why this beat:** establishes the architectural inversion explicitly
— PO chat surface is intentionally fast and minimal; the magic happens
on its own surface.

---

## 0:28 – 1:25 · Live deliberation playback

**Visual:** Cut to convene-ui. The page is loaded with the live session.

The shot stays on the convene-ui for ~57 seconds. The viewer watches:

1. **Specialty agents grid** (left card): Cardiology, Oncology,
   Nephrology, Endocrinology each turn from gray (idle) to yellow
   (thinking, with a pulsing dot) one by one over ~5 seconds. Then
   green (done) one by one as each returns.
2. **Audit timeline** (right card): events tick in. "Convener · Convening
   session opened" then 8 successive "Calls get_<specialty>_perspective"
   then 4 successive "Returns N concerns, N red flags".
3. **Specialty Consults tab** lights up its count (`2` → `3` → `4` → `5`).
4. The status pill in the top-right transitions from "active" (sage
   pulsing dot) to "completed" (navy dot).
5. **Concordant Plan tab count** populates (`5` action items).

The voiceover narrates over this.

**VO** (~57 seconds — broken into three sub-beats):

**Beat 1 (0:28 – 0:48):**
> *"Here's the deliberation playing out live. Each specialty agent
> reviews the chart through its own clinical lens — guidelines,
> red flags, dose-adjustment rules — and returns a structured
> SpecialtyView. Cardiology's looking at perioperative anticoagulation
> and BP control. Oncology's focused on adjuvant systemic therapy
> selection and CKD-aware chemotherapy contraindications. Nephrology's
> watching the metformin dose ceiling at eGFR 38. Endocrinology is
> intensifying glycemic management before the surgery."*

**Beat 2 (0:48 – 1:08):**
> *"Every reasoning step writes a row to a Supabase audit table —
> queryable forever, streamed live via Postgres Realtime. This is the
> Mandel-style MedLog vision realized as a first-class architectural
> feature, not an afterthought. Look at the timeline: each
> 'Tool returned' event captures the count of concerns and red flags
> from that specialty before the brief synthesis even runs."*

**Beat 3 (1:08 – 1:25):**
> *"The conflict the Council surfaces here is real. Nephrology says
> reduce the metformin dose immediately at eGFR 38, per KDIGO 2024.
> Endocrinology pushes back — HbA1c 9.2% is severe, initiate a
> GLP-1 agonist first to maintain glycemic momentum, THEN reduce
> metformin at the next visit. The brief synthesizer harmonizes via
> temporal sequencing; both safety boundaries honored, the dissent
> logged. Watch the conflict log fill in now."*

**Visual cue:** as the VO mentions the conflict log, the **Concordant
Plan tab** is clicked. Tab transition. The brief renders, the 5T
quadrants populate, the action plan list fills in, the conflict log
section becomes visible.

---

## 1:25 – 2:10 · ConcordantPlan render — the document

**Visual:** Concordant Plan tab. Scroll slowly through:

- **Brief** (summary + rationale paragraphs) — pause for ~2 seconds, let
  the viewer read the lede.
- **Continue / Start / Stop / Monitor** quadrants — quick pan, ~3 seconds.
- **Action plan** with priority badges — pause for ~5 seconds on the
  urgent + high-priority items.
- **Conflict log** — pause for ~5 seconds; explicit "harmonized" method
  pill visible.
- (No "Preserved dissents" section in this case — both conflicts resolved.)

**VO** (~45 seconds):
> *"This is the ConcordantPlan, rendered in the Prompt Opinion 5T
> framework — Template, Table, and Task all in one artifact. The
> brief is two paragraphs of plain-English clinical reasoning. The
> plan is the canonical continue / start / stop / monitor format
> any clinician knows. The action items are explicit tasks for the
> primary care clinician with owner, priority, and due date. And
> the conflict log shows exactly how each disagreement was resolved
> — by harmonization, by deferral to specialty, by guideline alignment,
> by patient preference, or, when the Council can't fully converge,
> as preserved dissents. The Council does not paper over disagreement.*
> *That's the differentiator from orchestrator-and-router patterns.*
> *The clinician sees the full reasoning, including where the agents
> didn't fully agree, and decides."*

---

## 2:10 – 2:40 · The architectural punch

**Visual:** Cut to a clean still frame — the architecture diagram from
[`council/docs/journey/`](docs/journey/) or a simple textbox slide:

```
8 specialty A2A peers · 1 SHARP-on-MCP server · live audit · ConcordantPlan

   peer-to-peer A2A — not orchestrator-with-router
   real 403 enforcement at the MCP edge — first impl to do this
   SHARP convening-session RFC — contributed upstream
   10 distinct Vertex regions — same project, ~10× burst quota
   Tunisia builder · $0 cash · no card
```

**VO** (~30 seconds):
> *"Architecturally — eight specialty agents over peer-to-peer A2A,
> not orchestrator-with-router. One SHARP-on-MCP server with real
> HTTP 403 enforcement at the request edge — none of the three
> reference implementations do this. A SHARP convening-session
> extension RFC contributed upstream to po-community-mcp. Ten distinct
> Vertex regions for quota distribution on the same GCP trial credit
> — independent per-region per-minute pools. And shipped on zero
> personal cash, no international credit card, from Tunisia."*

---

## 2:40 – 2:55 · Close

**Visual:** Cut to the convene-ui homepage with the Council Health logo
prominent. Animation: the logo + "council-health-ai" subdomain visible.
Brief silence.

**VO:**
> *"Council Health. Multi-specialty deliberation as a primitive. Built
> for the multi-morbid patients single-LLM systems can't reason about."*

End on logo. ~5 seconds of silence after the VO ends. Fade to black.

---

## 2:55 – 3:00 · Cards

**Visual:** End cards (no VO):
- "Built for the *Agents Assemble — The Healthcare AI Endgame* hackathon"
- "Live: convene.health" (or HF static URL until the domain is registered)
- "Source: github.com/council-health-ai/council"
- "SHARP RFC: [PR link]"

---

## Production checklist

### Tools

- **Recording:** macOS built-in screen recorder (Cmd+Shift+5) — already
  available, free, no install.
  - Set capture area to a fixed 1920×1080 region for clean upload.
- **Editing:** DaVinci Resolve (free) — adequate for cuts, captions,
  end cards. Or iMovie if simpler is faster.
- **Voiceover recording:** Audacity (free) for VO take + cleanup.
- **Music:** OPTIONAL. If used, royalty-free from YouTube Audio Library
  — calm, light bed, low volume. Most strong demos skip music entirely
  and let the VO carry. Recommend: NO music.

### Captions

Burn-in captions on every line of VO. Many judges watch with audio off
on first pass.

### Render

- Format: 1080p MP4, H.264, AAC audio, CFR.
- Duration: 2:50 - 2:58 (Devpost limit is 3:00; leave a small buffer).
- Upload: YouTube **Unlisted** (allows the Devpost embed; not searchable).

### Pre-record dry run

Do a full take with the live deliberation playing through ONCE before
the real take. Catches:
- Timing of the live deliberation playback (varies between 30-60 seconds
  depending on Vertex region quota at recording time)
- Audio levels
- Cuts that feel rushed

### Recording session prep (the morning of)

1. Pre-warm all 10 services (`for s in …; do curl -s …/healthz; done`).
2. Wait 60 seconds (Vertex per-minute quota window resets).
3. Open PO General Chat, select Mrs. Chen.
4. Start screen recording.
5. Type prompt, hit Enter, click the link the moment it appears.
6. Let the live deliberation play out fully.
7. Switch to Concordant Plan tab once the brief lands.
8. Stop recording.
9. Re-record VO over the screen capture later.

---

## Per-judge beat checklist (sanity-check before publish)

| Judge | Hook embedded? |
|---|---|
| Mandel (SMART-on-FHIR) | "Mandel-style MedLog vision" + "SHARP convening-session RFC contributed upstream" — ✓ in beat 0:48-1:08 |
| Hickey (Mayo) | Multi-specialty collective intelligence — ✓ implicit throughout |
| Proctor (pediatric) | One specialty agent abstains correctly (Developmental Pediatrics on a 67yo) — ✓ visible in roster |
| Mathur (intensivist + BrainX) | Apixaban perioperative beat + dose criteria + CHA₂DS₂-VASc 4 + clinical-review process — ✓ in dialogue + Devpost acknowledgment |
| Zheng (women's health) | Mrs. Chen as primary patient — postmenopausal ER+ breast cancer + comorbidities — ✓ entire video |
| Tripathi (Vertex DevRel) | "10 distinct Vertex regions for quota distribution on the same GCP trial credit" — ✓ in beat 2:10-2:40 |

If any judge's hook is NOT clearly embedded, re-script that beat before
recording.

---

## Backup plan

If the live deliberation has a slow run during recording (e.g., Vertex
quota cold), switch to:

> **Option A:** Re-record the deliberation on a freshly-warmed quota
>   window 5 minutes later. Edit the screen capture so the timeline
>   feels brisk.

> **Option B:** Pre-recorded canonical session URL — the ConcordantPlan
>   for Mrs. Chen from a previous successful run is persisted in
>   Supabase forever. Reload that session URL in convene-ui. Instant
>   render. Use this as the visual; voice-over doesn't change.

Option B is the safety net. Document the canonical session URL in
the recording-session prep notes so it's one click away if needed.
