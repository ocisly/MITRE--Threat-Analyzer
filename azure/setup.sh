#!/usr/bin/env bash
# MITRE ATT&CK Threat Analyzer — One-time Azure resource provisioning
#
# Creates all Azure resources using az CLI (no Bicep).
# Run this ONCE before the first deployment.
# Saves generated resource info (login server, app URL) to .deploy-state.json
# for deploy.sh to read.
#
# Prerequisites:
#   1. az CLI installed and logged in  →  az login
#   2. Resource group already exists  →  az group create --name <rg> --location <loc>
#   3. azure/deploy.config edited with your resource names
#   4. .env.local filled in (copy from .env.example)
#
# Usage: bash azure/setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$SCRIPT_DIR/deploy.config"
STATE_FILE="$SCRIPT_DIR/.deploy-state.json"
ENV_FILE="$PROJECT_ROOT/.env.local"

# ======================================================================
# Helpers
# ======================================================================

log()  { echo -e "\033[36m[setup]  $1\033[0m"; }
ok()   { echo -e "\033[32m[ok]     $1\033[0m"; }
warn() { echo -e "\033[33m[warn]   $1\033[0m"; }
step() { echo -e "\n\033[37m--- Step $1 : $2 ---\033[0m"; }
fail() { echo -e "\033[31m[error]  $1\033[0m"; exit 1; }

read_dot_env() {
    local file="$1"
    [ -f "$file" ] || return 0
    while IFS= read -r line; do
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue
        if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local val="${BASH_REMATCH[2]}"
            val="${val#\"}" ; val="${val%\"}"
            val="${val#\'}" ; val="${val%\'}"
            export "$key=$val"
        fi
    done < "$file"
}

# ======================================================================
# Load resource config (no secrets)
# ======================================================================

[ -f "$CONFIG_FILE" ] || fail "azure/deploy.config not found. Copy and edit it before running setup."
# shellcheck source=deploy.config
source "$CONFIG_FILE"

# ======================================================================
# Load credentials from .env.local
# ======================================================================

[ -f "$ENV_FILE" ] || fail ".env.local not found at $PROJECT_ROOT. Copy .env.example → .env.local and fill in your credentials."
read_dot_env "$ENV_FILE"

AOAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-}"
AOAI_DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-}"
AOAI_API_KEY="${AZURE_OPENAI_API_KEY:-}"
SQL_ADMIN_LOGIN="${SQL_ADMIN_LOGIN:-}"
SQL_ADMIN_PASSWORD="${SQL_ADMIN_PASSWORD:-}"

[ -z "$AOAI_ENDPOINT" ]      && fail "AZURE_OPENAI_ENDPOINT not set in .env.local"
[ -z "$AOAI_DEPLOYMENT" ]    && fail "AZURE_OPENAI_DEPLOYMENT not set in .env.local"
[ -z "$AOAI_API_KEY" ]       && fail "AZURE_OPENAI_API_KEY not set in .env.local"
[ -z "$SQL_ADMIN_LOGIN" ]    && fail "SQL_ADMIN_LOGIN not set in .env.local"
[ -z "$SQL_ADMIN_PASSWORD" ] && fail "SQL_ADMIN_PASSWORD not set in .env.local"

# ======================================================================
# Azure login check  (run 'az login' before this script)
# ======================================================================

log "Checking Azure login..."
if ! az account show --query "name" -o tsv > /dev/null 2>&1; then
    fail "Not logged in to Azure. Run 'az login' first, then re-run this script."
fi
ACCT=$(az account show --query "name" -o tsv)
ok "Logged in as: $ACCT"

log "Resource group : $RESOURCE_GROUP"
log "Location       : $LOCATION"

# Verify resource group exists
az group show --name "$RESOURCE_GROUP" --output none 2>/dev/null \
    || fail "Resource group '$RESOURCE_GROUP' not found. Create it first:
       az group create --name $RESOURCE_GROUP --location $LOCATION"

# ======================================================================
# Step 1 -- Azure Container Registry
# ======================================================================

step 1 "Azure Container Registry ($ACR_NAME)"
az acr create \
    --name "$ACR_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --sku Basic \
    --location "$LOCATION" \
    --admin-enabled true \
    --output none
ok "ACR created."

ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query "loginServer" -o tsv)
ACR_PWD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
log "ACR login server: $ACR_LOGIN_SERVER"

# ======================================================================
# Step 2 -- Container Apps Environment
# ======================================================================

step 2 "Container Apps Environment ($ACA_ENV_NAME)"
log "This creates a Log Analytics workspace automatically (~2 min)..."
az containerapp env create \
    --name "$ACA_ENV_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none
ok "Container Apps Environment created."

# ======================================================================
# Step 3 -- Azure SQL Server + Database (Serverless)
# ======================================================================

step 3 "Azure SQL Server ($SQL_SERVER_NAME)"
az sql server create \
    --name "$SQL_SERVER_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --admin-user "$SQL_ADMIN_LOGIN" \
    --admin-password "$SQL_ADMIN_PASSWORD" \
    --output none

# Allow Azure services (e.g. ACA) to reach the SQL server
az sql server firewall-rule create \
    --server "$SQL_SERVER_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --name AllowAzureServices \
    --start-ip-address 0.0.0.0 \
    --end-ip-address 0.0.0.0 \
    --output none
ok "SQL Server created."

step 3 "SQL Database Serverless ($SQL_DB_NAME, GP_S_Gen5_1)"
az sql db create \
    --server "$SQL_SERVER_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --name "$SQL_DB_NAME" \
    --edition GeneralPurpose \
    --family Gen5 \
    --capacity 1 \
    --compute-model Serverless \
    --auto-pause-delay 60 \
    --min-capacity 0.5 \
    --output none
ok "SQL Database created."

SQL_FQDN=$(az sql server show \
    --name "$SQL_SERVER_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "fullyQualifiedDomainName" -o tsv)

DB_URL="mssql+pyodbc://${SQL_ADMIN_LOGIN}:${SQL_ADMIN_PASSWORD}@${SQL_FQDN}/${SQL_DB_NAME}?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30"

# ======================================================================
# Step 4 -- Container App (placeholder image, env vars configured)
# ======================================================================

step 4 "Container App ($ACA_NAME)"
log "Creating Container App with placeholder image..."

az containerapp create \
    --name "$ACA_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ACA_ENV_NAME" \
    --image "mcr.microsoft.com/azuredocs/containerapps-helloworld:latest" \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 3 \
    --cpu 0.5 \
    --memory "1.0Gi" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_NAME" \
    --registry-password "$ACR_PWD" \
    --secrets "aoai-key=$AOAI_API_KEY" "db-url=$DB_URL" \
    --env-vars \
        "AZURE_OPENAI_ENDPOINT=$AOAI_ENDPOINT" \
        "AZURE_OPENAI_DEPLOYMENT=$AOAI_DEPLOYMENT" \
        "AZURE_OPENAI_API_KEY=secretref:aoai-key" \
        "DATABASE_URL=secretref:db-url" \
        "DEBUG=false" \
        "STIX_DATA_DIR=/app/data/stix" \
        "SYNC_INTERVAL_HOURS=24" \
        "FRONTEND_URL=http://localhost:5173" \
    --output none
ok "Container App created (running placeholder image)."

BACKEND_FQDN=$(az containerapp show \
    --name "$ACA_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --query "properties.configuration.ingress.fqdn" -o tsv)
BACKEND_URL="https://$BACKEND_FQDN"
ok "Container App URL: $BACKEND_URL"

# ======================================================================
# Save generated values to .deploy-state.json (gitignored)
# Only stores generated/discovered values — resource names come from deploy.config
# ======================================================================

jq -n \
    --arg rg  "$RESOURCE_GROUP" \
    --arg acr "$ACR_NAME" \
    --arg srv "$ACR_LOGIN_SERVER" \
    --arg aca "$ACA_NAME" \
    --arg url "$BACKEND_URL" \
    '{ResourceGroup: $rg, AcrName: $acr, AcrLoginServer: $srv, AcaName: $aca, BackendUrl: $url}' \
    > "$STATE_FILE"

# ======================================================================
# Summary
# ======================================================================

echo ""
echo -e "\033[32m====================================================\033[0m"
echo -e "\033[32m  Azure resources ready!\033[0m"
echo -e "\033[32m====================================================\033[0m"
echo -e "  App URL : \033[36m$BACKEND_URL\033[0m"
echo -e "  ACR     : \033[36m$ACR_LOGIN_SERVER\033[0m"
echo ""
echo "  State saved to: $STATE_FILE"
echo ""
echo -e "\033[33m  NEXT STEP: build and deploy the app:\033[0m"
echo -e "\033[33m  bash azure/deploy.sh\033[0m"
echo ""
