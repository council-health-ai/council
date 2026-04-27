"""Obstetrics + MFM specialty agent — built from the shared factory."""

from council_shared import build_specialty_agent

FOCUS_BLURB = (
    "pregnancy-specific medication safety (LMWH not DOACs/warfarin; labetalol/nifedipine/methyldopa "
    "not ACEi/ARB), hypertensive disorders of pregnancy, and gestational diabetes management"
)

root_agent = build_specialty_agent(specialty="obstetrics", focus_blurb=FOCUS_BLURB)
