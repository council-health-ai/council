/** Minimal FHIR R4 types we actually use — full @smile-cdr/fhirts is overkill. */

export interface CodeableConcept {
  coding?: Array<{ system?: string; code?: string; display?: string }>;
  text?: string;
}

export interface Reference {
  reference?: string;
  display?: string;
}

export interface Patient {
  resourceType: "Patient";
  id?: string;
  active?: boolean;
  gender?: "male" | "female" | "other" | "unknown";
  birthDate?: string;
  name?: Array<{ family?: string; given?: string[]; use?: string }>;
}

export interface Condition {
  resourceType: "Condition";
  id?: string;
  clinicalStatus?: CodeableConcept;
  verificationStatus?: CodeableConcept;
  code?: CodeableConcept;
  subject?: Reference;
  onsetDateTime?: string;
  recordedDate?: string;
  severity?: CodeableConcept;
  bodySite?: CodeableConcept[];
  note?: Array<{ text?: string }>;
}

export interface MedicationStatement {
  resourceType: "MedicationStatement";
  id?: string;
  status?: string;
  medicationCodeableConcept?: CodeableConcept;
  medicationReference?: Reference;
  subject?: Reference;
  effectiveDateTime?: string;
  effectivePeriod?: { start?: string; end?: string };
  dosage?: Array<{
    text?: string;
    route?: CodeableConcept;
  }>;
  reasonCode?: CodeableConcept[];
}

export interface MedicationRequest {
  resourceType: "MedicationRequest";
  id?: string;
  status?: string;
  intent?: string;
  medicationCodeableConcept?: CodeableConcept;
  medicationReference?: Reference;
  subject?: Reference;
  authoredOn?: string;
  dosageInstruction?: Array<{
    text?: string;
  }>;
}

export interface Observation {
  resourceType: "Observation";
  id?: string;
  status?: string;
  category?: Array<{ coding?: Array<{ system?: string; code?: string }> }>;
  code?: CodeableConcept;
  subject?: Reference;
  effectiveDateTime?: string;
  valueQuantity?: { value?: number; unit?: string; code?: string; system?: string };
  valueCodeableConcept?: CodeableConcept;
  valueString?: string;
  interpretation?: CodeableConcept[];
  referenceRange?: Array<{ low?: { value?: number }; high?: { value?: number }; text?: string }>;
}

export interface AllergyIntolerance {
  resourceType: "AllergyIntolerance";
  id?: string;
  clinicalStatus?: CodeableConcept;
  code?: CodeableConcept;
  patient?: Reference;
  criticality?: string;
  reaction?: Array<{ manifestation?: CodeableConcept[]; severity?: string }>;
}

export interface Procedure {
  resourceType: "Procedure";
  id?: string;
  status?: string;
  code?: CodeableConcept;
  subject?: Reference;
  performedDateTime?: string;
  performedPeriod?: { start?: string; end?: string };
}

export interface Encounter {
  resourceType: "Encounter";
  id?: string;
  status?: string;
  class?: { code?: string; display?: string };
  type?: CodeableConcept[];
  subject?: Reference;
  period?: { start?: string; end?: string };
  reasonCode?: CodeableConcept[];
}

export interface Bundle<T = Record<string, unknown>> {
  resourceType: "Bundle";
  id?: string;
  type?: string;
  total?: number;
  entry?: Array<{ resource?: T; fullUrl?: string }>;
}

export interface PatientChart {
  patient: Patient;
  conditions: Condition[];
  medications: MedicationStatement[];
  medicationRequests: MedicationRequest[];
  observations: Observation[];
  allergies: AllergyIntolerance[];
  procedures: Procedure[];
  encounters: Encounter[];
}
