"""ASGI entrypoint for the Endocrinology agent."""

from council_shared import make_specialty_a2a_app

from .agent import FOCUS_BLURB

a2a_app = make_specialty_a2a_app(specialty="endocrinology", focus_blurb=FOCUS_BLURB)
