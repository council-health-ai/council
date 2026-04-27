"""Cardiology specialty agent — built from the shared factory."""

from council_shared import build_specialty_agent

FOCUS_BLURB = (
    "cardiac safety (especially QT signal in polypharmacy), anticoagulation strategy "
    "for AFib/VTE, and renal-cleared cardiac drug dosing"
)

root_agent = build_specialty_agent(specialty="cardiology", focus_blurb=FOCUS_BLURB)
