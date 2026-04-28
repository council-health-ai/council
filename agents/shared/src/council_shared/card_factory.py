"""AgentCard factory — matches po-adk-python's working v1 shape exactly.

Subclasses two SDK types so v1 fields (supportedInterfaces, params on extension,
location-not-in on apiKey scheme) survive Pydantic serialization without
post-hoc JSON munging.
"""

from __future__ import annotations

from typing import Any

from a2a.types import AgentCapabilities, AgentCard, AgentExtension, AgentSkill
from pydantic import Field

from .config import settings

COIN_EXTENSION_URI = "https://council-health.ai/schemas/a2a/v1/coin"


class AgentExtensionV1(AgentExtension):
    """Adds the v1 `params` field that the installed a2a-sdk drops on serialize."""

    params: dict[str, Any] | None = Field(default=None)


class AgentCardV1(AgentCard):
    """Override two parent fields so the v1 shape survives serialization:

    1. `supportedInterfaces` — not defined in installed a2a-sdk; declared as a
       Pydantic field here so it's included in the serialized JSON.
    2. `securitySchemes` — parent types as `dict[str, SecurityScheme]`, which
       forces the OLD flat OpenAPI shape (type/name/in). Po expects the v1
       nested-key shape (apiKeySecurityScheme/...). Override to `dict[str, Any]`
       so we can pass the v1 dict through unchanged.
    """

    # Field names match A2A v1 JSON keys exactly (camelCase) — the SDK serializes them as-is.
    supportedInterfaces: list[dict[str, Any]] = Field(default_factory=list)  # noqa: N815
    securitySchemes: dict[str, Any] | None = None  # noqa: N815  # override parent's typed field


def make_agent_card(
    *,
    name: str,
    description: str,
    url: str,
    role: str,
    skills: list[AgentSkill],
    require_api_key: bool = True,
    streaming: bool = False,  # po-adk-python uses False; SDK then emits Tasks (not Messages) which PO requires
    version: str = "0.1.0",
) -> AgentCardV1:
    """Build an AgentCard with COIN + FHIR extensions, v1 shape ready for PO."""

    coin_ext = AgentExtensionV1(
        uri=COIN_EXTENSION_URI,
        description=(
            "Council Opinion Interchange Network — declares this agent participates in "
            "Council deliberations. The role parameter describes the agent's function."
        ),
        required=False,
        params={
            "role": role,
            "voteSchema": "concordant-plan-v1",
            "supportsRound2Refinement": True,
        },
    )

    fhir_ext = AgentExtensionV1(
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
        pushNotifications=False,
        stateTransitionHistory=False,  # v1 keeps the field but must be False
        extensions=[coin_ext, fhir_ext],
    )

    if require_api_key:
        security_schemes: dict[str, Any] | None = {
            "apiKey": {
                "apiKeySecurityScheme": {
                    "name": "X-API-Key",
                    "location": "header",  # Po backend uses "location", not "in"
                    "description": "API key required to access this agent.",
                }
            }
        }
        security: list[dict[str, list[str]]] | None = [{"apiKey": []}]
    else:
        security_schemes = None
        security = None

    return AgentCardV1(
        name=name,
        description=description,
        url=url,  # still required by installed a2a-sdk
        version=version,
        defaultInputModes=["text/plain"],
        defaultOutputModes=["text/plain"],
        capabilities=capabilities,
        supportedInterfaces=[
            {"url": url, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"},
        ],
        skills=skills,
        securitySchemes=security_schemes,
        security=security,
    )
