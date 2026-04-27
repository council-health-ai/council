"""Tests for council_shared.fhir_hook — verify SHARP context extraction from A2A metadata."""

from __future__ import annotations

import os
from typing import ClassVar

os.environ.setdefault("GEMINI_API_KEY", "test-key")

from council_shared.fhir_hook import (
    _is_fhir_context_key,
    _walk_for_fhir,
    extract_fhir_context,
)


def test_is_fhir_context_key_matches_canonical_uri() -> None:
    assert _is_fhir_context_key("https://app.promptopinion.ai/schemas/a2a/v1/fhir-context")
    assert _is_fhir_context_key("https://app.promptopinion.ai/api/workspaces/abc/schemas/a2a/v1/fhir-context")


def test_is_fhir_context_key_rejects_unrelated() -> None:
    assert not _is_fhir_context_key("https://council-health.ai/schemas/a2a/v1/coin")
    assert not _is_fhir_context_key("Authorization")


def test_walk_for_fhir_finds_nested_dict() -> None:
    metadata = {
        "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context": {
            "fhirUrl": "https://fhir.example.org/r4",
            "fhirToken": "xyz",
            "patientId": "patient-42",
        }
    }
    found = _walk_for_fhir(metadata)
    assert found is not None
    assert found["fhirUrl"] == "https://fhir.example.org/r4"
    assert found["fhirToken"] == "xyz"


def test_walk_for_fhir_returns_none_when_absent() -> None:
    assert _walk_for_fhir({"unrelated": {"key": "value"}}) is None
    assert _walk_for_fhir(None) is None
    assert _walk_for_fhir("just a string") is None


class _FakeCallback:
    """Minimal stand-in for ADK's CallbackContext for unit testing extract_fhir_context."""

    def __init__(self, metadata: dict | None = None) -> None:
        self.metadata = metadata
        self.state: dict = {}
        self.run_config = None


class _FakeLlmRequest:
    contents: ClassVar[list] = []


def test_extract_fhir_context_lifts_into_state() -> None:
    ctx = _FakeCallback(metadata={
        "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context": {
            "fhirUrl": "https://fhir.example.org/r4",
            "fhirToken": "abc-123",
            "patientId": "patient-99",
        }
    })
    extract_fhir_context(ctx, _FakeLlmRequest())
    assert ctx.state["fhir_url"] == "https://fhir.example.org/r4"
    assert ctx.state["fhir_token"] == "abc-123"
    assert ctx.state["patient_id"] == "patient-99"


def test_extract_fhir_context_idempotent() -> None:
    ctx = _FakeCallback()
    ctx.state = {"fhir_url": "already-set", "fhir_token": "stay"}
    extract_fhir_context(ctx, _FakeLlmRequest())
    assert ctx.state["fhir_url"] == "already-set"
    assert ctx.state["fhir_token"] == "stay"


def test_extract_fhir_context_handles_missing_metadata() -> None:
    ctx = _FakeCallback(metadata=None)
    extract_fhir_context(ctx, _FakeLlmRequest())
    assert "fhir_url" not in ctx.state
