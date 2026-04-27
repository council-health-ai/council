"""AgentCard factory — a2a-sdk 0.3.26 (the version google-adk's a2a integration is built against).

Builds AgentCard objects with our custom COIN extension declared. Compatible with the
Prompt Opinion platform (which uses v0 path /.well-known/agent.json — we serve at both v0 and v1
paths in app_factory.py).
"""

from __future__ import annotations

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentExtension,
    AgentInterface,
    AgentSkill,
    APIKeySecurityScheme,
    SecurityScheme,
)

from .config import settings

COIN_EXTENSION_URI = "https://council-health.ai/schemas/a2a/v1/coin"


def make_agent_card(
    *,
    name: str,
    description: str,
    url: str,
    role: str,  # e.g. "cardiology", "convener"
    skills: list[AgentSkill],
    require_api_key: bool = True,
    streaming: bool = True,
    version: str = "0.1.0",
) -> AgentCard:
    """Build an AgentCard with COIN + FHIR extensions declared and apiKey security applied."""

    coin_ext = AgentExtension(
        uri=COIN_EXTENSION_URI,
        description=(
            "Council Opinion Interchange Network — declares this agent participates in Council "
            "deliberations. Convener and specialty agents both declare COIN; the role parameter "
            "describes the agent's function within the deliberation."
        ),
        required=False,
        params={
            "role": role,
            "voteSchema": "concordant-plan-v1",
            "supportsRound2Refinement": True,
        },
    )

    fhir_ext = AgentExtension(
        uri=settings.fhir_extension_uri,
        description="FHIR context allowing the agent to query a FHIR server securely",
        required=False,
        params={
            "scopes": [
                {"name": "patient/Patient.rs", "required": True},
                {"name": "patient/Condition.rs"},
                {"name": "patient/MedicationStatement.rs"},
                {"name": "patient/MedicationRequest.rs"},
                {"name": "patient/Observation.rs"},
                {"name": "patient/AllergyIntolerance.rs"},
                {"name": "patient/Procedure.rs"},
                {"name": "patient/Encounter.rs"},
            ],
        },
    )

    capabilities = AgentCapabilities(
        streaming=streaming,
        push_notifications=False,
        state_transition_history=False,
        extensions=[coin_ext, fhir_ext],
    )

    security_schemes: dict[str, SecurityScheme] | None = None
    security: list[dict[str, list[str]]] | None = None
    if require_api_key:
        security_schemes = {
            "apiKey": SecurityScheme(
                root=APIKeySecurityScheme(
                    type="apiKey",
                    name="X-API-Key",
                    in_="header",
                    description="API key required to access this agent.",
                )
            )
        }
        security = [{"apiKey": []}]

    additional_interfaces = [AgentInterface(transport="JSONRPC", url=url)]

    return AgentCard(
        name=name,
        description=description,
        version=version,
        protocol_version="0.3.0",
        url=url,
        preferred_transport="JSONRPC",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=capabilities,
        additional_interfaces=additional_interfaces,
        skills=skills,
        security_schemes=security_schemes,
        security=security,
    )
