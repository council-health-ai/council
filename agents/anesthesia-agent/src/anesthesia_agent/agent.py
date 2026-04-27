"""Anesthesia + perioperative specialty agent — built from the shared factory."""

from council_shared import build_specialty_agent

FOCUS_BLURB = (
    "perioperative risk stratification (ASA, RCRI, frailty), renal-adjusted DOAC hold timing, "
    "OSA postoperative strategy, and Beers-list anticholinergic management around procedures"
)

root_agent = build_specialty_agent(specialty="anesthesia", focus_blurb=FOCUS_BLURB)
