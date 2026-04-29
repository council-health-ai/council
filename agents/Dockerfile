# Single Dockerfile for all 9 A2A agents (Convener + 8 specialty peers).
# AGENT_MODULE selects which agent runs at start time:
#   AGENT_MODULE=convener.app:a2a_app
#   AGENT_MODULE=cardiology_agent.app:a2a_app
#   ...
# HF Spaces runs the container as UID 1000 named `user`. We create that user
# first, drop privileges, and run all installs in $HOME/app.

FROM python:3.12-slim

# Create user + WORKDIR explicitly with ownership BEFORE dropping privileges.
# Cloud Build's WORKDIR-after-USER doesn't create the directory with the
# user's ownership the way HF Spaces' Docker daemon does, which makes
# `uv sync` fail with "Permission denied" creating .venv. mkdir+chown
# upfront is portable across both.
RUN useradd -m -u 1000 user \
    && mkdir -p /home/user/app \
    && chown -R user:user /home/user/app

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860 \
    AGENT_MODULE=convener.app:a2a_app

# Install uv as the runtime user
RUN pip install --no-cache-dir --user uv

WORKDIR $HOME/app

# Workspace files
COPY --chown=user:user pyproject.toml ./pyproject.toml
COPY --chown=user:user shared ./shared
COPY --chown=user:user convener ./convener
COPY --chown=user:user cardiology-agent ./cardiology-agent
COPY --chown=user:user oncology-agent ./oncology-agent
COPY --chown=user:user nephrology-agent ./nephrology-agent
COPY --chown=user:user endocrine-agent ./endocrine-agent
COPY --chown=user:user obstetrics-agent ./obstetrics-agent
COPY --chown=user:user pediatrics-agent ./pediatrics-agent
COPY --chown=user:user psychiatry-agent ./psychiatry-agent
COPY --chown=user:user anesthesia-agent ./anesthesia-agent

# Install all workspace members
RUN uv sync --all-packages --no-dev

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:7860/healthz', timeout=3)" || exit 1

# AGENT_MODULE is overridden per Space via HF Variables
CMD ["sh", "-c", "uv run uvicorn $AGENT_MODULE --host 0.0.0.0 --port $PORT --log-level info"]
