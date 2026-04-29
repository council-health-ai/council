# BrainX / hackathon Discord — clinician review request

The hackathon's locked plan calls for a real clinician review of the demo
dialogue before video record. Mathur (judge) co-founded BrainX; his
clinical network reviews submissions before he sees them. **Community
posts only — never DM judges.**

Two posts below: one for BrainX (LinkedIn group, longer-form), one for
the hackathon Discord (shorter, more conversational). Plus the artifact
to attach: `docs/demo-dialogue.md`.

---

## Post 1: BrainX LinkedIn group (longer)

**Title:** Clinician sanity-check requested: pre-op multi-morbidity Council deliberation (Agents Assemble entry)

**Body:**

Hi everyone — solo Tunisia-based builder shipping an entry to Prompt
Opinion's *Agents Assemble — The Healthcare AI Endgame* hackathon.
Building **The Council** — a peer-to-peer A2A network of 8 specialty
agents (cardiology, oncology, nephrology, endocrinology, obstetrics &
MFM, developmental pediatrics, psychiatry, anesthesia & perioperative)
that deliberate over a multi-morbid patient and synthesize a single
concordant plan with preserved dissent.

Asking for **clinical sanity-check on the demo dialogue** before I
record the video. The patient is a 67-year-old woman with newly-diagnosed
ER+/PR+/HER2- breast cancer on apixaban for paroxysmal AF, with HbA1c 9.2%
on metformin + empagliflozin, eGFR 38 (CKD 3a), and a lumpectomy in
2 weeks.

The Council's plan covers:

- **Apixaban perioperative management.** 5 mg BID outside the hold (she
  doesn't meet 2-of-3 dose-reduction criteria — age 67, weight 78 kg,
  SCr 1.4). 48h pre-op hold, 24h post-op resume, no bridging for
  non-mechanical-valve AF.
- **Metformin renal dose ceiling.** KDIGO 2024 → 500 mg BID at eGFR 38.
  But endocrinology preserved a dissent — sequence GLP-1 RA initiation
  FIRST, THEN metformin reduction, given HbA1c 9.2% severity.
- **Adjuvant systemic therapy.** Aromatase inhibitor post-lumpectomy as
  the postmenopausal ER+ standard; chemotherapy decision deferred to
  Oncotype DX recurrence score.
- **BP target.** ACC/AHA 2017 <130/80 vs KDIGO 2021 <120 SBP in CKD —
  current 138 above either target, recommending up-titrate or add a
  second antihypertensive.

The full dialogue (10 specific clinical decisions across 4 active
specialties) is here:
[**docs/demo-dialogue.md** on the public repo](https://github.com/council-health-ai/council/blob/main/docs/demo-dialogue.md)

There's a **clinical-review checklist at the bottom of that document**
— eight specific items I'd most like flagged. Anything else also welcome.

The architecture is peer-A2A (not orchestrator-with-router), full
SHARP-on-MCP compliance (with real 403 enforcement at the MCP edge —
none of the three reference impls do this), live audit log streaming
to a public deliberation viewer via Supabase Realtime, and a SHARP
convening-session extension RFC contributed upstream as a real PR
to po-community-mcp.

**Specifically NOT looking for:** marketing feedback, "what could you
add" suggestions, or hackathon-strategy advice. Looking for **clinical
errors** — the kind that would make a busy attending read the plan and
say *"no, that's not how we'd actually do it."*

If you have 5 minutes and feel like flagging anything, comment here or
DM. Will credit reviewers in the Devpost submission (with permission).

---

## Post 2: hackathon Discord #clinical-review (or #general) — shorter

> **Clinician sanity-check on a demo dialogue** before I record the
> hackathon video.
>
> Patient: 67yo F, new ER+/PR+/HER2- breast cancer pending lumpectomy,
> paroxysmal AF on apixaban, T2DM HbA1c 9.2%, CKD 3a (eGFR 38),
> hypertension. Council deliberation across cardiology + oncology +
> nephrology + endocrinology produces a coordinated pre-op plan.
>
> Plan covers periop apixaban (no bridging, 48h hold, 5 mg BID full
> dose), KDIGO metformin ceiling at eGFR 38, GLP-1 RA initiation
> sequencing (with a preserved dissent on metformin reduction timing
> from endo), AI as adjuvant standard with Oncotype-deferred
> chemotherapy decision, ACC/AHA / KDIGO BP target.
>
> Full dialogue + 8-item review checklist at the bottom:
> https://github.com/council-health-ai/council/blob/main/docs/demo-dialogue.md
>
> Looking for **clinical errors** specifically. Reviewers credited (with
> permission) in the Devpost.
>
> Submission deadline May 11; aiming to record video by May 7 — so any
> review by ~May 5 is gold.

---

## Where to post

- **BrainX LinkedIn group** — the longer post above.
  Tag: nothing too noisy; let it surface organically. If no engagement
  in 48 hours, post a follow-up reply with "any clinicians who could
  weigh in on the apixaban / metformin sequencing piece specifically?"

- **Hackathon Discord** — the shorter post above. Channel:
  `#clinical-review` if it exists, else `#general` or `#agents-assemble`.

- **Reddit** (optional): r/medicine has a clinician audience but they
  may push back on AI-anything; only post there if BrainX + Discord
  produce nothing in 5 days. If posting there, lead with the clinical
  question, not the tooling.

---

## Acknowledgment / credit plan

In the Devpost "Acknowledgments" section:

> Thanks to the BrainX clinical community and the *Agents Assemble*
> hackathon Discord clinicians for reviewing the demo dialogue and
> catching [specific items they caught — to be filled in].

If a reviewer is willing to be named, list them with their specialty
("Reviewed by [Name], [Specialty], [Institution]"). If they prefer
anonymity, just thank "the reviewers" without names.
