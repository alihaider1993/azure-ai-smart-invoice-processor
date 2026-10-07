#!/usr/bin/env bash
# Creates the Azure resources for the public demo and writes .streamlit/secrets.toml.
# Author: Syed Ali Haider
#
# Usage (Git Bash, WSL, macOS or Linux, after `az login`):
#   bash infra/setup_azure.sh
#
# Safe to re-run: resource names are derived from your subscription ID, and existing
# resources are updated rather than duplicated. Re-running rotates the service principal secret.
#
# Cost profile:
#   Document Intelligence  F0 (free, 500 pages/month)
#   Cosmos DB              free tier (1000 RU/s + 25 GB free; one free-tier account per subscription)
#   Azure OpenAI           pay per token; low TPM quota caps spend
set -euo pipefail
export MSYS_NO_PATHCONV=1  # stop Git Bash rewriting "/" and resource IDs into Windows paths

LOCATION="${LOCATION:-uksouth}"
RG="${RG:-rg-invoice-demo}"
MODEL="${MODEL:-gpt-4.1-mini}"
MODEL_VERSION="${MODEL_VERSION:-2025-04-14}"
TPM_CAPACITY="${TPM_CAPACITY:-10}"  # thousands of tokens per minute

tsv() { "$@" -o tsv | tr -d '\r'; }

SUBSCRIPTION_ID=$(tsv az account show --query id)
SUFFIX=$(printf '%s' "$SUBSCRIPTION_ID" | sha1sum | cut -c1-6)
OPENAI_NAME="aoai-invoice-$SUFFIX"
DOCINTEL_NAME="docintel-invoice-$SUFFIX"
COSMOS_NAME="cosmos-invoice-$SUFFIX"
SP_NAME="sp-invoice-demo-$SUFFIX"
DATABASE="invoice-db"
CONTAINERS=(invoices processed-invoices vendors duplicates)
TTL_SECONDS=86400

echo "Subscription: $SUBSCRIPTION_ID"
echo "Resource group: $RG ($LOCATION)"

az group create -n "$RG" -l "$LOCATION" -o none

disable_local_auth() {
  az resource update --ids "$1" --set properties.disableLocalAuth=true -o none
}

echo "==> Azure OpenAI: $OPENAI_NAME"
az cognitiveservices account create -n "$OPENAI_NAME" -g "$RG" -l "$LOCATION" \
  --kind OpenAI --sku S0 --custom-domain "$OPENAI_NAME" --yes -o none
OPENAI_ID=$(tsv az cognitiveservices account show -n "$OPENAI_NAME" -g "$RG" --query id)
disable_local_auth "$OPENAI_ID"
az cognitiveservices account deployment create -n "$OPENAI_NAME" -g "$RG" \
  --deployment-name "$MODEL" --model-name "$MODEL" --model-version "$MODEL_VERSION" \
  --model-format OpenAI --sku-name GlobalStandard --sku-capacity "$TPM_CAPACITY" -o none

echo "==> Document Intelligence (F0): $DOCINTEL_NAME"
az cognitiveservices account create -n "$DOCINTEL_NAME" -g "$RG" -l "$LOCATION" \
  --kind FormRecognizer --sku F0 --custom-domain "$DOCINTEL_NAME" --yes -o none
DOCINTEL_ID=$(tsv az cognitiveservices account show -n "$DOCINTEL_NAME" -g "$RG" --query id)
disable_local_auth "$DOCINTEL_ID"

echo "==> Cosmos DB (free tier): $COSMOS_NAME  (this step takes 5-10 minutes)"
if ! az cosmosdb show -n "$COSMOS_NAME" -g "$RG" -o none 2>/dev/null; then
  az cosmosdb create -n "$COSMOS_NAME" -g "$RG" --locations regionName="$LOCATION" \
    --enable-free-tier true --default-consistency-level Session -o none
fi
COSMOS_ID=$(tsv az cosmosdb show -n "$COSMOS_NAME" -g "$RG" --query id)
disable_local_auth "$COSMOS_ID"

if ! az cosmosdb sql database show -a "$COSMOS_NAME" -g "$RG" -n "$DATABASE" -o none 2>/dev/null; then
  az cosmosdb sql database create -a "$COSMOS_NAME" -g "$RG" -n "$DATABASE" --throughput 400 -o none
fi
for container in "${CONTAINERS[@]}"; do
  if ! az cosmosdb sql container show -a "$COSMOS_NAME" -g "$RG" -d "$DATABASE" -n "$container" -o none 2>/dev/null; then
    az cosmosdb sql container create -a "$COSMOS_NAME" -g "$RG" -d "$DATABASE" -n "$container" \
      --partition-key-path /id --ttl "$TTL_SECONDS" -o none
  fi
done

echo "==> Service principal: $SP_NAME"
SP_JSON=$(az ad sp create-for-rbac -n "$SP_NAME" --query "[appId, password, tenant]" -o tsv | tr -d '\r')
APP_ID=$(sed -n 1p <<<"$SP_JSON")
CLIENT_SECRET=$(sed -n 2p <<<"$SP_JSON")
TENANT_ID=$(sed -n 3p <<<"$SP_JSON")
SP_OBJECT_ID=$(tsv az ad sp show --id "$APP_ID" --query id)
USER_OBJECT_ID=$(tsv az ad signed-in-user show --query id)

# New principals can take a minute to replicate, so retry role assignments.
retry() {
  for attempt in 1 2 3 4 5 6; do
    "$@" && return 0
    echo "   retrying in 15s (attempt $attempt)..."; sleep 15
  done
  return 1
}

assign_roles() {
  local principal_id="$1" principal_type="$2"
  retry az role assignment create --assignee-object-id "$principal_id" --assignee-principal-type "$principal_type" \
    --role "Cognitive Services OpenAI User" --scope "$OPENAI_ID" -o none
  retry az role assignment create --assignee-object-id "$principal_id" --assignee-principal-type "$principal_type" \
    --role "Cognitive Services User" --scope "$DOCINTEL_ID" -o none
  # Cosmos DB Built-in Data Contributor (data-plane role)
  if [ -z "$(tsv az cosmosdb sql role assignment list -a "$COSMOS_NAME" -g "$RG" --query "[?principalId=='$principal_id'].id")" ]; then
    retry az cosmosdb sql role assignment create -a "$COSMOS_NAME" -g "$RG" \
      --role-definition-id 00000000-0000-0000-0000-000000000002 --principal-id "$principal_id" --scope "/" -o none
  fi
}

echo "==> Assigning roles to the service principal (Streamlit Cloud) and you (local dev)"
assign_roles "$SP_OBJECT_ID" ServicePrincipal
assign_roles "$USER_OBJECT_ID" User

ADMIN_PASSWORD=$(openssl rand -hex 12)
SECRETS_FILE="$(dirname "$0")/../.streamlit/secrets.toml"
mkdir -p "$(dirname "$SECRETS_FILE")"
cat > "$SECRETS_FILE" <<EOF
AZURE_OPENAI_ENDPOINT = "https://$OPENAI_NAME.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT = "$MODEL"
DOC_INTEL_ENDPOINT = "https://$DOCINTEL_NAME.cognitiveservices.azure.com/"
COSMOS_ENDPOINT = "https://$COSMOS_NAME.documents.azure.com:443/"
AZURE_TENANT_ID = "$TENANT_ID"
AZURE_CLIENT_ID = "$APP_ID"
AZURE_CLIENT_SECRET = "$CLIENT_SECRET"
ADMIN_PASSWORD = "$ADMIN_PASSWORD"
DAILY_INVOICE_LIMIT = "40"
EOF

echo
echo "Done. Wrote $SECRETS_FILE (git-ignored)."
echo "Paste its contents into Streamlit Community Cloud > App settings > Secrets."
echo "The service principal secret expires in 1 year; re-run this script to rotate it."
