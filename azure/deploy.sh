#!/usr/bin/env bash
# MITRE ATT&CK Threat Analyzer — Code deployment
#
# Builds the Docker image, pushes it to ACR, and updates the Container App.
# Frontend is bundled into the Docker image (multi-stage build) — no separate step needed.
#
# Reads resource info from .deploy-state.json written by setup.sh.
# Run setup.sh once first to provision Azure resources.
#
# Usage: bash azure/deploy.sh

set -euo pipefail

# ======================================================================
# Paths + config
# ======================================================================

# Timestamp tag ensures each push creates a unique image ref,
# which forces Azure Container Apps to create a new revision.
IMAGE_TAG=$(date +%Y%m%d%H%M%S)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$SCRIPT_DIR/deploy.config"
STATE_FILE="$SCRIPT_DIR/.deploy-state.json"

# Load resource names from deploy.config (no secrets)
[ -f "$CONFIG_FILE" ] || fail "azure/deploy.config not found. Edit it with your resource names."
# shellcheck source=deploy.config
source "$CONFIG_FILE"

# ======================================================================
# Logging — tee all output (stdout + stderr) to a timestamped log file
# ======================================================================

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy-${IMAGE_TAG}.log"
exec > >(tee "$LOG_FILE") 2>&1
echo "[deploy] Log file: $LOG_FILE"

# ======================================================================
# Helpers
# ======================================================================

log()  { echo -e "\033[36m[deploy] $1\033[0m"; }
ok()   { echo -e "\033[32m[ok]     $1\033[0m"; }
fail() { echo -e "\033[31m[error]  $1\033[0m"; exit 1; }

# ======================================================================
# Prerequisites
# ======================================================================

for cmd in az docker jq; do
    command -v "$cmd" > /dev/null 2>&1 || fail "'$cmd' not found. Install: sudo apt-get install $cmd"
done

[ -f "$STATE_FILE" ] || fail ".deploy-state.json not found. Run setup.sh first to provision Azure resources."

# ======================================================================
# Load state + credentials
# ======================================================================

RESOURCE_GROUP=$(jq -r '.ResourceGroup'    "$STATE_FILE")
ACR_NAME=$(jq -r '.AcrName'               "$STATE_FILE")
ACR_LOGIN_SERVER=$(jq -r '.AcrLoginServer' "$STATE_FILE")
ACA_NAME=$(jq -r '.AcaName'               "$STATE_FILE")
BACKEND_URL=$(jq -r '.BackendUrl'          "$STATE_FILE")

# Read Azure OpenAI credentials from .env.local.
# Re-applied on every deploy to prevent env vars from drifting after
# multiple 'az containerapp update' calls.
ENV_FILE="$PROJECT_ROOT/.env.local"
[ -f "$ENV_FILE" ] || fail ".env.local not found at $ENV_FILE"

read_env_var() {
    local file="$1" key="$2" line val
    line=$(grep -E "^${key}=" "$file" | head -1)
    val="${line#*=}"          # strip key= prefix (handles values containing =)
    val="${val#\"}" ; val="${val%\"}"   # strip surrounding double quotes
    val="${val#\'}" ; val="${val%\'}"   # strip surrounding single quotes
    echo "$val"
}

AOAI_ENDPOINT=$(read_env_var    "$ENV_FILE" "AZURE_OPENAI_ENDPOINT")
AOAI_DEPLOYMENT=$(read_env_var  "$ENV_FILE" "AZURE_OPENAI_DEPLOYMENT")
SQL_ADMIN_LOGIN=$(read_env_var  "$ENV_FILE" "SQL_ADMIN_LOGIN")
SQL_ADMIN_PASSWORD=$(read_env_var "$ENV_FILE" "SQL_ADMIN_PASSWORD")

[ -z "$AOAI_ENDPOINT" ]      && fail "AZURE_OPENAI_ENDPOINT not set in $ENV_FILE"
[ -z "$AOAI_DEPLOYMENT" ]    && fail "AZURE_OPENAI_DEPLOYMENT not set in $ENV_FILE"
[ -z "$SQL_ADMIN_LOGIN" ]    && fail "SQL_ADMIN_LOGIN not set in $ENV_FILE"
[ -z "$SQL_ADMIN_PASSWORD" ] && fail "SQL_ADMIN_PASSWORD not set in $ENV_FILE"

# Azure SQL — names from deploy.config (SQL_SERVER_NAME, SQL_DB_NAME)
SQL_FQDN="${SQL_SERVER_NAME}.database.windows.net"
DB_URL="mssql+pyodbc://${SQL_ADMIN_LOGIN}:${SQL_ADMIN_PASSWORD}@${SQL_FQDN}/${SQL_DB_NAME}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30"

log "Project root  : $PROJECT_ROOT"
log "Resource group: $RESOURCE_GROUP"
log "App URL       : $BACKEND_URL  (serves frontend + API)"

# ======================================================================
# Step 1 -- Azure login check
# ======================================================================

log "Checking Azure login..."
if ! az account show --query "name" -o tsv > /dev/null 2>&1; then
    fail "Not logged in to Azure. Run 'az login' first, then re-run this script."
fi
ok "Logged in: $(az account show --query "name" -o tsv)"

# ======================================================================
# Step 2 -- Build and push Docker image to ACR
# ======================================================================

FULL_IMAGE="$ACR_LOGIN_SERVER/mitre-analyzer:$IMAGE_TAG"

log "Logging in to ACR '$ACR_NAME'..."
az acr login --name "$ACR_NAME" || fail "ACR login failed."

log "Building Docker image (linux/amd64)..."
docker build --platform linux/amd64 --progress=plain --tag "$FULL_IMAGE" "$PROJECT_ROOT" \
    || fail "docker build failed."

log "Pushing image: $FULL_IMAGE"
docker push "$FULL_IMAGE" || fail "docker push failed."
ok "Image pushed."

# ======================================================================
# Step 3 -- Upsert Container App secrets (idempotent)
# ======================================================================

log "Upserting Container App secrets..."
az containerapp secret set \
    --name "$ACA_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --secrets "db-url=$DB_URL" \
    --output none \
    || fail "Secret upsert failed."
ok "Secrets upserted."

# ======================================================================
# Step 4 -- Update Container App to use the new image
# ======================================================================

log "Updating Container App '$ACA_NAME' with new image + env vars..."
# Set ALL env vars on every deploy — az containerapp update --set-env-vars
# is a replace operation, so any var omitted here will be dropped.
# Secret values are referenced by name (secretref:*); the secrets themselves
# were created by setup.sh and persist across deploys.
az containerapp update \
    --name "$ACA_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$FULL_IMAGE" \
    --set-env-vars \
        "AZURE_OPENAI_ENDPOINT=$AOAI_ENDPOINT" \
        "AZURE_OPENAI_DEPLOYMENT=$AOAI_DEPLOYMENT" \
        "AZURE_OPENAI_API_KEY=secretref:aoai-key" \
        "DATABASE_URL=secretref:db-url" \
        "DEBUG=false" \
        "STIX_DATA_DIR=/app/data/stix" \
        "SYNC_INTERVAL_HOURS=24" \
    --output none \
    || fail "Container App update failed."
ok "Container App updated."

# ======================================================================
# Step 5 -- Post-deployment verification
#
# Checks (in order):
#   1. Container service health  — GET /api/v1/health
#   2. Database connectivity     — GET /api/v1/tactics (count > 0)
#   3. STIX data sync status     — GET /api/v1/sync/status
#
# On failure, prints the exact 'az containerapp logs' command to debug.
# ======================================================================

log "Step 5: Post-deployment verification..."

# ── 1. Container health (wait up to 120 s for new revision) ────────────
log "  [1/3] Waiting for container service to be healthy..."
MAX_WAIT=120
INTERVAL=5
elapsed=0
HTTP_STATUS="000"
while [ "$elapsed" -lt "$MAX_WAIT" ]; do
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 \
        "$BACKEND_URL/api/v1/health" 2>/dev/null || echo "000")
    if [ "$HTTP_STATUS" = "200" ]; then
        ok "  [1/3] Container service: HEALTHY (HTTP 200)"
        break
    fi
    echo "        waiting... (${elapsed}s / ${MAX_WAIT}s, HTTP $HTTP_STATUS)"
    sleep "$INTERVAL"
    elapsed=$((elapsed + INTERVAL))
done

if [ "$HTTP_STATUS" != "200" ]; then
    fail "  [1/3] Container did not become healthy after ${MAX_WAIT}s (last HTTP: $HTTP_STATUS).
       Debug logs:
         az containerapp logs show --name $ACA_NAME --resource-group $RESOURCE_GROUP --tail 80 --format text
         az containerapp logs show --name $ACA_NAME --resource-group $RESOURCE_GROUP --follow --format text"
fi

# ── 2. Database connectivity (expect at least 1 tactic) ────────────────
log "  [2/3] Checking database connectivity..."
TACTICS_RESP=$(curl -s --max-time 10 "$BACKEND_URL/api/v1/tactics" 2>/dev/null || echo '{"count":0}')
TACTICS_COUNT=$(echo "$TACTICS_RESP" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('count',0))" 2>/dev/null || echo "0")

if [ "${TACTICS_COUNT:-0}" -gt 0 ] 2>/dev/null; then
    ok "  [2/3] Database: OK ($TACTICS_COUNT tactics loaded)"
else
    log "  [2/3] Database appears empty (tactics=0). STIX sync may still be running."
    log "        (If this is a fresh deploy, the sync runs automatically — check step 3)"
fi

# ── 3. STIX sync status ────────────────────────────────────────────────
log "  [3/3] Checking STIX data sync status..."
SYNC_RESP=$(curl -s --max-time 10 "$BACKEND_URL/api/v1/sync/status" 2>/dev/null || echo '{}')
SYNC_STATUS=$(echo "$SYNC_RESP" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")

case "$SYNC_STATUS" in
    success)
        T=$(echo "$SYNC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tactics_count',0))" 2>/dev/null)
        K=$(echo "$SYNC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('techniques_count',0))" 2>/dev/null)
        M=$(echo "$SYNC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('mitigations_count',0))" 2>/dev/null)
        ok "  [3/3] STIX sync: SUCCESS ($T tactics, $K techniques, $M mitigations)"
        ;;
    running)
        log "  [3/3] STIX sync still running — poll until done:"
        log "        curl -s $BACKEND_URL/api/v1/sync/status | python3 -m json.tool"
        ;;
    error|failed)
        ERR=$(echo "$SYNC_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error_message') or '')" 2>/dev/null)
        log "  [3/3] STIX sync FAILED: ${ERR}"
        log "        Re-trigger: curl -X POST $BACKEND_URL/api/v1/sync/trigger"
        log "        Debug logs: az containerapp logs show --name $ACA_NAME --resource-group $RESOURCE_GROUP --tail 100 --format text"
        ;;
    *)
        log "  [3/3] Sync status: '${SYNC_STATUS}' (no record yet — DB empty or container just started)"
        log "        Trigger manually: curl -X POST $BACKEND_URL/api/v1/sync/trigger"
        ;;
esac

# ======================================================================
# Summary
# NOTE: Frontend is bundled into the Docker image (multi-stage build).
# ======================================================================

echo ""
echo -e "\033[32m====================================================\033[0m"
echo -e "\033[32m  Deployment complete!\033[0m"
echo -e "\033[32m====================================================\033[0m"
echo -e "  App (frontend + API): \033[36m$BACKEND_URL\033[0m"
echo ""
echo "  Health check : $BACKEND_URL/api/v1/health"
echo "  Sync status  : $BACKEND_URL/api/v1/sync/status"
echo "  Sync trigger : POST $BACKEND_URL/api/v1/sync/trigger"
echo ""
echo "  Debug logs (stream):  az containerapp logs show --name $ACA_NAME --resource-group $RESOURCE_GROUP --follow --format text"
echo "  Debug logs (history): az containerapp logs show --name $ACA_NAME --resource-group $RESOURCE_GROUP --tail 100 --format text"
echo ""
echo "  Log saved to : $LOG_FILE"
echo ""
