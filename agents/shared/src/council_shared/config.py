"""Centralized env config with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # Service identity (set per-agent via env; the agent's main passes its own name+url)
    service_name: str = field(default_factory=lambda: os.getenv("SERVICE_NAME", "council-agent"))
    service_url: str = field(default_factory=lambda: os.getenv("SERVICE_URL", "http://localhost:7860"))
    service_port: int = field(default_factory=lambda: int(os.getenv("PORT", "7860")))

    # LLM
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    convener_model: str = field(default_factory=lambda: os.getenv("CONVENER_MODEL", "gemini-2.5-pro"))

    # MCP server (the specialty-lens-mcp Hugging Face Space)
    mcp_url: str = field(
        default_factory=lambda: os.getenv(
            "MCP_URL", "https://council-health-ai-specialty-lens-mcp.hf.space/mcp"
        )
    )

    # FHIR extension URI used in A2A message metadata to encode SHARP context
    fhir_extension_uri: str = field(
        default_factory=lambda: os.getenv(
            "FHIR_EXTENSION_URI",
            "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context",
        )
    )

    # API key auth — accept multiple keys via API_KEYS=k1,k2 or singletons
    api_keys: tuple[str, ...] = field(default_factory=lambda: _load_api_keys())

    # Supabase
    supabase_url: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    supabase_service_role_key: str = field(default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""))

    # Sentry
    sentry_dsn: str = field(default_factory=lambda: os.getenv("SENTRY_DSN", ""))
    sentry_environment: str = field(default_factory=lambda: os.getenv("SENTRY_ENVIRONMENT", "development"))

    # Convener — peer agent base URLs (one per specialty). All on the council-health-ai HF org by convention.
    cardiology_url: str = field(
        default_factory=lambda: os.getenv("CARDIOLOGY_AGENT_URL", "https://council-health-ai-cardiology.hf.space")
    )
    oncology_url: str = field(
        default_factory=lambda: os.getenv("ONCOLOGY_AGENT_URL", "https://council-health-ai-oncology.hf.space")
    )
    nephrology_url: str = field(
        default_factory=lambda: os.getenv("NEPHROLOGY_AGENT_URL", "https://council-health-ai-nephrology.hf.space")
    )
    endocrinology_url: str = field(
        default_factory=lambda: os.getenv("ENDOCRINOLOGY_AGENT_URL", "https://council-health-ai-endocrine.hf.space")
    )
    obstetrics_url: str = field(
        default_factory=lambda: os.getenv("OBSTETRICS_AGENT_URL", "https://council-health-ai-obstetrics.hf.space")
    )
    pediatrics_url: str = field(
        default_factory=lambda: os.getenv("PEDIATRICS_AGENT_URL", "https://council-health-ai-pediatrics.hf.space")
    )
    psychiatry_url: str = field(
        default_factory=lambda: os.getenv("PSYCHIATRY_AGENT_URL", "https://council-health-ai-psychiatry.hf.space")
    )
    anesthesia_url: str = field(
        default_factory=lambda: os.getenv("ANESTHESIA_AGENT_URL", "https://council-health-ai-anesthesia.hf.space")
    )

    # Per-peer API key for outbound A2A calls (Convener authenticates to specialty agents)
    peer_api_key: str = field(default_factory=lambda: os.getenv("PEER_API_KEY", ""))


def _load_api_keys() -> tuple[str, ...]:
    keys: set[str] = set()
    raw = os.getenv("API_KEYS", "")
    if raw:
        keys.update(k.strip() for k in raw.split(",") if k.strip())
    for env_name in ("API_KEY_PRIMARY", "API_KEY_SECONDARY"):
        v = os.getenv(env_name, "").strip()
        if v:
            keys.add(v)
    return tuple(sorted(keys))


settings = Settings()
