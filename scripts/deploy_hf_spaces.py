"""Deploy The Council to Hugging Face Spaces — 1 MCP server + 9 A2A agents.

Reads /Users/gharsallah/Desktop/Agents_Assemble/.env.local for credentials.
Creates each HF Space (idempotent), sets secrets + env vars, then uploads code.

Run:
    python scripts/deploy_hf_spaces.py

This is idempotent — repeated runs update existing Spaces in place.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from dotenv import dotenv_values
from huggingface_hub import HfApi

# ─── config ────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_LOCAL = REPO_ROOT.parent / ".env.local"
DEPLOY_ROOT = REPO_ROOT / ".deploy"

ORG = "council-health-ai"


def hf_url(name: str) -> str:
    return f"https://{ORG}-{name}.hf.space"


# Specialty → URL map (precomputed; HF Space URLs are deterministic from owner+name)
PEER_URLS = {
    "convener": hf_url("convener"),
    "cardiology": hf_url("cardiology"),
    "oncology": hf_url("oncology"),
    "nephrology": hf_url("nephrology"),
    "endocrine": hf_url("endocrine"),
    "obstetrics": hf_url("obstetrics"),
    "pediatrics": hf_url("pediatrics"),
    "psychiatry": hf_url("psychiatry"),
    "anesthesia": hf_url("anesthesia"),
}
MCP_URL = hf_url("specialty-lens-mcp") + "/mcp"

EMOJI_BY_NAME = {
    "specialty-lens-mcp": "🩺",
    "convener": "🏛️",
    "cardiology": "❤️",
    "oncology": "🎗️",
    "nephrology": "💧",
    "endocrine": "🧬",
    "obstetrics": "🤰",
    "pediatrics": "👶",
    "psychiatry": "🧠",
    "anesthesia": "💉",
}


# ─── helpers ───────────────────────────────────────────────────────────


def load_env() -> dict[str, str]:
    if not ENV_LOCAL.exists():
        sys.exit(f"Missing {ENV_LOCAL} — fill it from .env.template first")
    raw = dotenv_values(ENV_LOCAL)
    return {k: v for k, v in raw.items() if v}


def write_readme(deploy_dir: Path, *, title: str, emoji: str, blurb: str, app_port: int = 7860) -> None:
    body = f"""---
title: {title}
emoji: {emoji}
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: {app_port}
pinned: false
license: mit
---

# {title}

{blurb}

Part of [The Council](https://github.com/{ORG}/council) — an A2A peer-agent network for multi-specialty deliberation on multi-morbid patients. Submitted to Prompt Opinion's *Agents Assemble — The Healthcare AI Endgame* hackathon, May 2026.

## What this Space is

{blurb}

## Endpoints

- `POST /mcp` (or `/`) — A2A / MCP traffic
- `GET /healthz` — service liveness
- `GET /.well-known/agent-card.json` — A2A v1 Agent Card (for agents)
- `GET /.well-known/agent.json` — v0 backcompat path

## Source

Repository: <https://github.com/{ORG}/council>
"""
    (deploy_dir / "README.md").write_text(body)


def stage_mcp(env: dict[str, str]) -> Path:
    """Stage the specialty-lens-mcp deploy bundle."""
    target = DEPLOY_ROOT / "specialty-lens-mcp"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    src = REPO_ROOT / "packages/specialty-lens-mcp"
    for entry in src.iterdir():
        if entry.name in {"node_modules", "dist", "coverage", ".turbo", ".env", ".env.local"}:
            continue
        dst = target / entry.name
        if entry.is_dir():
            shutil.copytree(entry, dst)
        else:
            shutil.copy2(entry, dst)

    write_readme(
        target,
        title="Council Health AI — Specialty Lens MCP",
        emoji=EMOJI_BY_NAME["specialty-lens-mcp"],
        blurb=(
            "SHARP-on-MCP TypeScript server exposing 8 healthcare specialty lenses "
            "(`get_<specialty>_perspective`) plus 2 concordance tools "
            "(`get_council_conflict_matrix`, `get_concordance_brief`). "
            "Real HTTP 403 enforcement on missing FHIR context — none of the three "
            "reference impls in po-community-mcp do this."
        ),
    )
    return target


def stage_agent(name: str, blurb: str) -> Path:
    """Stage an agent deploy bundle. Each Space gets the entire agents/ tree (Dockerfile picks AGENT_MODULE)."""
    target = DEPLOY_ROOT / name
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    src = REPO_ROOT / "agents"
    for entry in src.iterdir():
        if entry.name in {".venv", "__pycache__", ".env", "uv.lock", ".gitignore"}:
            continue
        dst = target / entry.name
        if entry.is_dir():
            shutil.copytree(entry, dst, ignore=shutil.ignore_patterns(
                "__pycache__", "*.egg-info", ".pytest_cache", ".ruff_cache", "node_modules"
            ))
        else:
            shutil.copy2(entry, dst)

    write_readme(target, title=f"Council Health AI — {name.title()} Agent", emoji=EMOJI_BY_NAME[name], blurb=blurb)
    return target


def common_secrets(env: dict[str, str]) -> dict[str, str]:
    return {
        "GEMINI_API_KEY": env["GEMINI_API_KEY"],
        "SUPABASE_URL": env["SUPABASE_URL"],
        "SUPABASE_SERVICE_ROLE_KEY": env["SUPABASE_SERVICE_ROLE_KEY"],
    }


def mcp_secrets(env: dict[str, str]) -> dict[str, str]:
    return {
        **common_secrets(env),
        "SENTRY_DSN": env.get("SENTRY_DSN_MCP", ""),
    }


def agent_secrets(env: dict[str, str], *, peer_api_key: str) -> dict[str, str]:
    if not peer_api_key:
        sys.exit("PEER_API_KEY missing in env — generate one and add to .env.local")
    return {
        **common_secrets(env),
        "SENTRY_DSN": env.get("SENTRY_DSN_AGENTS", ""),
        "API_KEY_PRIMARY": peer_api_key,
        "PEER_API_KEY": peer_api_key,
    }


def agent_env(name: str) -> dict[str, str]:
    """Per-Space non-secret env vars (used in HF Spaces' Variables tab)."""
    module_name = name.replace("-", "_")
    if name == "convener":
        agent_module = "convener.app:a2a_app"
    else:
        agent_module = f"{module_name}_agent.app:a2a_app"
    return {
        "AGENT_MODULE": agent_module,
        "SERVICE_NAME": name,
        "SERVICE_URL": hf_url(name),
        "MCP_URL": MCP_URL,
        "PORT": "7860",
        "GEMINI_MODEL": "gemini-2.5-flash",
        "CONVENER_MODEL": "gemini-2.5-flash",
        "FHIR_EXTENSION_URI": (
            "https://app.promptopinion.ai/schemas/a2a/v1/fhir-context"
        ),
        # Peer URLs — used by Convener for fan-out; harmless on specialty agents
        "CARDIOLOGY_AGENT_URL": PEER_URLS["cardiology"],
        "ONCOLOGY_AGENT_URL": PEER_URLS["oncology"],
        "NEPHROLOGY_AGENT_URL": PEER_URLS["nephrology"],
        "ENDOCRINOLOGY_AGENT_URL": PEER_URLS["endocrine"],
        "OBSTETRICS_AGENT_URL": PEER_URLS["obstetrics"],
        "PEDIATRICS_AGENT_URL": PEER_URLS["pediatrics"],
        "PSYCHIATRY_AGENT_URL": PEER_URLS["psychiatry"],
        "ANESTHESIA_AGENT_URL": PEER_URLS["anesthesia"],
    }


# ─── deploy ────────────────────────────────────────────────────────────


def deploy_one(api: HfApi, *, name: str, local_path: Path, secrets: dict[str, str], variables: dict[str, str]) -> None:
    repo_id = f"{ORG}/{name}"
    print(f"\n=== {repo_id} ===")
    print("  → create_repo(exist_ok=True)")
    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="docker", exist_ok=True)

    print(f"  → setting {len(secrets)} secrets")
    for key, value in secrets.items():
        if not value:
            continue
        api.add_space_secret(repo_id=repo_id, key=key, value=value)

    print(f"  → setting {len(variables)} variables")
    for key, value in variables.items():
        api.add_space_variable(repo_id=repo_id, key=key, value=value)

    print(f"  → uploading {local_path.relative_to(REPO_ROOT)} → space repo")
    api.upload_folder(
        folder_path=str(local_path),
        repo_id=repo_id,
        repo_type="space",
        commit_message="deploy: council scaffold",
    )
    print(f"  ✓ deployed: {hf_url(name)}")


def main() -> int:
    env = load_env()
    hf_token = env.get("HF_TOKEN") or os.getenv("HF_TOKEN")
    if not hf_token:
        sys.exit("Missing HF_TOKEN")

    api = HfApi(token=hf_token)
    DEPLOY_ROOT.mkdir(exist_ok=True)

    # ── MCP server ─────────────────────────────────────────────────────
    mcp_path = stage_mcp(env)
    deploy_one(
        api,
        name="specialty-lens-mcp",
        local_path=mcp_path,
        secrets=mcp_secrets(env),
        variables={
            "PORT": "7860",
            "GEMINI_MODEL": "gemini-2.5-flash",
            "SHARP_ENFORCE_403": "true",
            "SENTRY_ENVIRONMENT": "production",
        },
    )

    # ── 9 A2A agents ───────────────────────────────────────────────────
    agent_blurbs = {
        "convener": "Convener agent — facilitates The Council's peer A2A deliberation. Issues Round 1 to all 8 specialty peers, synthesizes the conflict matrix, issues Round 2 to involved specialties, and emits the ConcordantPlan.",
        "cardiology": "Cardiology specialty agent — A2A peer in The Council. Cardiac safety, anticoagulation strategy, QT risk, renal-cleared cardiac drug dosing.",
        "oncology": "Oncology specialty agent — A2A peer in The Council. ER/PR/HER2-driven therapy choice, comorbidity-aware regimens, drug-drug interactions.",
        "nephrology": "Nephrology specialty agent — A2A peer in The Council. eGFR-trended renal dosing, fluid/electrolyte management, CKD-progression-aware monitoring.",
        "endocrine": "Endocrinology specialty agent — A2A peer in The Council. Diabetes management with individualized targets, thyroid/adrenal/pituitary, SGLT2i/GLP-1RA decisions.",
        "obstetrics": "Obstetrics + MFM specialty agent — A2A peer in The Council. Pregnancy-specific medication safety, hypertensive and diabetic disorders of pregnancy, VTE prophylaxis.",
        "pediatrics": "Developmental pediatrics specialty agent — A2A peer in The Council. Syndromic protocol awareness, weight-based pediatric dosing, behavioral comorbidity, transitions of care.",
        "psychiatry": "Psychiatry specialty agent — A2A peer in The Council. Psychotropic interactions, anticholinergic burden, QT-prolonging psychotropics, suicide risk awareness.",
        "anesthesia": "Anesthesia + perioperative specialty agent — A2A peer in The Council. ASA/RCRI risk, perioperative anticoagulation, OSA, postop strategy.",
    }

    peer_api_key = env.get("PEER_API_KEY", "")
    for name, blurb in agent_blurbs.items():
        path = stage_agent(name, blurb)
        deploy_one(
            api,
            name=name,
            local_path=path,
            secrets=agent_secrets(env, peer_api_key=peer_api_key),
            variables=agent_env(name),
        )

    print("\n✅ All 10 Spaces deployed. Builds will start in HF; check progress at:")
    for name in ["specialty-lens-mcp", *agent_blurbs.keys()]:
        print(f"  https://huggingface.co/spaces/{ORG}/{name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
