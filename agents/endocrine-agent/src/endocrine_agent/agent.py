"""Endocrinology specialty agent — built from the shared factory."""

from council_shared import build_specialty_agent

FOCUS_BLURB = (
    "diabetes management with individualized glycemic targets (deintensification in elderly polypharmacy "
    "where indicated), thyroid/adrenal/pituitary considerations, and SGLT2i/GLP-1RA agent decisions"
)

root_agent = build_specialty_agent(specialty="endocrinology", focus_blurb=FOCUS_BLURB)
