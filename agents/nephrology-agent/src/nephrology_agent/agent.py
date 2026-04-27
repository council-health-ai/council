"""Nephrology specialty agent — built from the shared factory."""

from council_shared import build_specialty_agent

FOCUS_BLURB = (
    "eGFR/CrCl-trended renal dosing across all drug classes (cardiac, oncology, endocrine, anticoag), "
    "fluid/electrolyte management, and CKD-progression-aware monitoring before med adjustments"
)

root_agent = build_specialty_agent(specialty="nephrology", focus_blurb=FOCUS_BLURB)
