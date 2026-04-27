/** Single import surface for all 8 specialty lens specs. */
import { CARDIOLOGY_LENS } from "./cardiology.js";
import { ONCOLOGY_LENS } from "./oncology.js";
import { NEPHROLOGY_LENS } from "./nephrology.js";
import { ENDOCRINOLOGY_LENS } from "./endocrinology.js";
import { OBSTETRICS_LENS } from "./obstetrics.js";
import { DEVELOPMENTAL_PEDIATRICS_LENS } from "./developmental_pediatrics.js";
import { PSYCHIATRY_LENS } from "./psychiatry.js";
import { ANESTHESIA_LENS } from "./anesthesia.js";

import type { LensSpec } from "./shared.js";
import type { Specialty } from "./types.js";

export const ALL_LENSES: LensSpec[] = [
  CARDIOLOGY_LENS,
  ONCOLOGY_LENS,
  NEPHROLOGY_LENS,
  ENDOCRINOLOGY_LENS,
  OBSTETRICS_LENS,
  DEVELOPMENTAL_PEDIATRICS_LENS,
  PSYCHIATRY_LENS,
  ANESTHESIA_LENS,
];

export const LENS_BY_SPECIALTY: Record<Specialty, LensSpec> = {
  cardiology: CARDIOLOGY_LENS,
  oncology: ONCOLOGY_LENS,
  nephrology: NEPHROLOGY_LENS,
  endocrinology: ENDOCRINOLOGY_LENS,
  obstetrics: OBSTETRICS_LENS,
  developmental_pediatrics: DEVELOPMENTAL_PEDIATRICS_LENS,
  psychiatry: PSYCHIATRY_LENS,
  anesthesia: ANESTHESIA_LENS,
};

/** Tool descriptions for MCP registration. */
export const LENS_DESCRIPTIONS: Record<Specialty, string> = {
  cardiology:
    "Cardiology specialty review. Covers AFib/HF/CAD/valvular, anticoagulation strategy, QT risk, and renal-cleared cardiac drug dosing.",
  oncology:
    "Oncology specialty review. Covers solid-tumor and heme malignancy management, systemic therapy choice (incl. ER/PR/HER2-driven), supportive care, oncologic emergencies.",
  nephrology:
    "Nephrology specialty review. Covers CKD/AKI staging, electrolyte/acid-base management, and renally-cleared drug dosing across all classes.",
  endocrinology:
    "Endocrinology specialty review. Covers DM/thyroid/adrenal/pituitary/bone, agent selection, and individualized glycemic targets.",
  obstetrics:
    "Obstetrics + maternal-fetal medicine review. Covers pregnancy-specific medication safety, hypertensive and diabetic disorders of pregnancy, and VTE prophylaxis.",
  developmental_pediatrics:
    "Developmental-behavioral pediatrics review. Covers syndromic and developmental concerns, weight-based pediatric dosing, behavioral comorbidity, transitions of care.",
  psychiatry:
    "Psychiatry specialty review. Covers mood/anxiety/psychosis/SUD, psychotropic interactions, anticholinergic burden, suicide risk, perinatal/oncologic considerations.",
  anesthesia:
    "Anesthesia + perioperative review. Covers ASA risk stratification, perioperative anticoagulation, airway/OSA, and ICU interface for surgical patients.",
};
