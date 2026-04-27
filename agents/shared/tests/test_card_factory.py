"""Tests for council_shared.card_factory — verify Agent Card shape, COIN extension, and security scheme."""

from __future__ import annotations

import os

# Stub env vars so config.Settings dataclass doesn't reach for missing values.
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("SERVICE_URL", "http://example.invalid")

from a2a.types import AgentSkill
from council_shared.card_factory import COIN_EXTENSION_URI, make_agent_card


def _skill() -> AgentSkill:
    return AgentSkill(
        id="test_skill",
        name="Test Skill",
        description="A test skill.",
        tags=["test"],
        examples=["Test {patient_id}."],
    )


def test_make_agent_card_returns_a_valid_card() -> None:
    card = make_agent_card(
        name="cardiology-agent",
        description="Test card.",
        url="https://council-health-ai-cardiology.hf.space",
        role="cardiology",
        skills=[_skill()],
    )
    assert card.name == "cardiology-agent"
    assert card.url == "https://council-health-ai-cardiology.hf.space"
    assert card.preferred_transport == "JSONRPC"
    assert card.protocol_version == "0.3.0"


def test_card_declares_coin_extension() -> None:
    card = make_agent_card(
        name="cardiology-agent",
        description="Test card.",
        url="https://example.invalid",
        role="cardiology",
        skills=[_skill()],
    )
    extension_uris = [ext.uri for ext in (card.capabilities.extensions or [])]
    assert COIN_EXTENSION_URI in extension_uris


def test_card_declares_fhir_context_extension() -> None:
    card = make_agent_card(
        name="cardiology-agent",
        description="Test card.",
        url="https://example.invalid",
        role="cardiology",
        skills=[_skill()],
    )
    extension_uris = [ext.uri for ext in (card.capabilities.extensions or [])]
    assert any("fhir-context" in uri for uri in extension_uris)


def test_card_with_api_key_security() -> None:
    card = make_agent_card(
        name="cardiology-agent",
        description="Test card.",
        url="https://example.invalid",
        role="cardiology",
        skills=[_skill()],
        require_api_key=True,
    )
    assert card.security_schemes is not None
    assert "apiKey" in card.security_schemes
    assert card.security == [{"apiKey": []}]


def test_card_without_api_key() -> None:
    card = make_agent_card(
        name="public-agent",
        description="Test card.",
        url="https://example.invalid",
        role="convener",
        skills=[_skill()],
        require_api_key=False,
    )
    assert card.security_schemes is None
    assert card.security is None


def test_capabilities_streaming_default_on() -> None:
    card = make_agent_card(
        name="cardiology-agent",
        description="Test card.",
        url="https://example.invalid",
        role="cardiology",
        skills=[_skill()],
    )
    assert card.capabilities.streaming is True
    assert card.capabilities.push_notifications is False
    assert card.capabilities.state_transition_history is False
