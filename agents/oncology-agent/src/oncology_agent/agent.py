"""Oncology specialty agent — built from the shared factory."""

from council_shared import build_specialty_agent

FOCUS_BLURB = (
    "ER/PR/HER2-driven systemic therapy choice, comorbidity-aware regimen selection, "
    "drug-drug interactions impacting cancer therapy, and supportive/oncologic-emergency care"
)

root_agent = build_specialty_agent(specialty="oncology", focus_blurb=FOCUS_BLURB)
