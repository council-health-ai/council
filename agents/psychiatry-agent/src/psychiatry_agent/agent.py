"""Psychiatry specialty agent — built from the shared factory."""

from council_shared import build_specialty_agent

FOCUS_BLURB = (
    "psychotropic drug interactions (CYP, P-gp), anticholinergic burden in elderly, "
    "QT-prolonging psychotropics, and adherence/capacity considerations in cognitive impairment"
)

root_agent = build_specialty_agent(specialty="psychiatry", focus_blurb=FOCUS_BLURB)
