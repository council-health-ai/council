"""Shared library for The Council's A2A agents.

Exports the building blocks every specialty agent + the Convener uses:
- create_a2a_app: Starlette app factory that serves Agent Card at v0 + v1 paths
- make_agent_card: AgentCard builder with COIN extension declared
- extract_fhir_context: ADK before_model_callback that lifts SHARP metadata into tool_context.state
- call_mcp_tool: async MCP client that forwards SHARP headers
- audit: Supabase audit log helpers
- build_specialty_agent / make_specialty_a2a_app: factories that build any of the 8 specialty agents
"""

from .app_factory import create_a2a_app
from .audit import (
    close_session,
    open_session,
    record_agent_message,
    record_audit_event,
    record_tool_call,
)
from .card_factory import COIN_EXTENSION_URI, make_agent_card
from .config import settings
from .fhir_hook import extract_fhir_context
from .mcp_client import MCP_BASE_URL, call_mcp_tool
from .middleware import ApiKeyMiddleware, get_default_api_keys
from .models import (
    Brief,
    BriefPlan,
    ConcordantPlan,
    ConflictMatrix,
    ProposedPlan,
    Specialty,
    SpecialtyView,
)
from .specialty_agent import build_specialty_agent
from .specialty_app import make_specialty_a2a_app

__all__ = [
    "COIN_EXTENSION_URI",
    "MCP_BASE_URL",
    "ApiKeyMiddleware",
    "Brief",
    "BriefPlan",
    "ConcordantPlan",
    "ConflictMatrix",
    "ProposedPlan",
    "Specialty",
    "SpecialtyView",
    "build_specialty_agent",
    "call_mcp_tool",
    "close_session",
    "create_a2a_app",
    "extract_fhir_context",
    "get_default_api_keys",
    "make_agent_card",
    "make_specialty_a2a_app",
    "open_session",
    "record_agent_message",
    "record_audit_event",
    "record_tool_call",
    "settings",
]
