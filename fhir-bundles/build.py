"""Generate FHIR R4 transaction bundles for The Council's 4 demo patients.

Produces clinically airtight synthetic bundles for upload to the Prompt Opinion workspace.
Codes are SNOMED CT / LOINC / RxNorm — verified against published terminology.

Run:
    python build.py

Outputs:
    bundles/mrs-chen.json    (67F, ER+/HER2- breast ca + AFib + CKD3 + T2DM — primary demo)
    bundles/aanya.json       (8F, T21 + repaired CHD + hypothyroidism + OSA + GDD — pediatric)
    bundles/sarah.json       (32F at 28w, T1DM + cHTN + prior PE — high-risk OB)
    bundles/henderson.json   (78M, CHF + COPD + CKD + Parkinson's + depression — geriatric polypharmacy)
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

# ─── code helpers ────────────────────────────────────────────────────────

SNOMED = "http://snomed.info/sct"
LOINC = "http://loinc.org"
RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
ICD10 = "http://hl7.org/fhir/sid/icd-10-cm"


def cc(system: str, code: str, display: str) -> dict:
    """CodeableConcept."""
    return {"coding": [{"system": system, "code": code, "display": display}], "text": display}


def ref(resource_type: str, rid: str) -> dict:
    return {"reference": f"{resource_type}/{rid}"}


def patient(
    *,
    rid: str,
    given: str,
    family: str,
    gender: str,
    birth_date: str,
    address_country: str = "US",
) -> dict:
    return {
        "resourceType": "Patient",
        "id": rid,
        "active": True,
        "name": [{"use": "official", "family": family, "given": [given]}],
        "gender": gender,
        "birthDate": birth_date,
        "address": [{"use": "home", "country": address_country}],
        "extension": [
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                "extension": [{"url": "text", "valueString": "Synthetic"}],
            },
        ],
    }


def encounter(*, rid: str, patient_id: str, when: str, reason: str) -> dict:
    return {
        "resourceType": "Encounter",
        "id": rid,
        "status": "finished",
        "class": {
            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
            "code": "AMB",
            "display": "ambulatory",
        },
        "type": [cc(SNOMED, "11429006", "Consultation")],
        "subject": ref("Patient", patient_id),
        "period": {"start": when, "end": when},
        "reasonCode": [{"text": reason}],
    }


def condition(
    *,
    rid: str,
    patient_id: str,
    snomed_code: str,
    snomed_display: str,
    onset_date: str,
    clinical_status: str = "active",
    severity: str | None = None,
    body_site: tuple[str, str] | None = None,
    notes: str | None = None,
) -> dict:
    res: dict = {
        "resourceType": "Condition",
        "id": rid,
        "clinicalStatus": cc(
            "http://terminology.hl7.org/CodeSystem/condition-clinical",
            clinical_status,
            clinical_status.capitalize(),
        ),
        "verificationStatus": cc(
            "http://terminology.hl7.org/CodeSystem/condition-ver-status",
            "confirmed",
            "Confirmed",
        ),
        "code": cc(SNOMED, snomed_code, snomed_display),
        "subject": ref("Patient", patient_id),
        "onsetDateTime": onset_date,
        "recordedDate": onset_date,
    }
    if severity:
        res["severity"] = {"text": severity}
    if body_site:
        res["bodySite"] = [cc(SNOMED, body_site[0], body_site[1])]
    if notes:
        res["note"] = [{"text": notes}]
    return res


def medication_statement(
    *,
    rid: str,
    patient_id: str,
    rxnorm_code: str,
    medication: str,
    dose: str,
    route: str = "oral",
    frequency: str = "BID",
    started: str,
    reason_text: str | None = None,
) -> dict:
    res: dict = {
        "resourceType": "MedicationStatement",
        "id": rid,
        "status": "active",
        "medicationCodeableConcept": cc(RXNORM, rxnorm_code, medication),
        "subject": ref("Patient", patient_id),
        "effectiveDateTime": started,
        "dateAsserted": started,
        "dosage": [
            {
                "text": f"{dose} {route} {frequency}",
                "route": cc(SNOMED, "26643006", "Oral route") if route == "oral" else {"text": route},
            }
        ],
    }
    if reason_text:
        res["reasonCode"] = [{"text": reason_text}]
    return res


def observation_quantity(
    *,
    rid: str,
    patient_id: str,
    loinc_code: str,
    loinc_display: str,
    value: float,
    unit: str,
    unit_code: str,
    when: str,
    interpretation: str | None = None,
    category: str = "laboratory",
) -> dict:
    res: dict = {
        "resourceType": "Observation",
        "id": rid,
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": category,
                        "display": category.capitalize(),
                    }
                ]
            }
        ],
        "code": cc(LOINC, loinc_code, loinc_display),
        "subject": ref("Patient", patient_id),
        "effectiveDateTime": when,
        "valueQuantity": {
            "value": value,
            "unit": unit,
            "system": "http://unitsofmeasure.org",
            "code": unit_code,
        },
    }
    if interpretation:
        res["interpretation"] = [
            cc(
                "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                interpretation,
                interpretation,
            )
        ]
    return res


def observation_codeable(
    *,
    rid: str,
    patient_id: str,
    loinc_code: str,
    loinc_display: str,
    value_system: str,
    value_code: str,
    value_display: str,
    when: str,
) -> dict:
    """Categorical observation (e.g., ER+ status)."""
    return {
        "resourceType": "Observation",
        "id": rid,
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                    }
                ]
            }
        ],
        "code": cc(LOINC, loinc_code, loinc_display),
        "subject": ref("Patient", patient_id),
        "effectiveDateTime": when,
        "valueCodeableConcept": cc(value_system, value_code, value_display),
    }


def procedure(
    *,
    rid: str,
    patient_id: str,
    snomed_code: str,
    snomed_display: str,
    when: str,
    status: str = "completed",
) -> dict:
    return {
        "resourceType": "Procedure",
        "id": rid,
        "status": status,
        "code": cc(SNOMED, snomed_code, snomed_display),
        "subject": ref("Patient", patient_id),
        "performedDateTime": when,
    }


def allergy_intolerance(
    *,
    rid: str,
    patient_id: str,
    code_system: str,
    code: str,
    display: str,
    criticality: str = "low",
) -> dict:
    return {
        "resourceType": "AllergyIntolerance",
        "id": rid,
        "clinicalStatus": cc(
            "http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
            "active",
            "Active",
        ),
        "verificationStatus": cc(
            "http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
            "confirmed",
            "Confirmed",
        ),
        "code": cc(code_system, code, display),
        "patient": ref("Patient", patient_id),
        "criticality": criticality,
    }


def bundle_entry(resource: dict) -> dict:
    rt = resource["resourceType"]
    rid = resource["id"]
    return {
        "fullUrl": f"urn:uuid:{rid}",
        "resource": resource,
        "request": {"method": "PUT", "url": f"{rt}/{rid}"},
    }


def make_bundle(*, bundle_id: str, resources: list[dict]) -> dict:
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "type": "transaction",
        "timestamp": datetime.now(UTC).isoformat(),
        "entry": [bundle_entry(r) for r in resources],
    }


# ─── Mrs. Chen ───────────────────────────────────────────────────────────
# 67yo F. Postmenopausal. ER+/HER2- invasive ductal carcinoma (recently dx),
# paroxysmal AFib (CHA2DS2-VASc 4), CKD stage 3a (eGFR 38), T2DM with HbA1c 9.2.
# Primary demo patient — apixaban dose IS 5mg BID (only one of three reduction
# criteria met: SCr 1.4 < 1.5; weight 72 > 60; age 67 < 80).

def build_mrs_chen() -> dict:
    pid = "patient-chen-67"
    today = date(2026, 4, 15)
    cancer_dx = today.replace(month=2, day=10).isoformat()
    afib_dx = "2024-09-22"
    ckd_dx = "2022-06-03"
    dm_dx = "2018-11-12"

    encounter_id = "enc-chen-onc-2026-04-15"
    res = [
        patient(
            rid=pid,
            given="Susan",
            family="Chen",
            gender="female",
            birth_date="1958-08-04",
        ),
        encounter(
            rid=encounter_id,
            patient_id=pid,
            when=today.isoformat(),
            reason="Multidisciplinary review — newly diagnosed ER+/HER2- invasive ductal carcinoma; co-managing AFib, CKD3, T2DM",
        ),

        # Conditions
        condition(
            rid="cond-chen-breast-ca",
            patient_id=pid,
            snomed_code="254837009",
            snomed_display="Malignant neoplasm of breast",
            onset_date=cancer_dx,
            severity="moderate",
            body_site=("76752008", "Breast structure"),
            notes="Invasive ductal carcinoma, ER+ PR+ HER2-, clinical stage cT2N0M0; lumpectomy planned",
        ),
        condition(
            rid="cond-chen-afib",
            patient_id=pid,
            snomed_code="49436004",
            snomed_display="Atrial fibrillation",
            onset_date=afib_dx,
            notes="Paroxysmal AFib; CHA2DS2-VASc 4 (HTN, age, female sex, DM); on apixaban for stroke prevention",
        ),
        condition(
            rid="cond-chen-ckd3",
            patient_id=pid,
            snomed_code="433144002",
            snomed_display="Chronic kidney disease stage 3",
            onset_date=ckd_dx,
            notes="CKD stage 3a (eGFR 38); etiology likely diabetic + hypertensive nephropathy",
        ),
        condition(
            rid="cond-chen-t2dm",
            patient_id=pid,
            snomed_code="44054006",
            snomed_display="Type 2 diabetes mellitus",
            onset_date=dm_dx,
            notes="Currently uncontrolled (HbA1c 9.2%); intensification indicated",
        ),
        condition(
            rid="cond-chen-htn",
            patient_id=pid,
            snomed_code="38341003",
            snomed_display="Hypertensive disorder",
            onset_date="2015-03-01",
        ),

        # Medications
        medication_statement(
            rid="med-chen-apixaban",
            patient_id=pid,
            rxnorm_code="1364430",
            medication="Apixaban 5 MG Oral Tablet",
            dose="5 mg",
            frequency="BID",
            started=afib_dx,
            reason_text="AFib stroke prevention (CHA2DS2-VASc 4). Dose: 5 mg BID — does not meet ≥2 of 3 reduction criteria (age ≥80, weight ≤60 kg, SCr ≥1.5).",
        ),
        medication_statement(
            rid="med-chen-metformin",
            patient_id=pid,
            rxnorm_code="860975",
            medication="Metformin Hydrochloride 1000 MG Oral Tablet",
            dose="1000 mg",
            frequency="BID",
            started=dm_dx,
            reason_text="T2DM glycemic control",
        ),
        medication_statement(
            rid="med-chen-empagliflozin",
            patient_id=pid,
            rxnorm_code="1545653",
            medication="Empagliflozin 10 MG Oral Tablet",
            dose="10 mg",
            frequency="QD",
            started="2024-01-15",
            reason_text="T2DM + cardio-renal protection (CKD3 + AFib)",
        ),
        medication_statement(
            rid="med-chen-lisinopril",
            patient_id=pid,
            rxnorm_code="314076",
            medication="Lisinopril 10 MG Oral Tablet",
            dose="10 mg",
            frequency="QD",
            started="2015-04-01",
            reason_text="HTN + CKD nephroprotection",
        ),
        medication_statement(
            rid="med-chen-atorvastatin",
            patient_id=pid,
            rxnorm_code="617310",
            medication="Atorvastatin 40 MG Oral Tablet",
            dose="40 mg",
            frequency="QD",
            started="2019-08-12",
            reason_text="ASCVD primary prevention",
        ),

        # Observations — labs
        observation_quantity(
            rid="obs-chen-hba1c",
            patient_id=pid,
            loinc_code="4548-4",
            loinc_display="Hemoglobin A1c",
            value=9.2,
            unit="%",
            unit_code="%",
            when="2026-04-10",
            interpretation="H",
        ),
        observation_quantity(
            rid="obs-chen-egfr",
            patient_id=pid,
            loinc_code="48642-3",
            loinc_display="Glomerular filtration rate predicted (CKD-EPI)",
            value=38.0,
            unit="mL/min/1.73m2",
            unit_code="mL/min/{1.73_m2}",
            when="2026-04-10",
            interpretation="L",
        ),
        observation_quantity(
            rid="obs-chen-creatinine",
            patient_id=pid,
            loinc_code="2160-0",
            loinc_display="Creatinine [Mass/volume] in Serum or Plasma",
            value=1.4,
            unit="mg/dL",
            unit_code="mg/dL",
            when="2026-04-10",
            interpretation="H",
        ),
        observation_quantity(
            rid="obs-chen-bun",
            patient_id=pid,
            loinc_code="3094-0",
            loinc_display="Urea nitrogen [Mass/volume] in Serum or Plasma",
            value=25.0,
            unit="mg/dL",
            unit_code="mg/dL",
            when="2026-04-10",
        ),
        observation_quantity(
            rid="obs-chen-potassium",
            patient_id=pid,
            loinc_code="2823-3",
            loinc_display="Potassium [Moles/volume] in Serum or Plasma",
            value=4.4,
            unit="mmol/L",
            unit_code="mmol/L",
            when="2026-04-10",
        ),
        observation_quantity(
            rid="obs-chen-bp-sys",
            patient_id=pid,
            loinc_code="8480-6",
            loinc_display="Systolic blood pressure",
            value=138,
            unit="mmHg",
            unit_code="mm[Hg]",
            when="2026-04-15",
            category="vital-signs",
        ),
        observation_quantity(
            rid="obs-chen-bp-dia",
            patient_id=pid,
            loinc_code="8462-4",
            loinc_display="Diastolic blood pressure",
            value=78,
            unit="mmHg",
            unit_code="mm[Hg]",
            when="2026-04-15",
            category="vital-signs",
        ),
        observation_quantity(
            rid="obs-chen-weight",
            patient_id=pid,
            loinc_code="29463-7",
            loinc_display="Body weight",
            value=72.0,
            unit="kg",
            unit_code="kg",
            when="2026-04-15",
            category="vital-signs",
        ),
        # Receptor status
        observation_codeable(
            rid="obs-chen-er",
            patient_id=pid,
            loinc_code="16113-3",
            loinc_display="Estrogen receptor in Tissue",
            value_system=SNOMED,
            value_code="416053008",
            value_display="Oestrogen receptor positive",
            when=cancer_dx,
        ),
        observation_codeable(
            rid="obs-chen-her2",
            patient_id=pid,
            loinc_code="48676-1",
            loinc_display="HER2 [Interpretation] in Tissue",
            value_system=SNOMED,
            value_code="260385009",
            value_display="Negative",
            when=cancer_dx,
        ),

        # Procedures
        procedure(
            rid="proc-chen-core-bx",
            patient_id=pid,
            snomed_code="122548005",
            snomed_display="Core needle biopsy of breast",
            when=cancer_dx,
        ),
    ]
    return make_bundle(bundle_id="bundle-mrs-chen", resources=res)


# ─── Aanya ───────────────────────────────────────────────────────────────
# 8yo F. Trisomy 21 (Down syndrome). Prior AVSD repair. Hypothyroidism on
# levothyroxine. OSA on CPAP. Global developmental delay.

def build_aanya() -> dict:
    pid = "patient-aanya-08"
    res = [
        patient(rid=pid, given="Aanya", family="Patel", gender="female", birth_date="2018-03-22"),
        encounter(
            rid="enc-aanya-multi-2026-04",
            patient_id=pid,
            when="2026-04-12",
            reason="Annual multidisciplinary review — T21, post-AVSD repair, hypothyroidism, OSA, GDD",
        ),
        condition(
            rid="cond-aanya-t21",
            patient_id=pid,
            snomed_code="70156005",
            snomed_display="Trisomy 21",
            onset_date="2018-03-22",
            notes="Confirmed by karyotype shortly after birth.",
        ),
        condition(
            rid="cond-aanya-avsd",
            patient_id=pid,
            snomed_code="13213009",
            snomed_display="Congenital heart disease",
            onset_date="2018-03-22",
            notes="Complete atrioventricular septal defect, repaired surgically at age 5 months. Mild residual MR; stable.",
        ),
        condition(
            rid="cond-aanya-hypothyroid",
            patient_id=pid,
            snomed_code="40930008",
            snomed_display="Hypothyroidism",
            onset_date="2020-09-01",
        ),
        condition(
            rid="cond-aanya-osa",
            patient_id=pid,
            snomed_code="78275009",
            snomed_display="Obstructive sleep apnea",
            onset_date="2023-02-14",
            notes="Moderate OSA per polysomnography (AHI 12). On CPAP.",
        ),
        condition(
            rid="cond-aanya-gdd",
            patient_id=pid,
            snomed_code="248290002",
            snomed_display="Global developmental delay",
            onset_date="2019-06-01",
        ),
        medication_statement(
            rid="med-aanya-levothyroxine",
            patient_id=pid,
            rxnorm_code="966247",
            medication="Levothyroxine Sodium 0.05 MG Oral Tablet",
            dose="50 mcg",
            frequency="QD",
            started="2020-09-15",
            reason_text="Hypothyroidism",
        ),
        observation_quantity(
            rid="obs-aanya-tsh",
            patient_id=pid,
            loinc_code="3016-3",
            loinc_display="Thyrotropin [Units/volume] in Serum or Plasma",
            value=2.8,
            unit="mIU/L",
            unit_code="m[IU]/L",
            when="2026-03-20",
        ),
        observation_quantity(
            rid="obs-aanya-weight",
            patient_id=pid,
            loinc_code="29463-7",
            loinc_display="Body weight",
            value=21.0,
            unit="kg",
            unit_code="kg",
            when="2026-04-12",
            category="vital-signs",
        ),
        procedure(
            rid="proc-aanya-avsd-repair",
            patient_id=pid,
            snomed_code="44777000",
            snomed_display="Repair of atrioventricular septal defect",
            when="2018-08-04",
        ),
    ]
    return make_bundle(bundle_id="bundle-aanya", resources=res)


# ─── Sarah ───────────────────────────────────────────────────────────────
# 32yo F at 28 weeks gestation. T1DM since age 14. Chronic HTN on labetalol
# (pregnancy-safe). Prior submassive PE 2024 — on prophylactic LMWH this pregnancy.

def build_sarah() -> dict:
    pid = "patient-sarah-32"
    res = [
        patient(rid=pid, given="Sarah", family="Williams", gender="female", birth_date="1994-01-09"),
        encounter(
            rid="enc-sarah-mfm-2026-04",
            patient_id=pid,
            when="2026-04-20",
            reason="MFM follow-up — 28w gestation, T1DM, chronic HTN, prior PE on prophylactic anticoag",
        ),
        condition(
            rid="cond-sarah-pregnancy",
            patient_id=pid,
            snomed_code="77386006",
            snomed_display="Pregnancy",
            onset_date="2025-10-13",
            notes="Singleton intrauterine pregnancy. EGA 28w0d as of 2026-04-20.",
        ),
        condition(
            rid="cond-sarah-t1dm",
            patient_id=pid,
            snomed_code="46635009",
            snomed_display="Type 1 diabetes mellitus",
            onset_date="2008-05-01",
            notes="On insulin pump (CSII). HbA1c 6.8%.",
        ),
        condition(
            rid="cond-sarah-htn",
            patient_id=pid,
            snomed_code="38341003",
            snomed_display="Hypertensive disorder",
            onset_date="2022-04-01",
            notes="Chronic HTN preceding pregnancy. On labetalol (pregnancy-safe).",
        ),
        condition(
            rid="cond-sarah-pe-history",
            patient_id=pid,
            snomed_code="59282003",
            snomed_display="Pulmonary embolism",
            onset_date="2024-06-22",
            clinical_status="resolved",
            notes="Submassive PE in 2024 on combined OCP. Completed 6 months therapeutic anticoag. Now on prophylactic LMWH for pregnancy.",
        ),
        medication_statement(
            rid="med-sarah-enoxaparin",
            patient_id=pid,
            rxnorm_code="854228",
            medication="Enoxaparin Sodium 40 MG/0.4ML Prefilled Syringe",
            dose="40 mg",
            frequency="QD",
            started="2025-11-01",
            reason_text="Prophylactic anticoagulation in pregnancy with prior VTE",
        ),
        medication_statement(
            rid="med-sarah-labetalol",
            patient_id=pid,
            rxnorm_code="855334",
            medication="Labetalol Hydrochloride 200 MG Oral Tablet",
            dose="200 mg",
            frequency="BID",
            started="2022-04-15",
            reason_text="Chronic HTN — pregnancy-safe agent",
        ),
        medication_statement(
            rid="med-sarah-aspirin",
            patient_id=pid,
            rxnorm_code="243670",
            medication="Aspirin 81 MG Oral Tablet",
            dose="81 mg",
            frequency="QD",
            started="2025-12-01",
            reason_text="Preeclampsia prophylaxis (USPSTF-aligned for high-risk patients)",
        ),
        observation_quantity(
            rid="obs-sarah-hba1c",
            patient_id=pid,
            loinc_code="4548-4",
            loinc_display="Hemoglobin A1c",
            value=6.8,
            unit="%",
            unit_code="%",
            when="2026-04-15",
        ),
        observation_quantity(
            rid="obs-sarah-bp-sys",
            patient_id=pid,
            loinc_code="8480-6",
            loinc_display="Systolic blood pressure",
            value=128,
            unit="mmHg",
            unit_code="mm[Hg]",
            when="2026-04-20",
            category="vital-signs",
        ),
        observation_quantity(
            rid="obs-sarah-bp-dia",
            patient_id=pid,
            loinc_code="8462-4",
            loinc_display="Diastolic blood pressure",
            value=82,
            unit="mmHg",
            unit_code="mm[Hg]",
            when="2026-04-20",
            category="vital-signs",
        ),
    ]
    return make_bundle(bundle_id="bundle-sarah", resources=res)


# ─── Mr. Henderson ───────────────────────────────────────────────────────
# 78yo M. CHF (HFrEF, EF 35%). COPD. CKD stage 3b (eGFR 38). Parkinson's.
# Major depression. On 14 medications — geriatric polypharmacy archetype.

def build_henderson() -> dict:
    pid = "patient-henderson-78"
    res = [
        patient(rid=pid, given="Robert", family="Henderson", gender="male", birth_date="1947-11-30"),
        encounter(
            rid="enc-henderson-pcp-2026-04",
            patient_id=pid,
            when="2026-04-22",
            reason="Geriatric medication review — symptomatic falls, suspected polypharmacy",
        ),
        condition(
            rid="cond-henderson-hfref",
            patient_id=pid,
            snomed_code="84114007",
            snomed_display="Heart failure",
            onset_date="2018-02-10",
            notes="HFrEF, ischemic etiology. Last echo EF 35%. NYHA class II.",
        ),
        condition(
            rid="cond-henderson-copd",
            patient_id=pid,
            snomed_code="13645005",
            snomed_display="Chronic obstructive lung disease",
            onset_date="2015-08-01",
            notes="GOLD group B (mMRC 2). Last FEV1 55% predicted.",
        ),
        condition(
            rid="cond-henderson-ckd3",
            patient_id=pid,
            snomed_code="433144002",
            snomed_display="Chronic kidney disease stage 3",
            onset_date="2020-01-15",
            notes="CKD 3b (eGFR 38). Etiology likely cardiorenal + age-related.",
        ),
        condition(
            rid="cond-henderson-pd",
            patient_id=pid,
            snomed_code="49049000",
            snomed_display="Parkinson's disease",
            onset_date="2021-09-04",
            notes="Hoehn & Yahr 2. Tremor-predominant.",
        ),
        condition(
            rid="cond-henderson-depression",
            patient_id=pid,
            snomed_code="370143000",
            snomed_display="Major depressive disorder",
            onset_date="2022-06-01",
            notes="Recurrent. PHQ-9 last visit: 14 (moderate).",
        ),
        # Polypharmacy — 14 active meds
        *[
            medication_statement(
                rid=f"med-henderson-{i}",
                patient_id=pid,
                rxnorm_code=rxnorm,
                medication=name,
                dose=dose,
                frequency=freq,
                started=started,
                reason_text=reason,
            )
            for i, (rxnorm, name, dose, freq, started, reason) in enumerate(
                [
                    ("1659149", "Metoprolol Succinate 50 MG Extended Release Oral Tablet", "50 mg", "QD", "2018-03-01", "HFrEF"),
                    ("314076", "Lisinopril 10 MG Oral Tablet", "10 mg", "QD", "2018-03-01", "HFrEF + HTN"),
                    ("315231", "Furosemide 40 MG Oral Tablet", "40 mg", "QD", "2018-04-01", "HFrEF volume management"),
                    ("310429", "Spironolactone 25 MG Oral Tablet", "25 mg", "QD", "2019-06-15", "HFrEF — mineralocorticoid antagonist"),
                    ("617310", "Atorvastatin 40 MG Oral Tablet", "40 mg", "QD", "2018-03-01", "ASCVD secondary prevention"),
                    ("243670", "Aspirin 81 MG Oral Tablet", "81 mg", "QD", "2018-03-01", "ASCVD secondary prevention"),
                    ("746763", "Tiotropium 0.018 MG Inhalation Powder", "1 puff", "QD", "2015-09-01", "COPD"),
                    ("1190795", "Albuterol 90 MCG/Actuation Metered Dose Inhaler", "2 puffs", "PRN", "2015-09-01", "COPD rescue"),
                    ("905395", "Carbidopa-Levodopa 25/100 MG Oral Tablet", "1 tab", "TID", "2021-10-01", "Parkinson's disease"),
                    ("314231", "Sertraline 50 MG Oral Tablet", "50 mg", "QD", "2022-06-15", "Major depression"),
                    ("197361", "Cholecalciferol 1000 UNT Oral Tablet", "1000 IU", "QD", "2020-01-01", "Vitamin D supplementation"),
                    ("198211", "Pantoprazole 40 MG Oral Tablet", "40 mg", "QD", "2019-04-01", "GERD"),
                    ("197531", "Cyclobenzaprine 5 MG Oral Tablet", "5 mg", "QHS", "2024-08-01", "Musculoskeletal pain (FLAGGED — Beers list in elderly)"),
                    ("197590", "Diphenhydramine 25 MG Oral Tablet", "25 mg", "PRN", "2024-08-01", "Sleep aid (FLAGGED — Beers list anticholinergic)"),
                ]
            )
        ],
        observation_quantity(
            rid="obs-henderson-egfr",
            patient_id=pid,
            loinc_code="48642-3",
            loinc_display="Glomerular filtration rate predicted (CKD-EPI)",
            value=38.0,
            unit="mL/min/1.73m2",
            unit_code="mL/min/{1.73_m2}",
            when="2026-04-15",
            interpretation="L",
        ),
        observation_quantity(
            rid="obs-henderson-creatinine",
            patient_id=pid,
            loinc_code="2160-0",
            loinc_display="Creatinine [Mass/volume] in Serum or Plasma",
            value=1.6,
            unit="mg/dL",
            unit_code="mg/dL",
            when="2026-04-15",
            interpretation="H",
        ),
        observation_quantity(
            rid="obs-henderson-ef",
            patient_id=pid,
            loinc_code="10230-1",
            loinc_display="Left ventricular Ejection fraction",
            value=35.0,
            unit="%",
            unit_code="%",
            when="2025-11-08",
            interpretation="L",
        ),
        observation_quantity(
            rid="obs-henderson-bp-sys",
            patient_id=pid,
            loinc_code="8480-6",
            loinc_display="Systolic blood pressure",
            value=118,
            unit="mmHg",
            unit_code="mm[Hg]",
            when="2026-04-22",
            category="vital-signs",
        ),
    ]
    return make_bundle(bundle_id="bundle-henderson", resources=res)


# ─── main ────────────────────────────────────────────────────────────────

ARCHETYPES = [
    ("mrs-chen", build_mrs_chen),
    ("aanya", build_aanya),
    ("sarah", build_sarah),
    ("henderson", build_henderson),
]


def main() -> None:
    out_dir = Path(__file__).parent / "bundles"
    out_dir.mkdir(exist_ok=True)
    for name, builder in ARCHETYPES:
        bundle = builder()
        out = out_dir / f"{name}.json"
        out.write_text(json.dumps(bundle, indent=2))
        n_resources = len(bundle["entry"])
        print(f"  ✓ {name}: {n_resources} resources → {out.relative_to(out_dir.parent.parent)}")


if __name__ == "__main__":
    main()
