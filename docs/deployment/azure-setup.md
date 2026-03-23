# Azure Deployment Guide

This guide walks through deploying OpenInsure to Azure, from prerequisite setup to a running production environment.

---

## Prerequisites

### Azure Subscription

- An active Azure subscription with **Contributor** role (or higher) on a resource group.
- Azure Entra ID (AAD) tenant for identity management.

### CLI Tools

Install the following tools on your development machine:

```bash
# Azure CLI (v2.60+)
# https://learn.microsoft.com/cli/azure/install-azure-cli
az --version

# Azure Developer CLI (azd) — optional but recommended
# https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd
azd version

# Bicep CLI (bundled with Azure CLI, or standalone)
az bicep version

# Docker (for local container builds)
docker --version

# Python 3.12+
python --version

# Git
git --version
```

### Authenticate

```bash
# Log in to Azure
az login

# Set your target subscription
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Verify
az account show --query "{name:name, id:id, tenantId:tenantId}"
```

---

## 1. Resource Group Creation

Create a resource group for all OpenInsure resources:

```bash
RESOURCE_GROUP="rg-openinsure-prod"
LOCATION="eastus2"

az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --tags "project=openinsure" "environment=production"
```

---

## 2. Bicep Deployment

OpenInsure infrastructure is defined in Bicep templates under `infra/`.

### Review Parameters

Edit `infra/main.bicepparam` to set your environment-specific values:

```
// infra/main.bicepparam
using 'main.bicep'

param environmentName = 'prod'
param location        = 'eastus2'
param principalId     = '<YOUR_AAD_OBJECT_ID>'
```

### Deploy

```bash
# Validate the template first
az deployment group validate \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam

# Deploy
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --name "openinsure-$(date +%Y%m%d-%H%M%S)"
```

### What Gets Deployed

The Bicep templates provision the following resources:

| Resource | SKU / Tier | Purpose |
|---|---|---|
| Azure Container Apps Environment | Consumption | Application hosting |
| Azure Container Registry | Basic | Container image registry |
| Azure SQL Database | S1 Standard | Transactional data store |
| Azure Cosmos DB (Gremlin API) | Serverless | Knowledge graph |
| Azure Blob Storage | Standard LRS | Document storage |
| Azure Event Grid Topic | Basic | Domain event publishing |
| Azure Service Bus Namespace | Standard | Reliable message processing |
| Azure AI Search | Basic | Hybrid search |
| Azure Key Vault | Standard | Secrets management |
| Azure Log Analytics Workspace | Pay-as-you-go | Monitoring & diagnostics |
| Azure Application Insights | — | Application telemetry |
| User-assigned Managed Identity | — | Passwordless service auth |

---

## 3. Post-Deployment Configuration

### Assign RBAC Roles

The managed identity needs access to each service:

```bash
# Get the managed identity principal ID
IDENTITY_ID=$(az identity show \
  --resource-group "$RESOURCE_GROUP" \
  --name "id-openinsure-prod" \
  --query principalId -o tsv)

# Azure SQL — assign db_datareader and db_datawriter via SQL
# (Bicep sets the AAD admin; run the following in the SQL database)
# CREATE USER [id-openinsure-prod] FROM EXTERNAL PROVIDER;
# ALTER ROLE db_datareader ADD MEMBER [id-openinsure-prod];
# ALTER ROLE db_datawriter ADD MEMBER [id-openinsure-prod];

# Cosmos DB — assign Cosmos DB Data Contributor
COSMOS_ID=$(az cosmosdb show -g "$RESOURCE_GROUP" -n "cosmos-openinsure-prod" --query id -o tsv)
az role assignment create \
  --assignee "$IDENTITY_ID" \
  --role "00000000-0000-0000-0000-000000000002" \
  --scope "$COSMOS_ID"

# Blob Storage — assign Storage Blob Data Contributor
STORAGE_ID=$(az storage account show -g "$RESOURCE_GROUP" -n "stopeninsure" --query id -o tsv)
az role assignment create \
  --assignee "$IDENTITY_ID" \
  --role "ba92f5b4-2d11-453d-a403-e96b0029c9fe" \
  --scope "$STORAGE_ID"

# Event Grid — assign Event Grid Data Sender
EG_ID=$(az eventgrid topic show -g "$RESOURCE_GROUP" -n "egt-openinsure-prod" --query id -o tsv)
az role assignment create \
  --assignee "$IDENTITY_ID" \
  --role "d5a91429-5739-47e2-a06b-3470a27159e7" \
  --scope "$EG_ID"

# Service Bus — assign Service Bus Data Owner
SB_ID=$(az servicebus namespace show -g "$RESOURCE_GROUP" -n "sb-openinsure-prod" --query id -o tsv)
az role assignment create \
  --assignee "$IDENTITY_ID" \
  --role "090c5cfd-751d-490a-894a-3ce6f1109419" \
  --scope "$SB_ID"

# AI Search — assign Search Index Data Contributor
SEARCH_ID=$(az search service show -g "$RESOURCE_GROUP" -n "srch-openinsure-prod" --query id -o tsv)
az role assignment create \
  --assignee "$IDENTITY_ID" \
  --role "8ebe5a00-799e-43f5-93ac-243d3dce84a7" \
  --scope "$SEARCH_ID"

# Key Vault — assign Key Vault Secrets User
KV_ID=$(az keyvault show -g "$RESOURCE_GROUP" -n "kv-openinsure-prod" --query id -o tsv)
az role assignment create \
  --assignee "$IDENTITY_ID" \
  --role "4633458b-17de-408a-b874-0445c86b69e6" \
  --scope "$KV_ID"
```

### Initialize the SQL Database

```bash
# Run the schema migration
python -m openinsure.infrastructure.migrations up
```

### Seed the Knowledge Graph

```bash
# Load product definitions and guidelines into Cosmos DB
python -m openinsure.knowledge.loader --source knowledge/
```

### Build and Push Container Image

```bash
ACR_NAME="acropeninsure"

# Build
az acr build \
  --registry "$ACR_NAME" \
  --image openinsure:latest \
  --file Dockerfile .

# Deploy to Container Apps
az containerapp update \
  --name "ca-openinsure-prod" \
  --resource-group "$RESOURCE_GROUP" \
  --image "$ACR_NAME.azurecr.io/openinsure:latest"
```

### Verify Deployment

```bash
# Get the application URL
APP_URL=$(az containerapp show \
  --name "ca-openinsure-prod" \
  --resource-group "$RESOURCE_GROUP" \
  --query "properties.configuration.ingress.fqdn" -o tsv)

# Health check
curl "https://$APP_URL/health"

# API docs
echo "OpenAPI docs: https://$APP_URL/docs"
```

---

## 4. Local Development Setup

### Clone and Install

```bash
git clone https://github.com/openinsure/openinsure.git
cd openinsure

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"
```

### Environment Variables

Create a `.env` file (not committed to Git):

```env
# Azure SQL
AZURE_SQL_SERVER=localhost
AZURE_SQL_DATABASE=openinsure_dev

# Cosmos DB (use emulator for local dev)
COSMOS_ENDPOINT=https://localhost:8081
COSMOS_KEY=<emulator_key>
COSMOS_DATABASE=openinsure
COSMOS_GRAPH=knowledge

# Blob Storage (use Azurite for local dev)
BLOB_ACCOUNT_URL=http://127.0.0.1:10000/devstoreaccount1
BLOB_CONTAINER=documents

# Event Grid / Service Bus (use local stubs in dev)
EVENT_BUS_MODE=local

# AI Search (optional — use stubs for local dev)
AI_SEARCH_ENDPOINT=
AI_SEARCH_INDEX=openinsure-dev
```

### Run Locally

```bash
# Start the development server
uvicorn openinsure.main:app --reload --port 8000

# Run tests
pytest

# Run type checks
mypy src/

# Run linter
ruff check src/
```

### Using Azurite and Cosmos DB Emulator

For local development without Azure access:

```bash
# Start Azurite (Blob Storage emulator)
npm install -g azurite
azurite --silent --location /tmp/azurite

# Start Cosmos DB emulator (Docker)
docker run -p 8081:8081 -p 10250-10255:10250-10255 \
  mcr.microsoft.com/cosmosdb/linux/azure-cosmos-emulator:latest
```

---

## 5. Monitoring

### Application Insights

Application telemetry is automatically collected via the Azure Monitor OpenTelemetry SDK. View dashboards in the Azure Portal under the Application Insights resource.

### Key Metrics to Monitor

| Metric | Alert Threshold | Description |
|---|---|---|
| API response time (P95) | > 2 seconds | End-to-end API latency |
| Error rate | > 1% | 5xx responses / total requests |
| Decision record count | Flatline | Indicates logging may be broken |
| Bias monitor flags | Any | Disparate impact detected |
| Dead-letter queue depth | > 0 for 15 min | Failed event processing |
| Container CPU usage | > 80% sustained | Scale-out trigger |

### Log Queries (KQL)

```kql
// Recent errors
traces
| where severityLevel >= 3
| order by timestamp desc
| take 50

// Decision records per hour
customEvents
| where name == "decision_record.stored"
| summarize count() by bin(timestamp, 1h)
| render timechart

// Slow API calls
requests
| where duration > 2000
| project timestamp, name, duration, resultCode
| order by duration desc
```

---

## 6. MCP Server Configuration (White-Label)

After deploying the backend to Azure Container Apps, configure the **MCP server** so
that MCP clients (Copilot CLI, Claude Desktop, custom orchestrators) connect to the
tenant's backend.

### Find your backend URL

```bash
# Get the backend's FQDN from Container Apps
az containerapp show \
  --name openinsure-backend \
  --resource-group $RESOURCE_GROUP \
  --query "properties.configuration.ingress.fqdn" -o tsv
```

This returns something like: `openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io`

### Option A: Environment variable (recommended)

Set `OPENINSURE_API_BASE_URL` in the MCP client config. This is the standard way
for white-label deployments — each tenant sets their own URL.

**Copilot CLI** (`.copilot/mcp-config.json`):

```json
{
  "mcpServers": {
    "openinsure": {
      "command": "python",
      "args": ["-m", "openinsure.mcp"],
      "env": {
        "OPENINSURE_API_BASE_URL": "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
      }
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "openinsure": {
      "command": "python",
      "args": ["-m", "openinsure.mcp"],
      "env": {
        "OPENINSURE_API_BASE_URL": "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
      }
    }
  }
}
```

### Option B: CLI argument

```bash
python -m openinsure.mcp --api-url https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io
```

### Verify connectivity

```bash
# Health check against the backend
curl https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io/health
```

### Resolution order

The MCP server resolves the backend URL in this order:

| Priority | Source | Use case |
|----------|--------|----------|
| 1 | `OPENINSURE_API_BASE_URL` env var | White-label / production |
| 2 | `--api-url` CLI argument | Ad-hoc / testing |
| 3 | `http://localhost:${OPENINSURE_PORT}` | Local development only |

> **⚠️** The localhost fallback emits a warning log. Always set `OPENINSURE_API_BASE_URL`
> for production deployments.

---

## Troubleshooting

| Issue | Resolution |
|---|---|
| `DefaultAzureCredential` fails | Run `az login` or check managed identity assignment |
| SQL connection timeout | Verify firewall rules allow the container's outbound IP |
| Cosmos DB 403 | Check RBAC role assignment for the managed identity |
| Event Grid events not arriving | Verify Event Grid subscription exists and endpoint is active |
| Container App not starting | Check `az containerapp logs show` for startup errors |
| MCP: "using_localhost_fallback" warning | Set `OPENINSURE_API_BASE_URL` env var in your MCP client config |
| MCP: connection refused | Verify the backend URL is correct and the Container App is running |
| MCP: triage returns empty response | Check the Foundry agent is deployed and `OPENINSURE_OPENAI_ENDPOINT` is set on the backend |
