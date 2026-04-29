#!/usr/bin/env bash
# Deploy The Council to Cloud Run on the existing GCP trial project.
#
# Pre-requisites (one-time):
#   - gcloud CLI installed (we use the Homebrew path)
#   - gcloud auth login
#   - APIs enabled: Cloud Run, Cloud Build, Artifact Registry, Secret Manager
#   - Artifact Registry repo: us-central1-docker.pkg.dev/firm-plexus-363809/council
#   - Images built + pushed via Cloud Build (10 images at :latest)
#   - Service account: council-vertex@firm-plexus-363809.iam.gserviceaccount.com
#     with roles/aiplatform.user
#   - Secret Manager secrets: gcp-sa-key, supabase-url, supabase-service-role-key,
#     peer-api-key — accessible by the SA
#
# macOS bash 3.2 compatible — no associative arrays.

set -euo pipefail

GCLOUD=${GCLOUD:-/opt/homebrew/share/google-cloud-sdk/bin/gcloud}
PROJECT=firm-plexus-363809
SA=council-vertex@${PROJECT}.iam.gserviceaccount.com
REGISTRY=us-central1-docker.pkg.dev/${PROJECT}/council
MEMORY=1Gi
CPU=1
CONVENE_UI=https://council-health-ai-convene-ui.static.hf.space

# Per-service deploy region
region_for() {
  case "$1" in
    specialty-lens-mcp)  echo us-central1 ;;
    convener)            echo us-east1 ;;
    cardiology)          echo us-west1 ;;
    oncology)            echo us-east4 ;;
    nephrology)          echo us-south1 ;;
    endocrine)           echo europe-west1 ;;
    obstetrics)          echo europe-west4 ;;
    pediatrics)          echo us-east5 ;;
    psychiatry)          echo asia-northeast1 ;;
    anesthesia)          echo asia-southeast1 ;;
    *)                   echo us-central1 ;;
  esac
}

# Per-service Vertex region (env var GOOGLE_CLOUD_LOCATION) — same as deploy region
vertex_region_for() { region_for "$1"; }

# Convener stays warm; rest scale to zero
min_instances_for() {
  case "$1" in
    convener) echo 1 ;;
    *)        echo 0 ;;
  esac
}

# Map service short name to AGENT_MODULE for the agents (irrelevant for the MCP)
agent_module_for() {
  case "$1" in
    convener)    echo convener.app:a2a_app ;;
    cardiology)  echo cardiology_agent.app:a2a_app ;;
    oncology)    echo oncology_agent.app:a2a_app ;;
    nephrology)  echo nephrology_agent.app:a2a_app ;;
    endocrine)   echo endocrine_agent.app:a2a_app ;;
    obstetrics)  echo obstetrics_agent.app:a2a_app ;;
    pediatrics)  echo pediatrics_agent.app:a2a_app ;;
    psychiatry)  echo psychiatry_agent.app:a2a_app ;;
    anesthesia)  echo anesthesia_agent.app:a2a_app ;;
    *)           echo "" ;;
  esac
}

# Track URLs in a temp file (no associative arrays in bash 3.2)
URLS_FILE=$(mktemp)
trap 'rm -f "$URLS_FILE"' EXIT

url_for() {
  grep -E "^${1}=" "$URLS_FILE" 2>/dev/null | cut -d= -f2- | head -1
}

set_url() {
  echo "${1}=${2}" >> "$URLS_FILE"
}

deploy_one() {
  local name=$1
  # First-pass Cloud Build hit a bash variable-concatenation quirk that named
  # the images "<service>atest:latest" instead of "<service>:latest". Rather
  # than rebuild all 10, we point Cloud Run at the actual (oddly-named) image.
  local image="$REGISTRY/${name}atest:latest"
  local region=$(region_for "$name")
  local vertex_region=$(vertex_region_for "$name")
  local min_inst=$(min_instances_for "$name")

  echo ""
  echo "=== ${name} ==="
  echo "  region:        ${region}"
  echo "  vertex region: ${vertex_region}"
  echo "  min instances: ${min_inst}"

  # NOTE: PORT is reserved by Cloud Run — it auto-sets PORT=8080 by default.
  # We use --port=7860 below to keep our containers happy with their existing
  # EXPOSE 7860 / hardcoded uvicorn args.
  local env_vars="GOOGLE_CLOUD_PROJECT=${PROJECT}"
  env_vars="${env_vars},GOOGLE_CLOUD_LOCATION=${vertex_region}"
  env_vars="${env_vars},GOOGLE_GENAI_USE_VERTEXAI=true"
  env_vars="${env_vars},SENTRY_ENVIRONMENT=production"
  env_vars="${env_vars},FHIR_EXTENSION_URI=https://app.promptopinion.ai/schemas/a2a/v1/fhir-context"

  if [ "$name" != "specialty-lens-mcp" ]; then
    # All agent services
    env_vars="${env_vars},SERVICE_NAME=${name}"
    env_vars="${env_vars},GEMINI_MODEL=gemini-2.5-flash"
    env_vars="${env_vars},CONVENER_MODEL=gemini-2.5-flash"
    env_vars="${env_vars},CONVENE_UI_URL=${CONVENE_UI}"
    env_vars="${env_vars},AGENT_MODULE=$(agent_module_for "$name")"
    # MCP URL (set after MCP is deployed)
    local mcp_url=$(url_for specialty-lens-mcp)
    env_vars="${env_vars},MCP_URL=${mcp_url:-https://council-health-ai-specialty-lens-mcp.hf.space}/mcp"
    # Inject peer URLs (specialty agent URLs go to the Convener)
    for spec_key in cardiology oncology nephrology endocrine obstetrics pediatrics psychiatry anesthesia; do
      url=$(url_for "$spec_key")
      url=${url:-https://council-health-ai-${spec_key}.hf.space}
      case "$spec_key" in
        endocrine)  env_vars="${env_vars},ENDOCRINOLOGY_AGENT_URL=${url}" ;;
        pediatrics) env_vars="${env_vars},PEDIATRICS_AGENT_URL=${url}" ;;
        *)          env_vars="${env_vars},$(echo $spec_key | tr a-z A-Z)_AGENT_URL=${url}" ;;
      esac
    done
    local service_url_placeholder="https://${name}-XXXX.${region}.run.app"
    env_vars="${env_vars},SERVICE_URL=${service_url_placeholder}"
  else
    # MCP server
    env_vars="${env_vars},GEMINI_MODEL=gemini-2.5-flash"
    env_vars="${env_vars},SHARP_ENFORCE_403=true"
    # Placeholder — config.ts zod schema requires the field; Vertex path
    # ignores it in production. (config.ts will be relaxed in the next
    # rebuild but this lets us deploy from the current image.)
    env_vars="${env_vars},GEMINI_API_KEY=unused-vertex-only"
  fi

  $GCLOUD run deploy "$name" \
    --image="$image" \
    --region="$region" \
    --project="$PROJECT" \
    --service-account="$SA" \
    --memory="$MEMORY" \
    --cpu="$CPU" \
    --min-instances="$min_inst" \
    --max-instances=5 \
    --concurrency=80 \
    --port=7860 \
    --allow-unauthenticated \
    --set-env-vars="$env_vars" \
    --update-secrets="GCP_SA_KEY_JSON=gcp-sa-key:latest,SUPABASE_URL=supabase-url:latest,SUPABASE_SERVICE_ROLE_KEY=supabase-service-role-key:latest,API_KEY_PRIMARY=peer-api-key:latest,PEER_API_KEY=peer-api-key:latest" \
    --quiet 2>&1 | tail -3

  local url=$($GCLOUD run services describe "$name" --region="$region" --project="$PROJECT" --format='value(status.url)')
  set_url "$name" "$url"
  echo "  ✓ ${url}"
}

# Phase 1: deploy MCP first (no agent dependencies)
deploy_one specialty-lens-mcp

# Phase 2: deploy all 8 specialty agents (they only need the MCP URL — already known)
for s in cardiology oncology nephrology endocrine obstetrics pediatrics psychiatry anesthesia; do
  deploy_one "$s"
done

# Phase 3: deploy Convener with all peer URLs known
deploy_one convener

echo ""
echo "=== All 10 services deployed ==="
for s in specialty-lens-mcp convener cardiology oncology nephrology endocrine obstetrics pediatrics psychiatry anesthesia; do
  printf "%-22s %s\n" "$s" "$(url_for "$s")"
done

# Save URLs for the Convener registration step + future ops
{
  echo "# Cloud Run URLs (generated $(date -u +%FT%TZ))"
  for s in specialty-lens-mcp convener cardiology oncology nephrology endocrine obstetrics pediatrics psychiatry anesthesia; do
    echo "${s}=$(url_for "$s")"
  done
} > /Users/gharsallah/Desktop/Agents_Assemble/.env.cloudrun

echo ""
echo "Saved URLs to .env.cloudrun"
echo ""
echo "Next steps:"
echo "  1. Update PO External Agent → Convener URL = $(url_for convener)"
echo "  2. Test: ./po_consult.sh \"Consult with the Convener on this patient.\""
echo "  3. Pause HF Spaces once verified"
