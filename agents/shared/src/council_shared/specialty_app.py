"""Factory for specialty A2A apps — wraps build_specialty_agent + create_a2a_app + a sensible default skill set."""

from __future__ import annotations

from a2a.types import AgentSkill
from starlette.applications import Starlette

from .app_factory import create_a2a_app
from .config import settings
from .models import Specialty
from .specialty_agent import _humanize, build_specialty_agent


def make_specialty_a2a_app(*, specialty: Specialty, focus_blurb: str) -> Starlette:
    """Build a complete A2A ASGI app for a specialty agent."""
    human_name = _humanize(specialty)
    agent = build_specialty_agent(specialty, focus_blurb)

    skills = [
        AgentSkill(
            id=f"opine_on_patient_{specialty}",
            name=f"Provide {human_name} specialty opinion",
            description=(
                f"Given a FHIR Patient.id with SHARP-bridged FHIR context, return a structured "
                f"SpecialtyView covering {focus_blurb}. Used by the Convener in Round 1 of a "
                f"Council deliberation."
            ),
            tags=[specialty, "council", "specialty-opinion"],
            examples=[
                "Convene Council Round 1: please opine on patient {patient_id}.",
                f"Round 2 conflict response: please weigh in from the {human_name} lens.",
            ],
        ),
    ]

    return create_a2a_app(
        agent=agent,
        name=f"{specialty.replace('_', '-')}-agent",
        description=f"{human_name} specialty agent — A2A peer in The Council.",
        url=settings.service_url or "http://localhost:7860",
        role=specialty,
        skills=skills,
        require_api_key=True,
        # CRITICAL: specialty agents are called peer-to-peer by the Convener via the
        # a2a-sdk client, which expects the canonical spec response shape. Reshaping
        # to PO's envelope breaks that path. Only the Convener (called directly by PO)
        # should reshape.
        reshape_response_for_po=False,
    )
