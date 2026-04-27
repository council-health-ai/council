"""ASGI entrypoint for the Oncology agent."""

from council_shared import make_specialty_a2a_app

from .agent import FOCUS_BLURB

a2a_app = make_specialty_a2a_app(specialty="oncology", focus_blurb=FOCUS_BLURB)
