"""ASGI entrypoint for the Nephrology agent."""

from council_shared import make_specialty_a2a_app

from .agent import FOCUS_BLURB

a2a_app = make_specialty_a2a_app(specialty="nephrology", focus_blurb=FOCUS_BLURB)
