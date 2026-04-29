# Demo dialogue — Mrs. Susan Chen

**Status:** v1, ready for clinician review on BrainX / hackathon Discord.
Hard milestone before video record.

**Patient archetype:** the cardiometabolic-oncology archetype from
`fhir-bundles/bundles/mrs-chen.json`.

---

## Patient summary (from the FHIR bundle)

**Mrs. Susan Chen** · 67-year-old postmenopausal female

**Active conditions:**
- Newly diagnosed cT2N0M0 ER+/PR+/HER2- invasive ductal carcinoma of the
  left breast. Lumpectomy scheduled in ~2 weeks; sentinel lymph node biopsy.
- Paroxysmal atrial fibrillation (CHA₂DS₂-VASc 4) on apixaban 5 mg BID.
- Type 2 diabetes mellitus, **HbA1c 9.2%** (uncontrolled). On metformin
  1000 mg BID + empagliflozin 10 mg QD.
- Chronic kidney disease stage 3a (eGFR 38, SCr 1.4). Hypertensive nephropathy +
  diabetic kidney disease.
- Hypertension, current SBP 138 mmHg on lisinopril 10 mg QD.
- Hyperlipidemia on atorvastatin 40 mg QD.

**Notable demographics for dose-reduction triage:** weight 78 kg
(NOT ≤60 kg), age 67 (NOT ≥80). So apixaban 2.5 mg dose-reduction
criteria are NOT met (need 2 of 3: age ≥80, weight ≤60 kg, SCr ≥1.5).
She stays on **5 mg BID** outside the perioperative hold.

**No known drug allergies.**

---

## The clinical question

The PCP types into PO General Chat (with Mrs. Chen as the active patient):

> *"Convene the Council on this patient. She's about two weeks out from her
> lumpectomy and her HbA1c just came back at 9.2% — I want a coordinated plan
> across her four chronic problems before surgery."*

The Convener fires off the deliberation. The four cardiometabolic-oncology
specialties (Cardiology, Oncology, Nephrology, Endocrinology) are the
clinically-relevant returners; the other four abstain (Obstetrics:
postmenopausal; Developmental Pediatrics: 67yo; Psychiatry: no acute
psychiatric concern noted; Anesthesia: relevant but secondary to the
internal-medicine optimization).

---

## What each specialty says

### Cardiology

**Brief:** A 67yo woman with paroxysmal AF (CHA₂DS₂-VASc 4) on apixaban 5 mg
BID, hypertension on lisinopril 10 mg QD with current SBP 138 (above target),
and CKD stage 3a is two weeks out from a lumpectomy.

**Primary concerns:**
1. Perioperative anticoagulation — balancing stroke risk against surgical bleeding risk.
2. Blood pressure currently 138/—, above guideline target <130/80 mmHg
   (ACC/AHA 2017 + KDIGO 2021 BP-in-CKD).
3. Statin and BP optimization in the context of new oncology comorbidity.

**Red flags:**
- Apixaban must be held perioperatively. Patient does NOT meet 2-of-3
  criteria for the 2.5 mg reduced dose (age 67 < 80, weight 78 > 60,
  SCr 1.4 < 1.5) — she stays on 5 mg BID outside the hold.

**Plan (continue / start / stop / monitor):**
- **Continue:** apixaban 5 mg BID, lisinopril 10 mg QD, atorvastatin 40 mg QD, empagliflozin 10 mg QD.
- **Start:** consider second antihypertensive if BP remains >130/80 after 2-week reassessment.
- **Stop:** apixaban hold ≥ 48 hours pre-op for low-to-moderate bleeding-risk
  procedure (lumpectomy + SLNB qualifies); resume 24 hours post-op once
  surgical hemostasis confirmed. **No bridging** for non-mechanical-valve AF
  on apixaban.
- **Monitor:** BP, signs of bleeding/thrombosis perioperatively, eGFR with
  any med change. Baseline TTE before any future anthracycline-based
  chemotherapy decision (cardio-oncology surveillance).

**Applicable guidelines:** ACC/AHA/HRS 2023 AF; ACC/AHA 2017 HTN; KDIGO
2021 BP-in-CKD; ESC 2022 cardio-oncology.

---

### Oncology

**Brief:** Newly diagnosed cT2N0M0 ER+/PR+/HER2- invasive ductal carcinoma
in a postmenopausal patient with significant comorbidities (CKD 3a, T2DM
HbA1c 9.2%, AF on apixaban, HTN). Lumpectomy + sentinel node biopsy in
2 weeks.

**Primary concerns:**
1. Adjuvant systemic therapy selection — endocrine therapy is core; chemotherapy
   only if Oncotype DX recurrence score warrants.
2. Specific chemotherapy contraindications driven by CKD 3a: cisplatin
   contraindicated; methotrexate dose-adjusted; cyclophosphamide
   metabolites renally cleared — caution.
3. Drug-drug interactions between apixaban and any planned systemic therapy.

**Red flags:**
- Uncontrolled diabetes (HbA1c 9.2%) increases infection risk during
  myelosuppressive chemotherapy if used. Needs glycemic optimization first.
- If anthracycline considered, baseline cardiac function assessment required
  given AF + age (cardio-oncology hand-off to cardiology).

**Plan:**
- **Continue:** all current chronic-disease medications.
- **Start (post-op):** adjuvant endocrine therapy with an aromatase inhibitor
  (anastrozole or letrozole) — postmenopausal, ER+, standard of care.
  Defer chemotherapy decision to Oncotype DX result.
- **Stop:** nothing yet from the oncology side.
- **Monitor:** post-lumpectomy pathology (tumor size, margin, grade, Ki-67);
  Oncotype DX recurrence score; if AI initiated, bone density (DEXA)
  baseline + lipid panel.

**Applicable guidelines:** NCCN Breast Cancer (current edition); ASCO/CAP
HER2 + ER/PR testing.

**Note for clinician review:** chemotherapy decision is contingent on
genomic assay and final pathology — the Council does not pre-commit; it
flags the dependency.

---

### Nephrology

**Brief:** CKD stage 3a (eGFR 38, SCr 1.4). Hypertensive nephropathy +
diabetic kidney disease. Currently on empagliflozin 10 mg QD (renal-protective
SGLT2i, appropriate at this eGFR), lisinopril (RAS blockade — appropriate),
and metformin 1000 mg BID (eGFR-borderline).

**Primary concerns:**
1. Metformin dosing at eGFR 38 — KDIGO 2024 says reduce to maximum 1000 mg
   total daily (i.e., 500 mg BID or 1000 mg QD) when eGFR < 45.
2. Perioperative AKI risk — ensure pre-op euvolemia, avoid nephrotoxic NSAIDs,
   limit IV contrast.
3. Glycemic intensification beyond SGLT2i is endocrinology's call; nephrology
   advises on renal dosing of any new agents.

**Red flags:**
- eGFR is a **single data point**; trend over time would refine progression
  risk. Recommend repeat BMP within 1-2 weeks pre-op.
- BP target in CKD is <120 mmHg systolic (KDIGO 2021) when tolerated — current 138 is above target.

**Plan:**
- **Continue:** empagliflozin 10 mg QD, lisinopril 10 mg QD.
- **Start:** GLP-1 RA per endocrinology (semaglutide is renally tolerable
  at this eGFR) for additional glycemic + cardiorenal benefit; close BP
  monitoring; pre-op BMP + UACR.
- **Stop:** no abrupt stops. **Reduce metformin to 500 mg BID** (i.e.,
  1000 mg total daily) per KDIGO 2024 dosing in CKD 3a.
- **Monitor:** eGFR + electrolytes after med changes; UACR for albuminuria
  trend; BP.

**Applicable guidelines:** KDIGO 2024 Diabetes-in-CKD; KDIGO 2021 BP-in-CKD;
KDIGO 2024 Evaluation & Management of CKD.

---

### Endocrinology

**Brief:** Type 2 diabetes, HbA1c 9.2%, on metformin 1000 mg BID + empagliflozin
10 mg QD. eGFR 38. Postmenopausal, with active oncology comorbidity. Two
weeks pre-lumpectomy.

**Primary concerns:**
1. HbA1c 9.2% is significantly above goal — pre-operative glycemic optimization
   is urgent (target <8% pre-op; ADA Standards of Care 2024).
2. Periprocedural glucose management plan needed for lumpectomy day-of.
3. Future cancer-treatment interactions with glycemic control (e.g.,
   aromatase inhibitors and glucose handling, dexamethasone in chemo
   premedication if used).

**Red flags:**
- Persistent uncontrolled hyperglycemia delays wound healing, increases
  surgical infection risk, complicates any future steroid-containing
  chemotherapy.

**Plan:**
- **Continue:** empagliflozin 10 mg QD (cardiorenal benefit, retain).
  Lisinopril and atorvastatin unchanged.
- **Start:** **GLP-1 RA — semaglutide 0.25 mg SQ weekly initially**, titrate
  per tolerance. Provides both glycemic and cardiometabolic benefit, no
  hypoglycemia risk, weight-neutral or beneficial. Hold semaglutide
  the morning of surgery (per current periprocedural GLP-1 RA guidance
  pending broader anesthesia consensus).
- **Stop:** **reduce metformin to 500 mg BID** per the renal-dosing constraint.
  (Endocrinology agrees with nephrology here — see conflict log if reduction
  is contested.)
- **Monitor:** fasting glucose + post-prandial; HbA1c at 3 months; renal
  function with each med change.

**Applicable guidelines:** ADA Standards of Care in Diabetes 2024; AACE
Comprehensive Diabetes Algorithm; KDIGO 2024 Diabetes-in-CKD.

**Notable dissent (preserved):** Endocrinology raises a flag — while KDIGO
calls for metformin dose reduction at eGFR 38, the patient's HbA1c 9.2%
is severe enough that aggressively reducing her existing glucose-lowering
agent without immediately replacing it could worsen control during the
critical 2-week pre-op window. **Preferred sequence:** initiate semaglutide
first (week 1), reassess glycemia + tolerability at week 2, then taper
metformin to 500 mg BID rather than the same-visit reduction recommended
by nephrology.

---

## The Concordant Plan (synthesized)

**Brief — summary:**
> A 67yo postmenopausal woman with newly diagnosed early-stage ER+/PR+/HER2-
> breast cancer is two weeks pre-lumpectomy with significant cardiometabolic
> comorbidities — paroxysmal AF on apixaban (CHA₂DS₂-VASc 4), uncontrolled
> T2DM (HbA1c 9.2%), CKD stage 3a (eGFR 38), and hypertension above target.
> The Council's pre-operative optimization plan focuses on glycemic
> intensification, renal-dose-aware medication adjustments, perioperative
> apixaban management without bridging, and deferral of adjuvant systemic
> therapy decisions to post-lumpectomy pathology + Oncotype DX.

**Brief — rationale:**
> The patient's overall health and tolerance of upcoming oncologic care are
> rate-limited by her uncontrolled diabetes and CKD. Aggressive glycemic
> management before surgery reduces wound-healing risk, infection risk, and
> downstream chemotherapy complications. Renal-dose-aware adjustments
> (metformin reduction; SGLT2i + RAS-blockade retention; GLP-1 RA addition)
> simultaneously serve glycemic, renal, and cardiometabolic goals. The
> apixaban hold-and-resume plan follows ACC/AHA AFib 2023 — no bridging,
> 48h pre-op hold, 24h post-op resume on confirmed hemostasis. Adjuvant
> endocrine therapy (aromatase inhibitor) is the post-op pillar; chemotherapy
> is reserved for post-op pathology + genomic-assay decision.

**Plan:**

| | |
|---|---|
| **Continue** | Apixaban 5 mg BID (with planned perioperative hold) · Empagliflozin 10 mg QD · Lisinopril 10 mg QD (with possible up-titration) · Atorvastatin 40 mg QD |
| **Start** | Semaglutide 0.25 mg SQ weekly, titrate per tolerance · Pre-op BMP + UACR · Confirm pre-op fasting glucose target 80-130 mg/dL · Schedule post-op pathology review with Oncotype DX |
| **Stop** | Reduce **metformin to 500 mg BID** per KDIGO 2024 renal-dose ceiling — sequenced AFTER GLP-1 RA initiation per Endocrinology's preferred sequence · Hold apixaban 48h pre-lumpectomy, **no bridging** |
| **Monitor** | BP (target <130/80 in this patient with CKD per KDIGO + ACC/AHA) · Renal function (eGFR, BMP, K+) at each med change · Glycemic response (SMBG, HbA1c at 3 months) · Bleeding/thrombosis perioperatively · Post-op pathology + genomic assay |

**Timing notes:**
- Perioperative apixaban management coordinated with surgical team prior to lumpectomy date.
- Semaglutide initiation week 1; metformin dose reduction week 2 after glycemic and tolerability check (per Endocrinology's preserved sequence).
- Adjuvant endocrine therapy initiated post-lumpectomy after final pathology.
- Oncotype DX ordered on lumpectomy specimen; chemotherapy decision driven by recurrence score.

---

## Conflict log

**Topic:** Sequence of metformin reduction relative to GLP-1 RA initiation.

| Specialty | Initial position |
|---|---|
| Nephrology | Reduce metformin to 500 mg BID immediately at this eGFR per KDIGO 2024. |
| Endocrinology | HbA1c 9.2% is severe — initiate semaglutide first to maintain glycemic momentum, THEN reduce metformin at week 2 reassessment. |

**Resolution:** Harmonized via temporal sequencing. Semaglutide initiated
week 1 (no abrupt loss of glucose-lowering effect), metformin dose-reduction
applied week 2 with renal + glycemic recheck. Both safety boundaries
(KDIGO renal ceiling) and clinical-priority concerns (HbA1c 9.2% requires
aggressive control) are honored.

**Method:** harmonized.

---

## Preserved dissent

None for this case — both potential conflicts (metformin sequence;
chemotherapy decision) resolved via temporal sequencing or deferral
to objective data (pathology + genomic assay).

---

## Action items for the primary clinician

1. **[urgent]** Coordinate apixaban hold + resume plan with surgical team before lumpectomy date. *Owner: Primary Care + Surgery. Due: prior to lumpectomy.*
2. **[high]** Initiate semaglutide 0.25 mg SQ weekly. *Owner: Primary Care. Due: this week.*
3. **[high]** Reduce metformin to 500 mg BID at week 2 follow-up. *Owner: Primary Care. Due: 2 weeks.*
4. **[high]** Order pre-op BMP + UACR. *Owner: Primary Care. Due: 1 week.*
5. **[high]** Up-titrate or add a second antihypertensive if SBP remains >130 at week 2. *Owner: Primary Care. Due: 2 weeks.*
6. **[routine]** Order Oncotype DX on lumpectomy specimen at the time of pathology. *Owner: Oncology. Due: post-op pathology review.*
7. **[routine]** Pre-op nutrition + glycemic optimization counseling. *Owner: Primary Care + RD. Due: this week.*
8. **[routine]** If AF rate noted at any pre-op visit, confirm rate-controlled status; otherwise no change. *Owner: Cardiology. Due: ongoing.*
9. **[routine]** Schedule baseline DEXA + lipid panel at AI initiation. *Owner: Oncology. Due: post-op AI start.*

---

## Audit trail summary

- Specialties consulted: 4 (Cardiology, Oncology, Nephrology, Endocrinology)
- Specialties abstained: 4 (Obstetrics & MFM — postmenopausal; Developmental Pediatrics — adult patient; Psychiatry — no acute psychiatric concern; Anesthesia — secondary, perioperative plan delegated to cardiology + surgical team coordination)
- Total messages: 8 inbound SpecialtyViews + 2 MCP synthesis tool calls
- Total rounds: 1 (with conflict resolution embedded in concordance brief)
- FHIR resources referenced: Patient, 5 Conditions, 4 MedicationStatements, ~10 Observations, 0 Procedures (lumpectomy not yet performed)
- Total deliberation latency: ~45 seconds end-to-end

---

## Clinical-review checklist (for BrainX / Discord reviewers)

Reviewers, please flag any of the following:

1. **[ ] Apixaban dosing and perioperative plan.** Confirm 5 mg BID is correct
   given Mrs. Chen does not meet 2-of-3 criteria (age 67 < 80, weight 78 > 60,
   SCr 1.4 < 1.5). Confirm 48h hold + 24h post-op resume + no bridging is
   appropriate for non-mechanical-valve AF on apixaban for a low-to-moderate
   bleeding-risk procedure (lumpectomy + SLNB).
2. **[ ] Metformin dose at eGFR 38.** Confirm KDIGO 2024 ceiling of 1000 mg
   total daily (500 mg BID or 1000 mg QD) at this renal function.
3. **[ ] GLP-1 RA selection and timing.** Semaglutide 0.25 mg SQ weekly
   titration; one week pre-op hold of GLP-1 RA per current periprocedural
   guidance.
4. **[ ] Pre-op glycemic target.** HbA1c < 8% pre-op (ADA Standards of
   Care). Comment on whether 2 weeks is realistic.
5. **[ ] BP target.** <130/80 (ACC/AHA 2017) versus the more aggressive
   <120 systolic in CKD (KDIGO 2021) — current guidance in this patient
   pattern.
6. **[ ] Adjuvant endocrine therapy.** Aromatase inhibitor as standard
   for postmenopausal ER+ disease — anastrozole vs letrozole choice
   considerations.
7. **[ ] Oncotype DX trigger criteria.** Confirm the score-driven
   chemotherapy decision algorithm for this stage/grade combination
   matches current NCCN guidance.
8. **[ ] Anything else** — please flag any clinically-relevant beat the
   Council missed.

---

## Notes for the demo video

- Mrs. Chen's chart shows on screen for ~3 seconds before the consultation
  prompt — gives judges time to register the comorbidity load.
- The deliberation **plays out live** on convene-ui as the video runs;
  agents activate one by one, the audit timeline ticks, the ConcordantPlan
  fills in. Cuts are minimal (1-2 cuts max — let the architecture do the
  talking).
- Voice-over hits exactly four beats:
  1. **Problem framing (~25s):** "60% of Medicare patients are multi-morbid,
     and a single-LLM RAG-over-guidelines can't reason across conflicting
     specialty recommendations…"
  2. **Architecture (~35s):** "Eight specialty agents over peer A2A. SHARP-on-MCP
     gives them safe FHIR context. Real audit log streams to Supabase
     Realtime."
  3. **Live deliberation (~45s):** Watch the agents activate, the conflict
     surface, the brief synthesize.
  4. **Plan + dissent (~30s):** ConcordantPlan rendered as a clinical
     document. Note the preserved dissent — "the Council doesn't paper
     over disagreement."
- Total: ~135s = 2:15. Leaves ~45s for opener + close.
