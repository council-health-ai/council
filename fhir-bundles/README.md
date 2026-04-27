# Demo patient cohort

Hand-built FHIR R4 transaction bundles for The Council's 4 demo archetypes. Synthetic data only — no PHI ever.

| Archetype | File | Bundle entries | Highlights |
|-----------|------|----------------|------------|
| **Mrs. Susan Chen** (67F) — *primary demo* | [`bundles/mrs-chen.json`](bundles/mrs-chen.json) | 23 | ER+/HER2- breast cancer (newly dx), paroxysmal AFib (CHA2DS2-VASc 4), CKD3a (eGFR 38), uncontrolled T2DM (HbA1c 9.2%), HTN. **Apixaban 5 mg BID is correct** — only 1 of 3 reduction criteria met (SCr 1.4 < 1.5; weight 72 > 60; age 67 < 80). |
| **Aanya Patel** (8F) — pediatric | [`bundles/aanya.json`](bundles/aanya.json) | 11 | Trisomy 21, repaired AVSD, hypothyroidism on levothyroxine, moderate OSA on CPAP, GDD. |
| **Sarah Williams** (32F at 28w gestation) — high-risk OB | [`bundles/sarah.json`](bundles/sarah.json) | 12 | Singleton pregnancy, T1DM on CSII, chronic HTN on labetalol, prior submassive PE on prophylactic enoxaparin. |
| **Robert Henderson** (78M) — geriatric polypharmacy | [`bundles/henderson.json`](bundles/henderson.json) | 25 | HFrEF (EF 35%), COPD GOLD-B, CKD3b, Parkinson's, major depression. **14 active meds** including 2 flagged Beers-list (cyclobenzaprine, diphenhydramine). |

## Regenerating

```bash
python3 build.py
```

Codes are SNOMED CT, LOINC, and RxNorm — verified against published terminology. The script is the source of truth; the JSON files are derived.

## Validating

```bash
# Online validator (no install)
# https://validator.fhir.org/

# Or via Inferno (Java)
# https://github.com/onc-healthit/inferno-program
```

## Uploading

Through the Prompt Opinion platform UI:
1. Open `app.promptopinion.ai`
2. **Patients → Import → Upload FHIR Bundle**
3. Pick each `bundles/*.json` in turn
4. Confirm all Conditions / MedicationStatements / Observations render in the patient view
5. Note each platform-issued `Patient.id` and capture in `.env.local` (`MRS_CHEN_PATIENT_ID`, etc.)

## Clinical credibility

Mrs. Chen's bundle is tuned to make the demo case clinically airtight. In particular, the apixaban dosing reflects current FDA label criteria for non-valvular AFib — none of the three reduction triggers (age ≥80, weight ≤60 kg, SCr ≥1.5 mg/dL) are met simultaneously, so 5 mg BID is correct. The Council's nephrology agent surfaces this explicitly, which is the kind of detail that earns clinician trust.
