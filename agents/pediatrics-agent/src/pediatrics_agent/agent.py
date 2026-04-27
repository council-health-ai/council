"""Developmental pediatrics specialty agent — built from the shared factory."""

from council_shared import build_specialty_agent

FOCUS_BLURB = (
    "syndromic-protocol-aware management (T21 surveillance, etc.), strict weight-based pediatric "
    "dosing, behavioral co-occurrence in chronic disease, and transitions of care"
)

root_agent = build_specialty_agent(specialty="developmental_pediatrics", focus_blurb=FOCUS_BLURB)
