# The Council — Prompt Opinion Marketplace Listings

Ten ready-to-publish listings for the peer A2A specialty network and its supporting MCP server. Each section is self-contained for copy/paste into the PO Marketplace publish form.

---

## 1. specialty-lens-mcp

**Title:** Specialty Lens MCP — SHARP-on-MCP Server for Multi-Specialty Clinical Reasoning

**Tagline:** A SHARP-403-enforcing MCP server that exposes eight specialty perspective tools and two concordance tools for multi-morbid patient deliberation.

**Description:**
specialty-lens-mcp is a TypeScript MCP server built to the SHARP-on-MCP profile. It exposes a curated tool surface for clinical specialty reasoning: eight perspective tools (cardiology, oncology, nephrology, endocrine, obstetrics, pediatrics, psychiatry, anesthesia) plus two concordance tools that surface inter-specialty conflict and synthesize a ConcordantPlan. Inputs and outputs are FHIR R4 native, every call is recorded to an immutable audit trail, and SHARP-403 unauthorized-context responses are enforced at the protocol layer — a guarantee none of the three MCP reference implementations currently provide.

The server applies per-specialty Vertex region routing so that perinatal and pediatric tools can be pinned to data-residency-appropriate regions independently of the rest of the fleet. Tool schemas are versioned, deterministic, and round-trip-clean against the proposed SHARP convening-session extension RFC contributed upstream to po-community-mcp.

Designed for production clinician-facing use. Not a patient-facing assistant; not a chatbot; not a documentation generator.

**Capabilities:**
- 8 specialty perspective tools, each scoped to a defined clinical lens
- 2 concordance tools: `surface_conflicts` and `synthesize_plan`
- SHARP-403 enforcement on every request (refuses out-of-scope context cleanly)
- FHIR R4 input/output across all tools
- Per-tool Vertex region routing for residency-sensitive specialties
- Immutable audit trail with per-call observability hooks
- Versioned, deterministic JSON Schema for every tool
- Compatible with the proposed SHARP convening-session extension

**Tags:** `mcp`, `sharp`, `fhir-r4`, `multi-specialty`, `clinical-reasoning`, `audit-trail`, `vertex-ai`, `typescript`, `peer-a2a`, `concordance`

**What it's good for:**
- Powering a Council-style peer A2A deliberation network
- Adding strict SHARP-403 enforcement to an existing MCP host
- Hosting eight specialty lenses behind a single, audited tool surface
- Multi-morbid case review where conflict-surfacing matters
- Compliance-sensitive deployments needing per-tool region pinning

---

## 2. convener

**Title:** Convener — Peer A2A Facilitator for Multi-Morbid Clinical Deliberation

**Tagline:** Facilitates an eight-specialty peer A2A council in parallel and emits a ConcordantPlan grounded in surfaced conflict.

**Description:**
convener is the facilitating peer in The Council — not a router, not an orchestrator, not a supervisor. It joins the same A2A fabric as the eight specialty agents and participates as a peer whose role is convening, not delegating. On receipt of a multi-morbid case, it fans out to all eight specialties in parallel, collects their independent perspectives, runs the two concordance tools to surface conflicts, and synthesizes a ConcordantPlan using the 5T framework: Template, Table, Task.

The architectural distinction matters. Orchestrator-with-router topologies collapse to a single point of opinion; the convener preserves eight independent specialty voices and only synthesizes after conflict has been made explicit. Every fan-out, every specialty response, and every conflict resolution is recorded to the audit trail in real time. The output is a clinician-reviewable plan, not an autonomous order set.

SHARP-compliant, FHIR R4 native, and built for cases where 60% of Medicare patients have two or more chronic conditions and a single-specialty answer is structurally insufficient.

**Capabilities:**
- Parallel A2A fan-out to 8 specialty peers
- Conflict surface across specialty perspectives via concordance tools
- ConcordantPlan synthesis using the 5T framework (Template + Table + Task)
- Preserves independent specialty voices — no router collapse
- Real-time audit observability for every fan-out and synthesis step
- FHIR R4 case input, ConcordantPlan output
- Honors SHARP convening-session semantics end-to-end
- Deterministic re-runs on the same case input

**Tags:** `a2a`, `peer-network`, `convener`, `multi-morbid`, `concordance`, `5t-framework`, `sharp`, `fhir-r4`, `deliberation`, `clinical`

**What it's good for:**
- Multi-morbid patient deliberation where one specialty alone is insufficient
- Surfacing inter-specialty conflict before a plan is committed
- Tumor boards, perioperative reviews, and complex perinatal cases
- Replacing single-LLM "all-knowing" answers with structured peer review
- Audit-required environments where every step must be reconstructable

---

## 3. cardiology

**Title:** Cardiology Lens — Cardiac Safety and Anticoagulation Reasoning

**Tagline:** Specialty perspective for cardiac safety, anticoagulation strategy, QT risk, and renal-cleared cardiac drug dosing.

**Description:**
The cardiology lens contributes a focused cardiac-safety perspective to a Council deliberation. It evaluates a case for anticoagulation strategy (DOAC selection, bridging, reversal), QT-prolongation risk in the context of the full medication list, and renal-cleared cardiac drug dosing across changing eGFR. It does not act as a primary decision-maker; it returns a perspective that the convener will weigh against seven peers.

In scope: rhythm-versus-rate framing, perioperative anticoagulation interruption, ischemic and bleeding risk balance, heart failure regimen safety, structural and electrophysiologic implications of proposed therapy, and interaction calls flagged from a cardiac-safety viewpoint. Out of scope: definitive cancer regimen choice, primary obstetric management, primary psychiatric medication selection, and any non-cardiac specialty primary read — those belong to peer agents.

SHARP-compliant, FHIR R4 native, audit-logged, and deterministic for the same input. Returns structured findings keyed to the ConcordantPlan template.

**Capabilities:**
- DOAC and warfarin strategy with bleeding-risk framing
- QT-prolongation risk assessment across full med list
- Renal-cleared cardiac drug dosing under changing eGFR
- Perioperative anticoagulation interruption guidance
- Heart failure regimen safety review
- Rhythm-vs-rate strategy framing
- Structured ConcordantPlan-aligned output

**Tags:** `cardiology`, `anticoagulation`, `qt-prolongation`, `doac`, `heart-failure`, `perioperative`, `sharp`, `fhir-r4`, `peer-a2a`

**What it's good for:**
- Multi-morbid cases with cardiac comorbidity
- Bleeding-risk vs thrombotic-risk balancing
- QT-risk surveillance when psychotropics or oncologics are added
- Perioperative cardiac risk and anticoagulation decisions

---

## 4. oncology

**Title:** Oncology Lens — Receptor-Driven Therapy Selection with Comorbidity Awareness

**Tagline:** Specialty perspective on ER/PR/HER2-driven therapy choice, comorbidity-aware regimens, and oncologic drug-drug interactions.

**Description:**
The oncology lens contributes a tumor-biology-grounded perspective to a Council deliberation. It reads receptor status (ER, PR, HER2), staging, and prior lines of therapy, and returns a regimen perspective that is explicitly aware of comorbidities surfaced by other peers — cardiac, renal, hepatic, and psychiatric. It also flags oncologic drug-drug interactions that frequently sit at the boundary between specialties: anthracycline cardiotoxicity, platinum nephrotoxicity, CYP-mediated interactions with psychotropics, and immunotherapy endocrinopathies.

In scope: receptor-driven systemic therapy selection, comorbidity-modulated regimen choice, supportive care for oncologic toxicity, and oncologic interaction flags. Out of scope: cardiac primary management of anthracycline-induced cardiomyopathy (returns to cardiology), renal dose adjustment finalization (returns to nephrology), and pregnancy-specific oncology (returns to obstetrics for the perinatal layer).

SHARP-compliant, FHIR R4 native, audit-logged. Returns structured findings keyed to the ConcordantPlan.

**Capabilities:**
- ER/PR/HER2-driven systemic therapy framing
- Comorbidity-aware regimen selection
- Anthracycline and platinum toxicity surveillance flags
- CYP-mediated drug-drug interaction surfacing
- Immunotherapy-related endocrinopathy awareness
- Supportive care perspective for active treatment
- Structured ConcordantPlan-aligned output

**Tags:** `oncology`, `her2`, `er-pr`, `chemotherapy`, `immunotherapy`, `drug-interactions`, `comorbidity`, `sharp`, `fhir-r4`, `peer-a2a`

**What it's good for:**
- Multi-morbid oncology cases with cardiac, renal, or psychiatric comorbidity
- Receptor-driven first-line and subsequent-line framing
- Surfacing oncologic interactions hiding in long medication lists
- Cases where a single-specialty oncology answer would miss comorbidity drag

---

## 5. nephrology

**Title:** Nephrology Lens — eGFR-Trended Dosing and CKD-Aware Monitoring

**Tagline:** Specialty perspective for eGFR-trended renal dosing, fluid and electrolyte management, and CKD-progression-aware monitoring.

**Description:**
The nephrology lens contributes a renal-physiology-grounded perspective to a Council deliberation. It evaluates the case against eGFR trend (not a single point), flags drugs that require dose adjustment or avoidance, and surfaces fluid and electrolyte considerations that are commonly underweighted when other specialties optimize their own organ system. It is explicitly CKD-progression-aware: a regimen that is acceptable at eGFR 45 may be unsafe by the next encounter.

In scope: renal dose adjustment, contrast and nephrotoxin avoidance, fluid balance in heart failure overlap, electrolyte management (potassium, magnesium, phosphate, bicarbonate), CKD staging and progression risk, and dialysis-relevant timing for drugs and procedures. Out of scope: primary cardiac decision-making, primary oncologic regimen choice, and definitive transplant immunosuppression management — those are peer responsibilities.

SHARP-compliant, FHIR R4 native, audit-logged. Returns structured findings keyed to the ConcordantPlan.

**Capabilities:**
- eGFR-trended renal dose adjustment (not single-point)
- Nephrotoxin and contrast avoidance flags
- Electrolyte management across full med list
- Fluid balance perspective in cardiorenal overlap
- CKD-progression-aware monitoring cadence
- Dialysis-timing implications for drugs and procedures
- Structured ConcordantPlan-aligned output

**Tags:** `nephrology`, `ckd`, `egfr`, `renal-dosing`, `electrolytes`, `cardiorenal`, `sharp`, `fhir-r4`, `peer-a2a`

**What it's good for:**
- Cases with declining eGFR and complex polypharmacy
- Cardiorenal cases where fluid and rhythm priorities collide
- Oncology cases where platinum or contrast exposure is on the table
- Surveillance cadence design for at-risk CKD patients

---

## 6. endocrine

**Title:** Endocrine Lens — Individualized Diabetes Targets and Modern Agent Selection

**Tagline:** Specialty perspective for individualized diabetes targets, thyroid/adrenal/pituitary considerations, and SGLT2i/GLP-1RA decisions.

**Description:**
The endocrine lens contributes a hormonal-system perspective to a Council deliberation. It frames diabetes management with individualized A1c targets — tighter for younger, comorbidity-light patients, looser for frail or hypoglycemia-prone — rather than defaulting to a single number. It surfaces modern agent selection (SGLT2 inhibitors, GLP-1 receptor agonists) with explicit awareness of cardiac, renal, and oncologic comorbidities being weighed by peer agents. It also covers thyroid, adrenal, and pituitary considerations that often hide under a primarily metabolic presentation.

In scope: individualized glycemic targets, SGLT2i and GLP-1RA framing with cardiorenal and oncologic context, insulin regimen design, thyroid replacement and suppression, adrenal sufficiency considerations, and pituitary-axis flags. Out of scope: primary cardiac, oncologic, or perinatal decision-making.

SHARP-compliant, FHIR R4 native, audit-logged. Returns structured findings keyed to the ConcordantPlan.

**Capabilities:**
- Individualized A1c target framing (not one-size-fits-all)
- SGLT2i and GLP-1RA decision support with comorbidity weighting
- Insulin regimen perspective for complex inpatients
- Thyroid replacement and suppression considerations
- Adrenal sufficiency and steroid-stress framing
- Pituitary-axis flags
- Structured ConcordantPlan-aligned output

**Tags:** `endocrine`, `diabetes`, `sglt2i`, `glp1ra`, `thyroid`, `adrenal`, `pituitary`, `sharp`, `fhir-r4`, `peer-a2a`

**What it's good for:**
- Multi-morbid diabetes cases with cardiac or renal stakes
- Choosing among modern agents in the context of a full comorbidity picture
- Thyroid and adrenal layers that primary specialties tend to skip
- Hypoglycemia-risk-aware target setting

---

## 7. obstetrics

**Title:** Obstetrics Lens — Pregnancy-Specific Medication Safety and Perinatal Risk

**Tagline:** Specialty perspective for pregnancy-specific medication safety, hypertensive and diabetic disorders of pregnancy, and VTE prophylaxis.

**Description:**
The obstetrics lens contributes a perinatal-safety perspective to a Council deliberation. It evaluates the case against trimester-specific medication safety, hypertensive disorders of pregnancy (chronic hypertension, gestational hypertension, preeclampsia spectrum), diabetic disorders of pregnancy (pregestational and gestational), and VTE prophylaxis decisions across pregnancy and postpartum. It explicitly flags drugs that other specialties would default to but which are contraindicated or require modification in pregnancy.

In scope: trimester-aware medication review, hypertensive-disorder-of-pregnancy framing, gestational and pregestational diabetes management, antepartum and postpartum VTE prophylaxis, and lactation-safety perspective on continuation decisions. Out of scope: primary cardiac, oncologic, or psychiatric decisions outside the perinatal lens — those return to peer agents with the perinatal flag attached.

SHARP-compliant, FHIR R4 native, audit-logged. Region-pinnable for residency-sensitive perinatal data. Returns structured findings keyed to the ConcordantPlan.

**Capabilities:**
- Trimester-aware medication safety review
- Hypertensive-disorder-of-pregnancy framing across the spectrum
- Gestational and pregestational diabetes perspective
- Antepartum and postpartum VTE prophylaxis decisions
- Lactation-safety continuation guidance
- Region-pinnable Vertex routing for residency
- Structured ConcordantPlan-aligned output

**Tags:** `obstetrics`, `pregnancy`, `preeclampsia`, `gestational-diabetes`, `vte-prophylaxis`, `lactation`, `sharp`, `fhir-r4`, `peer-a2a`

**What it's good for:**
- Pregnant patients with chronic comorbidities under active treatment
- Hypertensive-disorder-of-pregnancy cases with cardiac overlap
- VTE prophylaxis decisions across antepartum and postpartum
- Continuation-vs-modification calls on existing medications

---

## 8. pediatrics

**Title:** Pediatrics (Developmental) Lens — Weight-Based Dosing and Syndromic Awareness

**Tagline:** Specialty perspective for syndromic protocol awareness, weight-based pediatric dosing, behavioral comorbidity, and transitions of care.

**Description:**
The pediatrics lens contributes a developmental-pediatric perspective to a Council deliberation. It treats children as not-small-adults: dosing is weight-based and developmentally bracketed, syndromic protocols (Down, Turner, neurofibromatosis, sickle cell, congenital heart disease post-repair, and more) modulate baseline expectations, and behavioral comorbidity is taken seriously rather than deferred. It also explicitly surfaces transitions-of-care risk — the period when adolescents move from pediatric to adult systems is a documented danger zone, and the lens flags it.

In scope: weight-based and developmentally appropriate dosing, syndromic-protocol-aware care, behavioral and developmental comorbidity layering, transitions-of-care risk flagging, and pediatric-specific safety contraindications. Out of scope: primary adult specialty management — those return to peer agents.

SHARP-compliant, FHIR R4 native, audit-logged. Region-pinnable for pediatric data residency. Returns structured findings keyed to the ConcordantPlan.

**Capabilities:**
- Weight-based, developmentally bracketed dosing
- Syndromic-protocol awareness (Down, Turner, NF, sickle cell, post-CHD-repair, etc.)
- Behavioral and developmental comorbidity integration
- Transitions-of-care risk flagging for adolescents
- Pediatric-specific contraindication surfacing
- Region-pinnable Vertex routing for residency
- Structured ConcordantPlan-aligned output

**Tags:** `pediatrics`, `developmental`, `weight-based-dosing`, `syndromic`, `transitions-of-care`, `behavioral-comorbidity`, `sharp`, `fhir-r4`, `peer-a2a`

**What it's good for:**
- Pediatric patients with chronic syndromic conditions on multi-drug regimens
- Adolescents approaching transition to adult care
- Behavioral comorbidity in the context of medical management
- Cases where adult-default dosing would be unsafe

---

## 9. psychiatry

**Title:** Psychiatry Lens — Psychotropic Interactions and Anticholinergic Burden

**Tagline:** Specialty perspective on psychotropic interactions, anticholinergic burden, QT-prolonging psychotropics, and suicide risk awareness.

**Description:**
The psychiatry lens contributes a psychopharmacology and risk-awareness perspective to a Council deliberation. It reads the full medication list for psychotropic-driven interactions, totals anticholinergic burden across all sources (not just psychotropics), and flags QT-prolonging psychotropics in the context of cardiac and oncologic peers' concerns. Suicide risk awareness is treated as a first-class, non-skippable input — the lens explicitly returns a risk-awareness signal that the convener can route appropriately.

In scope: psychotropic selection and interaction perspective, anticholinergic burden totaling, QT-prolonging psychotropic flags, suicide risk awareness signaling, and behavioral comorbidity layering. Out of scope: primary medical decision-making in non-psychiatric specialties, and any patient-facing crisis intervention — the lens is clinician-facing and returns clinician-reviewable findings only.

SHARP-compliant, FHIR R4 native, audit-logged. Returns structured findings keyed to the ConcordantPlan.

**Capabilities:**
- Psychotropic interaction surfacing across the full med list
- Anticholinergic burden totaling from all sources
- QT-prolonging psychotropic flags integrated with cardiac peer
- Suicide risk awareness as a structured signal
- Behavioral comorbidity layering for medical cases
- Clinician-facing output only — never patient-facing
- Structured ConcordantPlan-aligned output

**Tags:** `psychiatry`, `psychotropics`, `anticholinergic-burden`, `qt-prolongation`, `suicide-risk`, `behavioral`, `sharp`, `fhir-r4`, `peer-a2a`

**What it's good for:**
- Polypharmacy cases where psychotropics meet cardiac and oncologic agents
- Geriatric cases where anticholinergic burden is silently high
- Surfacing suicide risk awareness in a structured, non-skippable way
- Cases where the medical team needs a psychiatry voice without a separate consult queue

---

## 10. anesthesia

**Title:** Anesthesia Lens — Perioperative Risk and Postoperative Strategy

**Tagline:** Specialty perspective for ASA/RCRI risk, perioperative anticoagulation, OSA, and postoperative strategy.

**Description:**
The anesthesia lens contributes a perioperative-risk perspective to a Council deliberation. It frames the case using ASA physical status and RCRI cardiac risk, integrates the cardiology peer's anticoagulation interruption guidance, evaluates OSA risk and its postoperative implications, and returns a postoperative strategy perspective spanning analgesia, monitoring level, and disposition. It is explicitly comorbidity-aware: an OSA patient on chronic opioids facing major surgery is a different problem than the same surgery in an otherwise-healthy patient, and the lens reflects that.

In scope: ASA and RCRI risk framing, perioperative anticoagulation coordination with the cardiology peer, OSA risk and postoperative monitoring implications, postoperative analgesia strategy, and disposition-level recommendations (floor, step-down, ICU). Out of scope: definitive surgical decision-making, primary specialty management of underlying conditions, and any non-perioperative window.

SHARP-compliant, FHIR R4 native, audit-logged. Returns structured findings keyed to the ConcordantPlan.

**Capabilities:**
- ASA physical status and RCRI cardiac risk framing
- Perioperative anticoagulation coordination with cardiology peer
- OSA risk identification and postoperative implication surfacing
- Postoperative analgesia strategy with comorbidity weighting
- Disposition-level perspective (floor / step-down / ICU)
- Comorbidity-aware perioperative monitoring cadence
- Structured ConcordantPlan-aligned output

**Tags:** `anesthesia`, `perioperative`, `asa`, `rcri`, `osa`, `postoperative`, `analgesia`, `sharp`, `fhir-r4`, `peer-a2a`

**What it's good for:**
- Preoperative review of multi-morbid surgical candidates
- Coordinating anticoagulation interruption across cardiology and surgery
- OSA-positive patients facing major surgery or opioid exposure
- Disposition planning when comorbidities push the monitoring level upward
