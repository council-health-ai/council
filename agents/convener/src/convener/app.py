"""ASGI entrypoint for the Convener agent.

Run: uvicorn convener.app:a2a_app --host 0.0.0.0 --port 7860
"""

from __future__ import annotations

from a2a.types import AgentSkill
from council_shared import create_a2a_app, settings

from .agent import root_agent

SKILLS = [
    AgentSkill(
        id="convene_council",
        name="Convene The Council on a patient",
        description=(
            "Facilitates a multi-specialty deliberation over a multi-morbid patient using true peer "
            "A2A. Fans out to 8 specialty agents in Round 1, synthesizes a conflict matrix via MCP, "
            "issues Round 2 to specialties involved in conflicts, then emits a ConcordantPlan "
            "artifact (Template + Table + Task in one)."
        ),
        tags=["council", "convener", "multi-specialty", "a2a-peer"],
        examples=[
            "Convene the Council on patient {patient_id}.",
            "Multi-specialty review for patient {patient_id} focused on {topic}.",
        ],
    ),
]


a2a_app = create_a2a_app(
    agent=root_agent,
    name="convener",
    description="Convener — facilitates The Council's peer A2A deliberation.",
    url=settings.service_url or "http://localhost:7860",
    role="convener",
    skills=SKILLS,
    require_api_key=True,
)
