"""ASGI entrypoint for the Obstetrics + MFM agent."""

from council_shared import make_specialty_a2a_app

from .agent import FOCUS_BLURB

a2a_app = make_specialty_a2a_app(specialty="obstetrics", focus_blurb=FOCUS_BLURB)
