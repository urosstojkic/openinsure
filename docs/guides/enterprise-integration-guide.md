# OpenInsure Enterprise Integration Guide

**For organizations deploying OpenInsure as a production insurance platform**

This guide provides practical steps for deploying OpenInsure in an enterprise environment. It covers infrastructure setup, user provisioning, knowledge base configuration, product setup, integrations, data migration, and ongoing operations.

---

## 1. Pre-Deployment: Azure Resources Needed

OpenInsure requires the following Azure resources. All are provisioned via Bicep templates in `infra/`.

### Core Infrastructure

| Resource | Purpose | Bicep Module | Estimated Monthly Cost |
|----------|---------|--------------|------------------------|
| **Resource Group** | Container for all OpenInsure resources | Manual creation | Free |
| **User-Assigned Managed Identity** | Service-to-service authentication (no secrets) | `infra/main.bicep` | Free |
| **Azure Container Registry (ACR)** | Store backend and dashboard container images | `infra/main.bicep` (implied) | ~$5 (Basic) |
| **Azure Container Apps** (2 apps) | Host backend API and React dashboard | `infra/main.bicep` (implied) | ~$30–$150/month |
| **Azure SQL Database** | Transactional data (submissions, policies, claims, parties) | `infra/modules/sql.bicep` | ~$15–$500/month |
| **Cosmos DB (NoSQL)** | Knowledge graph source of truth, unstructured documents | `infra/modules/cosmos.bicep` | ~$25–$200/month |
| **Azure Blob Storage** | Document uploads, policy forms, claims evidence | `infra/modules/storage.bicep` | ~$5–$50/month |
| **Azure AI Search** | Cognitive search over knowledge graph and guidelines | `infra/modules/search.bicep` | ~$250/month (Standard) |
| **Azure AI Foundry Project** | 10 GPT-5.2 agents + AI Search tools | Manual (Foundry portal) | ~$500–$5,000/month |
| **Azure Service Bus** | Event-driven messaging (domain events) | `infra/modules/servicebus.bicep` | ~$10/month (Standard) |
| **Azure Event Grid** | Webhook routing for external integrations | `infra/modules/eventgrid.bicep` | ~$1/month |
| **Log Analytics Workspace** | Centralized logging and monitoring | `infra/modules/monitoring.bicep` | ~$50–$200/month |
| **Application Insights** | APM, traces, exceptions | `infra/modules/monitoring.bicep` | Included with Log Analytics |

**Estimated Total Monthly Cost:** $900–$6,500 depending on scale, region, and tier selection.

### Optional Resources (for production-grade deployments)

| Resource | Purpose | Integration Method |
|----------|---------|-------------------|
| **Azure Communication Services** | Email notifications (broker correspondence, policy delivery, claims updates) | Azure SDK, triggered by Service Bus events |
| **Azure Key Vault** | Secret management (API keys, connection strings) | Referenced in Bicep via `@Microsoft.KeyVault(secretUri='...')` |
| **Azure Front Door** | Global CDN, WAF, DDoS protection for dashboard | Points to Container Apps |
| **Azure Private Link** | VNet-integrated private endpoints for SQL, Cosmos, Storage | Configured in Bicep modules |
| **Azure Virtual Network** | Network isolation for Container Apps | `infra/modules/network.bicep` (if implementing private endpoints) |

### Third-Party Integrations (External)

| System | Purpose | Integration Method | Estimated Monthly Cost |
|--------|---------|-------------------|------------------------|
| **Stripe / Payment Gateway** | Premium collection, ACH, credit card processing | Webhook + API | 2.9% + $0.30 per transaction |
| **SecurityScorecard / BitSight** | Cyber risk scoring for underwriting | REST API via Foundry Tools | ~$1,000–$5,000/month |
| **ISO / AAIS** | Rating bureau loss costs, statistical reporting | Data feed + API | Varies by state/LOB |
| **DocuSign / Adobe Sign** | E-signatures for policy documents | Webhook + API | ~$40/user/month |
| **Docmosis / Windward** | Policy document generation (declarations pages, certificates) | Template engine + Blob storage output | ~$500–$2,000/month |

---

## 2. Infrastructure Deployment

### Step 1: Authenticate and Set Subscription

```bash
# Log in to Azure
az login

# Set target subscription
az account set --subscription "<YOUR_SUBSCRIPTION_ID>"

# Verify
az account show --query "{name:name, id:id, tenantId:tenantId}"
```

### Step 2: Create Resource Group

```bash
RESOURCE_GROUP="rg-openinsure-prod"
LOCATION="eastus2"  # Choose region close to your operations

az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --tags "project=openinsure" "environment=production"
```

### Step 3: Deploy Bicep Templates

```bash
cd infra/

# Validate the template
az deployment group validate \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters environmentName=prod

# Deploy all infrastructure
az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file main.bicep \
  --parameters environmentName=prod \
  --mode Incremental
```

This deploys:
- Managed Identity
- Log Analytics + Application Insights
- Azure SQL Database (with Entra ID admin)
- Cosmos DB (NoSQL API, 2 databases: `knowledge-dev`, `knowledge-prod`)
- Blob Storage (3 containers: `submissions`, `policies`, `claims`)
- Azure AI Search (Standard tier)
- Service Bus (namespace + 10 topics)
- Event Grid (namespace + 3 topics)

**Deployment time:** 10–15 minutes.

### Step 4: Retrieve Connection Strings

After deployment, retrieve connection strings for environment configuration:

```bash
# SQL connection string
az sql db show-connection-string \
  --client ado.net \
  --server "openinsure-prod-sql-<uniqueId>" \
  --name "openinsure"

# Cosmos DB connection string
az cosmosdb keys list \
  --resource-group "$RESOURCE_GROUP" \
  --name "openinsure-prod-cosmos-<uniqueId>" \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" -o tsv

# Storage account connection string
az storage account show-connection-string \
  --resource-group "$RESOURCE_GROUP" \
  --name "openinsurestorage<uniqueId>" -o tsv

# Service Bus connection string
az servicebus namespace authorization-rule keys list \
  --resource-group "$RESOURCE_GROUP" \
  --namespace-name "openinsure-prod-sb-<uniqueId>" \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv

# AI Search admin key
az search admin-key show \
  --resource-group "$RESOURCE_GROUP" \
  --service-name "openinsure-prod-search-<uniqueId>" \
  --query primaryKey -o tsv
```

Store these securely in Azure Key Vault or your CI/CD secrets.

### Step 5: Configure Azure AI Foundry

Azure AI Foundry (the agent platform) is not yet fully Bicep-provisioned. Create the Foundry project manually:

1. Navigate to https://ai.azure.com
2. Click **New project** → Name: `openinsure-prod`
3. Select resource group: `rg-openinsure-prod`
4. Select region: `eastus2` (must match AI Search region)
5. Create or select an **Azure AI Hub** (shared across projects)
6. Under **AI Services**, attach the AI Search instance deployed earlier

**Deploy the 10 Foundry agents:**

```bash
cd src/openinsure/agents/

# Deploy all agents (requires Azure AI Projects SDK)
python deploy_agents.py \
  --project "openinsure-prod" \
  --resource-group "$RESOURCE_GROUP" \
  --model "gpt-5.2" \
  --search-endpoint "<your-search-endpoint>"
```

This deploys:
1. Orchestrator
2. Submission
3. Underwriting
4. Policy
5. Claims
6. Compliance
7. Document
8. Knowledge
9. Enrichment
10. Analytics

Each agent is configured with AI Search tools pointing to the knowledge base.

### Step 6: Deploy Container Apps

Build and push container images to ACR:

```bash
# Build backend
az acr build \
  --registry "openinsureacr<uniqueId>" \
  --image "openinsure-backend:prod-v1" \
  --file Dockerfile \
  .

# Build dashboard
az acr build \
  --registry "openinsureacr<uniqueId>" \
  --image "openinsure-dashboard:prod-v1" \
  --file dashboard/Dockerfile \
  ./dashboard
```

Deploy to Container Apps:

```bash
# Backend (API)
az containerapp create \
  --name "openinsure-backend" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "<your-container-app-env>" \
  --image "openinsureacr<uniqueId>.azurecr.io/openinsure-backend:prod-v1" \
  --registry-server "openinsureacr<uniqueId>.azurecr.io" \
  --registry-identity "<managed-identity-resource-id>" \
  --target-port 8000 \
  --ingress external \
  --env-vars \
    "AZURE_SQL_CONNECTION_STRING=secretref:sql-connection" \
    "COSMOS_CONNECTION_STRING=secretref:cosmos-connection" \
    "STORAGE_CONNECTION_STRING=secretref:storage-connection" \
    "SERVICEBUS_CONNECTION_STRING=secretref:servicebus-connection" \
    "AI_SEARCH_ENDPOINT=<your-search-endpoint>" \
    "AI_SEARCH_API_KEY=secretref:search-key" \
    "FOUNDRY_PROJECT_NAME=openinsure-prod" \
    "STORAGE_MODE=sql"

# Dashboard (React UI)
az containerapp create \
  --name "openinsure-dashboard" \
  --resource-group "$RESOURCE_GROUP" \
  --environment "<your-container-app-env>" \
  --image "openinsureacr<uniqueId>.azurecr.io/openinsure-dashboard:prod-v1" \
  --registry-server "openinsureacr<uniqueId>.azurecr.io" \
  --registry-identity "<managed-identity-resource-id>" \
  --target-port 80 \
  --ingress external \
  --env-vars \
    "VITE_API_URL=https://<your-backend-url>" \
    "VITE_USE_MOCK=false"
```

**URLs:**
- Backend: `https://openinsure-backend.<container-app-env>.<region>.azurecontainerapps.io`
- Dashboard: `https://openinsure-dashboard.<container-app-env>.<region>.azurecontainerapps.io`

### Step 7: VNet Integration and Private Endpoints (Optional, for Enterprise Security)

For production deployments requiring network isolation:

1. **Create VNet:**
   ```bash
   az network vnet create \
     --resource-group "$RESOURCE_GROUP" \
     --name "openinsure-vnet" \
     --address-prefixes "10.0.0.0/16" \
     --subnet-name "container-apps-subnet" \
     --subnet-prefix "10.0.1.0/24"
   ```

2. **Configure Container Apps Environment with VNet:**
   ```bash
   az containerapp env create \
     --name "openinsure-env" \
     --resource-group "$RESOURCE_GROUP" \
     --location "$LOCATION" \
     --infrastructure-subnet-resource-id "<subnet-id>" \
     --internal-only false  # Set to true for fully private deployment
   ```

3. **Enable Private Endpoints for SQL, Cosmos, Storage:**
   ```bash
   # SQL Database private endpoint
   az network private-endpoint create \
     --resource-group "$RESOURCE_GROUP" \
     --name "sql-private-endpoint" \
     --vnet-name "openinsure-vnet" \
     --subnet "container-apps-subnet" \
     --private-connection-resource-id "<sql-server-resource-id>" \
     --group-id "sqlServer" \
     --connection-name "sql-private-connection"
   
   # Repeat for Cosmos DB (groupId: "Sql") and Storage (groupId: "blob")
   ```

4. **Configure Private DNS Zones** for name resolution within the VNet.

---

## 3. User & Role Setup

OpenInsure supports **11 core personas** mapped to Azure Entra ID roles. Map these roles to your organization's identity structure.

### Persona-to-Role Mapping

| Persona | Entra ID Role | Use Case | Access Level |
|---------|---------------|----------|--------------|
| **CEO** | `openinsure-ceo` | Board reporting, strategic oversight | Full portfolio visibility, read-only for most operations, override authority |
| **Chief Underwriting Officer (CUO)** | `openinsure-cuo` | Underwriting strategy, risk appetite, final authority | Full underwriting portfolio, configure agents, unlimited authority |
| **Senior Underwriter** | `openinsure-senior-underwriter` | Complex submissions, exceptions, broker relationships | Submission workbench, quote issuance, book management (within limits) |
| **Underwriting Analyst** | `openinsure-uw-analyst` | Data entry, research, junior underwriting tasks | View submissions, limited edit, no quote authority |
| **Claims Adjuster** | `openinsure-claims-adjuster` | Investigate and settle claims | Claims workbench, reserve authority, settlement authority (within limits) |
| **Claims Manager** | `openinsure-claims-manager` | Oversee adjuster performance, approve reserves/settlements | Full claims portfolio, unlimited authority |
| **Finance Lead** | `openinsure-finance` | Reconciliation, billing, accounting | Billing management, financial reporting |
| **CFO** | `openinsure-cfo` | Financial oversight, reinsurance strategy | Full financial visibility, approve reserves, manage reinsurance |
| **Compliance Officer** | `openinsure-compliance` | Audit decision records, regulatory reporting | Read-only access to all data, audit trails, bias reports |
| **Product Manager** | `openinsure-product-manager` | Configure products, update knowledge graph | Product catalog management, knowledge base editing |
| **Platform Administrator** | `openinsure-platform-admin` | User provisioning, system configuration | User management, Foundry agent configuration, monitoring dashboards |

### Setting Up Entra ID Roles

#### Option 1: Azure AD App Roles (Recommended for Production)

1. **Register an Entra ID App:**
   ```bash
   az ad app create --display-name "OpenInsure Production"
   ```

2. **Define App Roles** in the app manifest (`appRoles` section):
   ```json
   {
     "appRoles": [
       {
         "allowedMemberTypes": ["User"],
         "displayName": "Chief Underwriting Officer",
         "id": "<unique-guid>",
         "isEnabled": true,
         "description": "Full underwriting authority and portfolio management",
         "value": "openinsure-cuo"
       },
       {
         "allowedMemberTypes": ["User"],
         "displayName": "Senior Underwriter",
         "id": "<unique-guid>",
         "isEnabled": true,
         "description": "Underwriting workbench with delegated authority",
         "value": "openinsure-senior-underwriter"
       }
       // ... repeat for all 11 roles
     ]
   }
   ```

3. **Assign Users to Roles:**
   - In Azure Portal → Entra ID → Enterprise Applications → OpenInsure → Users and groups
   - Assign each user to their appropriate role

4. **Configure Backend to Validate JWT Tokens:**
   Update `src/openinsure/rbac/auth.py`:
   ```python
   # Validate JWT token from Entra ID
   from azure.identity import DefaultAzureCredential
   from azure.core.credentials import AccessToken
   
   # Extract roles from token claims
   def get_user_role_from_token(token: str) -> str:
       decoded = jwt.decode(token, options={"verify_signature": False})
       roles = decoded.get("roles", [])
       return roles[0] if roles else "unauthenticated"
   ```

#### Option 2: Entra ID Security Groups (Simpler for SMB)

1. **Create Security Groups** in Entra ID:
   ```bash
   az ad group create --display-name "OpenInsure - CUO" --mail-nickname "openinsure-cuo"
   az ad group create --display-name "OpenInsure - Senior Underwriters" --mail-nickname "openinsure-senior-uw"
   # ... repeat for all 11 roles
   ```

2. **Add Users to Groups** via Azure Portal or CLI.

3. **Configure Backend to Read Group Membership:**
   Use Microsoft Graph API to check group membership on each request.

### Dev-Mode vs. Production Auth

**Dev/Test Mode (Header-based):**
- Set `AUTH_MODE=dev` in backend environment variables
- Pass role via `X-User-Role` header (no authentication required)
- **WARNING:** This mode must be disabled in production.

**Production Mode (JWT-based):**
- Set `AUTH_MODE=jwt` in backend environment variables
- Backend validates JWT tokens issued by Entra ID
- Extracts role from token claims (`roles` claim)
- Rejects requests without valid tokens

**API Key Mode (for M2M integrations):**
- Set `AUTH_MODE=api_key` for machine-to-machine integrations
- Pass API key via `X-API-Key` header
- Map API key to a service principal with specific role

### Authority Delegation

After users are assigned roles, configure **authority limits** in the database:

```sql
-- Set underwriting authority for a senior underwriter
INSERT INTO authority_delegations (user_id, role, action_type, limit_amount, lob, territory)
VALUES 
  ('user-guid-123', 'openinsure-senior-underwriter', 'quote', 2000000, 'cyber', 'US'),
  ('user-guid-123', 'openinsure-senior-underwriter', 'bind', 1000000, 'cyber', 'US');

-- Set claims settlement authority for an adjuster
INSERT INTO authority_delegations (user_id, role, action_type, limit_amount, lob, territory)
VALUES 
  ('user-guid-456', 'openinsure-claims-adjuster', 'settle', 50000, NULL, 'US');
```

CUO and Claims Manager typically have `limit_amount = NULL` (unlimited within their domain).

---

## 4. Knowledge Base Configuration

The **knowledge base** is the source of truth for underwriting guidelines, rating factors, exclusions, state regulations, and claims precedents. It powers all 10 Foundry agents via Azure AI Search.

### Knowledge Base Structure

Knowledge is stored in **Cosmos DB** (`knowledge-prod` database) and indexed in **Azure AI Search**. Each document has:
- `id`: Unique identifier
- `title`: Human-readable name
- `content`: Markdown or structured text
- `doc_type`: One of: `guideline`, `rating_factor`, `exclusion`, `regulation`, `claims_precedent`, `product_definition`
- `tags`: Array of searchable tags (e.g., `["cyber", "healthcare", "US"]`)
- `version`: Semantic version (e.g., `1.2.0`)
- `effective_date`: ISO 8601 date
- `status`: `active`, `draft`, `superseded`

### Populating the Knowledge Base

#### Step 1: Prepare Your Guidelines

Convert your company's underwriting manuals, rating tables, and claims guidelines into structured documents. Example:

**Cyber Insurance Underwriting Guideline:**
```markdown
---
id: UW-CYBER-001
title: Cyber Insurance Underwriting Guidelines
doc_type: guideline
tags: [cyber, underwriting, SMB]
version: 2.1.0
effective_date: 2025-01-01
status: active
---

# Cyber Insurance Underwriting Guidelines

## Appetite

We write cyber insurance for:
- Technology companies: SaaS, cloud services, software development
- Professional services: consulting, accounting, legal
- Healthcare: HIPAA-covered entities under $50M revenue
- Retail: E-commerce with annual revenue $5M–$100M

We decline:
- Cryptocurrency exchanges or blockchain platforms
- Adult content websites
- Companies with known ransomware infections in past 24 months
- Companies without MFA on all email accounts

## Rating Factors

Base premium is calculated using:
- Revenue: primary rating variable
- Industry class: healthcare 1.4x, technology 1.0x, retail 1.2x
- Security posture: SecurityScorecard rating (A=0.8x, B=1.0x, C=1.3x, D/F=decline)
- Prior claims: 1 claim in 3 years = 1.5x, 2+ claims = decline
- Limits purchased: $1M, $2M, $5M, $10M available

## Authority Levels

- Junior Underwriter: Quote only, up to $1M limits, standard risks
- Senior Underwriter: Quote and bind up to $2M limits
- VP Underwriting: Quote and bind up to $10M limits
- CUO: Unlimited authority, all exceptions

## Required Subjectivities

All cyber policies require:
1. Annual security awareness training
2. MFA enabled on all email and admin accounts
3. Daily backups with offline storage
4. Endpoint protection on all devices
5. Incident response plan documented
```

#### Step 2: Upload to Cosmos DB

Use the backend API to upload knowledge documents:

```bash
curl -X POST "https://<your-backend-url>/api/v1/knowledge" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{
    "id": "UW-CYBER-001",
    "title": "Cyber Insurance Underwriting Guidelines",
    "content": "<markdown-content>",
    "doc_type": "guideline",
    "tags": ["cyber", "underwriting", "SMB"],
    "version": "2.1.0",
    "effective_date": "2025-01-01",
    "status": "active"
  }'
```

#### Step 3: Bulk Import from Existing Documents

If you have existing underwriting manuals in Word/PDF format:

1. **Convert to Markdown** using Pandoc or Adobe Acrobat
2. **Split into Logical Sections** (one guideline per document)
3. **Bulk Upload via Python Script:**

```python
import json
import requests
from pathlib import Path

API_URL = "https://<your-backend-url>/api/v1/knowledge"
API_KEY = "<your-api-key>"

knowledge_dir = Path("./knowledge_sources")

for filepath in knowledge_dir.glob("*.md"):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Extract frontmatter (YAML) for metadata
    # Parse using python-frontmatter or custom parser
    
    doc = {
        "id": filepath.stem,
        "title": filepath.stem.replace("-", " ").title(),
        "content": content,
        "doc_type": "guideline",  # adjust per file
        "tags": [],
        "version": "1.0.0",
        "effective_date": "2025-01-01",
        "status": "active"
    }
    
    response = requests.post(
        API_URL,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        json=doc
    )
    
    print(f"Uploaded {filepath.name}: {response.status_code}")
```

#### Step 4: Verify AI Search Indexing

After uploading, verify documents are indexed and searchable:

```bash
curl -X GET "https://<your-backend-url>/api/v1/knowledge/search?q=cyber+underwriting" \
  -H "X-API-Key: <your-api-key>"
```

Expected response:
```json
{
  "results": [
    {
      "id": "UW-CYBER-001",
      "title": "Cyber Insurance Underwriting Guidelines",
      "score": 0.92,
      "highlights": ["We write cyber insurance for technology companies..."]
    }
  ]
}
```

### Knowledge Management Best Practices

1. **Version Control:** Increment `version` whenever guidelines change. Keep old versions with `status: superseded`.
2. **Effective Dates:** Set `effective_date` for rate changes to ensure agents use correct rates per policy term.
3. **Tagging:** Use consistent tags (LOB, territory, process stage) for precise agent retrieval.
4. **Regular Audits:** Review agent decisions quarterly to identify knowledge gaps. Add missing guidelines.
5. **Change Management:** Notify underwriters when guidelines are updated (via dashboard notifications).

### Specialized Knowledge Types

**Rating Factors (Table-based):**
```json
{
  "id": "RATE-CYBER-001",
  "title": "Cyber Insurance Rating Table v3.1",
  "doc_type": "rating_factor",
  "content": "...",
  "tags": ["cyber", "rating"],
  "version": "3.1.0",
  "effective_date": "2025-04-01",
  "status": "active",
  "rating_table": {
    "base_rate_per_million_revenue": 0.005,
    "industry_factors": {
      "technology": 1.0,
      "healthcare": 1.4,
      "retail": 1.2,
      "manufacturing": 0.9
    },
    "security_score_factors": {
      "A": 0.8,
      "B": 1.0,
      "C": 1.3,
      "D": 1.6,
      "F": "decline"
    },
    "limit_factors": {
      "1000000": 1.0,
      "2000000": 1.8,
      "5000000": 4.0,
      "10000000": 7.5
    }
  }
}
```

**Claims Precedents:**
```json
{
  "id": "CLAIMS-CYBER-2023-047",
  "title": "Ransomware Coverage - Healthcare Entity",
  "doc_type": "claims_precedent",
  "content": "Insured: Regional medical practice (50 employees). Incident: Ransomware encrypted EMR system. Claim: Business interruption ($120K), forensic costs ($35K), ransom payment ($50K). Decision: Covered in full. Rationale: Policy in force, no MFA exclusion triggered (MFA was implemented), ransomware explicitly covered. Settlement: $205K total.",
  "tags": ["cyber", "ransomware", "healthcare", "coverage-granted"],
  "effective_date": "2023-08-15",
  "claim_id": "CLM-2023-047"
}
```

**Regulatory Requirements:**
```json
{
  "id": "REG-CYBER-CA",
  "title": "California Cyber Insurance Requirements",
  "doc_type": "regulation",
  "content": "California AB 1950 requires cyber insurers to collect and report breach statistics annually. All cyber policies sold in CA must include coverage for regulatory fines and penalties arising from data breaches. Minimum policy language: ...",
  "tags": ["cyber", "california", "regulatory"],
  "jurisdiction": "CA",
  "effective_date": "2024-01-01"
}
```

---

## 5. Product Configuration

OpenInsure includes a **Product Management UI** for configuring insurance products (cyber, property, general liability, etc.). Products define coverages, limits, deductibles, rating structure, and subjectivities.

### Product Model

Each product has:
- **Basic Info:** Name, LOB, effective date, status (`active`, `draft`, `superseded`)
- **Coverages:** List of coverage items (e.g., "Third-party liability", "Business interruption", "Ransomware")
- **Limits:** Available policy limits (e.g., $1M, $2M, $5M, $10M)
- **Deductibles:** Available deductible options (e.g., $10K, $25K, $50K)
- **Rating Algorithm:** Formula or reference to rating table in knowledge base
- **Subjectivities:** Required risk control measures (MFA, backups, training)
- **Exclusions:** Standard policy exclusions
- **Forms:** Policy form references (ISO forms, proprietary wording)

### Creating a Cyber Insurance Product

#### Via Dashboard UI:

1. Navigate to **Products** → **New Product**
2. Fill in basic details:
   - **Product Name:** Cyber Liability Insurance
   - **LOB:** Cyber
   - **Effective Date:** 2025-01-01
   - **Status:** Active
3. Define **Coverages** (click **Add Coverage** for each):
   - First-party breach response ($100K sublimit)
   - Business interruption (actual loss sustained, 30-day waiting period)
   - Ransomware payments ($500K sublimit)
   - Third-party liability (per policy limit)
   - Regulatory fines and penalties (per policy limit)
   - Media liability (per policy limit)
4. Set **Limits:** $1M, $2M, $5M, $10M
5. Set **Deductibles:** $10K, $25K, $50K, $100K
6. Link **Rating Table:** Select `RATE-CYBER-001` from knowledge base
7. Add **Subjectivities:**
   - MFA enabled on all accounts
   - Daily backups with offline copy
   - Security awareness training completed annually
   - Endpoint protection deployed on 100% of devices
   - Incident response plan documented and tested
8. Add **Exclusions:**
   - Prior known incidents
   - War and terrorism (unless endorsed)
   - Intentional acts
   - Bodily injury or property damage
9. Upload **Policy Forms** (PDF) to Blob Storage, link URLs
10. **Save** → Product is now available for quoting

#### Via API:

```bash
curl -X POST "https://<your-backend-url>/api/v1/products" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{
    "name": "Cyber Liability Insurance",
    "lob": "cyber",
    "effective_date": "2025-01-01",
    "status": "active",
    "coverages": [
      {"name": "First-party breach response", "sublimit": 100000, "description": "..."},
      {"name": "Business interruption", "sublimit": null, "waiting_period_days": 30},
      {"name": "Ransomware payments", "sublimit": 500000},
      {"name": "Third-party liability", "sublimit": null}
    ],
    "limits": [1000000, 2000000, 5000000, 10000000],
    "deductibles": [10000, 25000, 50000, 100000],
    "rating_algorithm_ref": "RATE-CYBER-001",
    "subjectivities": [
      "MFA enabled on all accounts",
      "Daily backups with offline copy",
      "Security awareness training completed annually",
      "Endpoint protection deployed on 100% of devices",
      "Incident response plan documented and tested"
    ],
    "exclusions": [
      "Prior known incidents",
      "War and terrorism",
      "Intentional acts",
      "Bodily injury or property damage"
    ],
    "form_urls": [
      "https://<storage-account>.blob.core.windows.net/forms/cyber-policy-2025.pdf"
    ]
  }'
```

### Product Versioning

When updating a product (e.g., rate change, coverage modification):

1. **Duplicate the Product** with a new `effective_date`
2. Set the old product `status: superseded`
3. New policies use the new version; existing policies remain on old version until renewal

This ensures **rate stability** — policies are not mid-term re-rated.

### Multi-Line Products

For package policies (e.g., BOP = Property + General Liability):

- Create separate products for each coverage part
- Use a **Package Product** entity that references multiple products
- Set package discount factor (e.g., 15% discount vs. standalone)

---

## 6. Integration Points

OpenInsure follows an **API-first** architecture. External systems integrate via REST APIs, webhooks, or Foundry Tools connectors.

### A. Payment Processing (Stripe, Bank API)

**Use Case:** Collect premium payments from policyholders.

**Integration Method:**

1. **Backend generates an invoice** (via billing API, to be implemented):
   ```bash
   POST /api/v1/billing/invoices
   {
     "policy_id": "POL-2025-001",
     "amount": 5000.00,
     "due_date": "2025-02-01",
     "payment_plan": "annual"
   }
   ```

2. **Dashboard displays payment link** using Stripe Checkout:
   ```javascript
   const stripe = require('stripe')('sk_live_...');
   
   const session = await stripe.checkout.sessions.create({
     payment_method_types: ['card', 'ach_debit'],
     line_items: [{
       price_data: {
         currency: 'usd',
         product_data: { name: `Policy ${policyNumber} - Premium Payment` },
         unit_amount: amountCents,
       },
       quantity: 1,
     }],
     mode: 'payment',
     success_url: 'https://<your-dashboard-url>/billing/success',
     cancel_url: 'https://<your-dashboard-url>/billing/cancel',
     metadata: { invoice_id: invoiceId }
   });
   ```

3. **Stripe sends webhook** on payment success:
   ```bash
   POST <your-backend-url>/webhooks/stripe
   {
     "type": "checkout.session.completed",
     "data": {
       "object": {
         "id": "cs_...",
         "metadata": { "invoice_id": "INV-2025-0042" },
         "amount_total": 500000,
         "payment_status": "paid"
       }
     }
   }
   ```

4. **Backend webhook handler** updates billing record:
   ```python
   @app.post("/webhooks/stripe")
   async def stripe_webhook(request: Request):
       payload = await request.body()
       sig_header = request.headers.get("stripe-signature")
       
       event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
       
       if event["type"] == "checkout.session.completed":
           session = event["data"]["object"]
           invoice_id = session["metadata"]["invoice_id"]
           
           # Update invoice status to "paid"
           billing_service.mark_invoice_paid(invoice_id, session["amount_total"] / 100)
       
       return {"status": "ok"}
   ```

**Setup Checklist:**
- [ ] Create Stripe account and obtain API keys
- [ ] Configure webhook endpoint in Stripe Dashboard
- [ ] Store `STRIPE_SECRET_KEY` in Azure Key Vault
- [ ] Implement billing API endpoints (see roadmap, Phase 1)
- [ ] Test end-to-end payment flow in sandbox

---

### B. Email Notifications (Azure Communication Services)

**Use Case:** Send policy documents, claims updates, and broker correspondence.

**Integration Method:**

1. **Provision Azure Communication Services:**
   ```bash
   az communication create \
     --name "openinsure-comm" \
     --resource-group "$RESOURCE_GROUP" \
     --location "global"
   
   az communication email domain create \
     --email-service-name "openinsure-comm" \
     --resource-group "$RESOURCE_GROUP" \
     --domain-name "notifications.openinsure.com"
   ```

2. **Subscribe to Service Bus Events:**
   ```python
   # In backend: src/openinsure/infrastructure/messaging/subscribers.py
   
   from azure.communication.email import EmailClient
   
   email_client = EmailClient.from_connection_string(COMM_SERVICES_CONNECTION_STRING)
   
   async def on_policy_issued(event: PolicyIssuedEvent):
       """Send policy documents to policyholder and broker"""
       policy = await policy_service.get_policy(event.policy_id)
       
       message = {
           "senderAddress": "noreply@notifications.openinsure.com",
           "recipients": {
               "to": [{"address": policy.policyholder_email}],
               "cc": [{"address": policy.broker_email}]
           },
           "content": {
               "subject": f"Policy Issued: {policy.policy_number}",
               "plainText": f"Your policy has been issued. Policy number: {policy.policy_number}",
               "html": render_template("policy_issued.html", policy=policy)
           },
           "attachments": [
               {
                   "name": f"{policy.policy_number}_declarations.pdf",
                   "contentType": "application/pdf",
                   "contentInBase64": get_policy_document_base64(policy.id)
               }
           ]
       }
       
       poller = email_client.begin_send(message)
       result = poller.result()
       
       logger.info(f"Sent policy issuance email: {result.id}")
   ```

3. **Wire Event Subscriber in Service Bus:**
   ```python
   # Register subscriber for policy.issued topic
   servicebus_client = ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
   
   async with servicebus_client:
       receiver = servicebus_client.get_subscription_receiver(
           topic_name="policy-events",
           subscription_name="email-notifications"
       )
       
       async with receiver:
           async for msg in receiver:
               event = json.loads(str(msg))
               if event["event_type"] == "policy.issued":
                   await on_policy_issued(PolicyIssuedEvent(**event["data"]))
               await receiver.complete_message(msg)
   ```

**Email Templates:**
- Policy issuance notification (with declarations PDF)
- Claim FNOL acknowledgment
- Claim status updates (reserves, settlements)
- Renewal notices (90/60/30 days before expiry)
- Broker submission acknowledgment

**Setup Checklist:**
- [ ] Provision Azure Communication Services
- [ ] Configure custom domain and SPF/DKIM records
- [ ] Implement event subscribers for domain events
- [ ] Create HTML email templates
- [ ] Test deliverability (check spam folders)

---

### C. Document Management (SharePoint, OnBase)

**Use Case:** Long-term document retention, versioning, compliance.

**Current State:** Documents stored in Azure Blob Storage (3 containers: `submissions`, `policies`, `claims`). No lifecycle management or permissions model.

**Integration Method:**

**Option 1: SharePoint Online (M365 Integration)**
```python
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.client_credential import ClientCredential

site_url = "https://yourtenant.sharepoint.com/sites/OpenInsure"
client = ClientContext(site_url).with_credentials(ClientCredential(client_id, client_secret))

# Upload policy document to SharePoint library
target_folder = client.web.get_folder_by_server_relative_url("/Shared Documents/Policies")
with open(f"{policy_number}_declarations.pdf", "rb") as f:
    target_folder.upload_file("policy.pdf", f.read()).execute_query()
```

**Option 2: Hyland OnBase (Enterprise DMS)**
- Install OnBase Unity Client or Web API
- Upload documents via OnBase API with metadata (policy number, document type, retention class)
- OnBase handles retention schedules, audit trails, permissions

**Setup Checklist:**
- [ ] Choose DMS solution (SharePoint for SMB, OnBase/DocuWare for enterprise)
- [ ] Configure document retention policies
- [ ] Map OpenInsure document types to DMS document classes
- [ ] Implement upload/retrieval via API
- [ ] Migrate existing Blob documents to DMS

---

### D. Accounting / General Ledger (QuickBooks, SAP, Xero)

**Use Case:** Post premium income, claims expense, commission payments to GL.

**Integration Method:**

1. **Generate Journal Entries** from OpenInsure events:
   - Policy bound → Debit: Accounts Receivable, Credit: Unearned Premium
   - Policy effective → Debit: Unearned Premium, Credit: Earned Premium (pro-rata daily)
   - Claim reserved → Debit: Claims Expense, Credit: Claims Reserve Liability
   - Claim paid → Debit: Claims Reserve Liability, Credit: Cash

2. **Push to GL via API:**

**QuickBooks Online:**
```python
from quickbooks import QuickBooks
from quickbooks.objects.journalentry import JournalEntry, JournalEntryLine

qb_client = QuickBooks(access_token=QB_ACCESS_TOKEN, company_id=QB_COMPANY_ID)

# Create journal entry for policy bound
je = JournalEntry()
je.DocNumber = f"POL-{policy.policy_number}"
je.TxnDate = policy.bound_date.strftime("%Y-%m-%d")
je.Line = [
    JournalEntryLine.where(
        Account=qb_client.Account.where(Name="Accounts Receivable")[0],
        Amount=policy.premium,
        DetailType="JournalEntryLineDetail",
        JournalEntryLineDetail={"PostingType": "Debit"}
    ),
    JournalEntryLine.where(
        Account=qb_client.Account.where(Name="Unearned Premium")[0],
        Amount=policy.premium,
        DetailType="JournalEntryLineDetail",
        JournalEntryLineDetail={"PostingType": "Credit"}
    )
]
je.save()
```

**SAP (via Foundry Connector):**
- Use Azure AI Foundry Tools connector for SAP
- Send JournalEntry XML via SAP BAPI

**Setup Checklist:**
- [ ] Define chart of accounts mapping (OpenInsure categories → GL accounts)
- [ ] Implement journal entry generation on domain events
- [ ] Test with sandbox accounting system
- [ ] Schedule daily batch sync for historical data

---

### E. CRM (Salesforce, Dynamics 365)

**Use Case:** Sync parties (brokers, policyholders) and opportunities.

**Integration Pattern:**

**Salesforce:**
```python
from simple_salesforce import Salesforce

sf = Salesforce(username=SF_USER, password=SF_PASS, security_token=SF_TOKEN)

# Sync broker to Salesforce as Account
def sync_broker_to_salesforce(broker: Party):
    sf.Account.create({
        "Name": broker.legal_name,
        "Type": "Broker",
        "Phone": broker.primary_phone,
        "BillingStreet": broker.addresses[0].street,
        "BillingCity": broker.addresses[0].city,
        "BillingState": broker.addresses[0].state,
        "BillingPostalCode": broker.addresses[0].postal_code,
        "External_ID__c": str(broker.id)
    })

# Sync submission to Salesforce as Opportunity
def sync_submission_to_salesforce(submission: Submission):
    sf.Opportunity.create({
        "Name": f"{submission.insured_name} - {submission.lob.upper()}",
        "StageName": "Qualification",
        "CloseDate": submission.requested_effective_date.strftime("%Y-%m-%d"),
        "Amount": submission.quoted_premium if submission.status == "quoted" else None,
        "AccountId": get_salesforce_account_id(submission.broker_id),
        "External_ID__c": str(submission.id)
    })
```

**Dynamics 365 (via Microsoft Graph):**
- Use Microsoft Graph API to sync contacts and opportunities
- Bidirectional sync: CRM updates push back to OpenInsure via webhook

**Setup Checklist:**
- [ ] Map OpenInsure Party → CRM Account/Contact
- [ ] Map Submission → CRM Opportunity
- [ ] Implement bidirectional sync (CRM webhook → OpenInsure API)
- [ ] Resolve duplicate detection (match by email, external ID)

---

### F. Rating Bureau (ISO, AAIS)

**Use Case:** Import state-mandated loss costs and rating factors.

**Integration Pattern:**

1. **Download ISO ERC Data Feed** (Excel or XML)
2. **Parse and Load into Knowledge Base:**
   ```python
   import pandas as pd
   
   # Parse ISO ERC Excel file
   df = pd.read_excel("iso_erc_commercial_property_2025.xlsx")
   
   for _, row in df.iterrows():
       doc = {
           "id": f"ISO-RATE-{row['State']}-{row['Class']}",
           "title": f"ISO Loss Cost - {row['State']} - Class {row['Class']}",
           "doc_type": "rating_factor",
           "content": f"Base loss cost: ${row['Loss_Cost']}/100 of exposure",
           "tags": ["ISO", row["State"], "commercial_property"],
           "effective_date": row["Effective_Date"],
           "status": "active",
           "rating_table": {
               "base_loss_cost": row["Loss_Cost"],
               "state": row["State"],
               "class_code": row["Class"]
           }
       }
       
       requests.post(f"{API_URL}/knowledge", json=doc, headers={"X-API-Key": API_KEY})
   ```

3. **Underwriting Agent References ISO Rates:**
   - Agent retrieves loss cost from knowledge base by state + class code
   - Applies carrier's loss cost multiplier (LCM) and expense load
   - Calculates final rate

**Setup Checklist:**
- [ ] Subscribe to ISO ERC or AAIS data feeds
- [ ] Implement parser for rating bureau data formats
- [ ] Load into knowledge base with `doc_type: rating_factor`
- [ ] Configure agents to reference ISO rates in premium calculations

---

### G. Regulatory Filing (SERFF, Lloyd's)

**Use Case:** Submit rate filings, policy forms, and compliance reports to state DOIs.

**Current State:** No integration. Compliance module tracks decision records but does not generate filing formats.

**Integration Pattern:**

**SERFF (State Electronic Rate and Form Filing):**
- Export rate tables and policy forms in SERFF XML format
- Upload to SERFF portal via API (requires state-specific credentials)

**Lloyd's Market:**
- Generate bordereaux in Lloyd's-specified format (CSV or XML)
- Submit via Lloyd's Policy Signing Office API

**Setup Checklist:**
- [ ] Register for SERFF credentials per state
- [ ] Implement SERFF XML export (rate filings, form filings)
- [ ] Schedule quarterly compliance reports
- [ ] For Lloyd's: integrate with MODA (Market Operations Data)

---

## 7. Data Migration

Migrating existing policies, claims, and parties from a legacy system into OpenInsure.

### Migration Approach

1. **Extract Data** from legacy system (SQL export, API, CSV)
2. **Transform to OpenInsure Schema** (Python ETL scripts)
3. **Load via Bulk API** (batched POST requests)
4. **Validate** (reconcile counts, spot-check data integrity)

### Migration Script Example

```python
import pandas as pd
import requests
from datetime import datetime

API_URL = "https://<your-backend-url>/api/v1"
API_KEY = "<your-api-key>"

# Step 1: Extract legacy policies
legacy_policies = pd.read_csv("legacy_policies.csv")

# Step 2: Transform to OpenInsure schema
for _, row in legacy_policies.iterrows():
    policy = {
        "policy_number": row["policy_id"],
        "product_id": map_product(row["product_code"]),  # Map legacy product codes
        "policyholder_id": find_or_create_party(row["insured_name"], row["insured_email"]),
        "effective_date": datetime.strptime(row["effective_date"], "%Y-%m-%d").isoformat(),
        "expiration_date": datetime.strptime(row["expiration_date"], "%Y-%m-%d").isoformat(),
        "premium": float(row["premium"]),
        "limit": int(row["limit"]),
        "deductible": int(row["deductible"]),
        "status": "active" if row["status"] == "ACTIVE" else "expired",
        "lob": row["line_of_business"].lower(),
        "territory": row["state"],
        "rating_info": {
            "base_rate": row.get("base_rate"),
            "rate_factors": {}
        }
    }
    
    # Step 3: Load via API
    response = requests.post(
        f"{API_URL}/policies/bulk",
        json=policy,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"}
    )
    
    if response.status_code != 201:
        print(f"Failed to migrate policy {row['policy_id']}: {response.text}")

print("Migration complete. Validate counts:")
print(f"Legacy policies: {len(legacy_policies)}")
print(f"OpenInsure policies: {requests.get(f'{API_URL}/policies', headers={'X-API-Key': API_KEY}).json()['total']}")
```

### Data Mapping

| Legacy Field | OpenInsure Field | Transformation |
|--------------|------------------|----------------|
| `policy_id` | `policy_number` | Direct mapping |
| `insured_name` | `policyholder.legal_name` | Create Party entity first |
| `product_code` | `product_id` | Map legacy codes to OpenInsure product UUIDs |
| `effective_date` | `effective_date` | Parse date format |
| `premium` | `premium` | Convert to Decimal |
| `coverages` (JSON) | `coverages` array | Parse and map to OpenInsure coverage schema |

### Migration Validation

**Post-Migration Checks:**

```python
# Count reconciliation
legacy_count = len(pd.read_csv("legacy_policies.csv"))
openinsure_count = requests.get(f"{API_URL}/policies", headers={"X-API-Key": API_KEY}).json()["total"]
assert legacy_count == openinsure_count, "Policy count mismatch!"

# Premium reconciliation
legacy_premium_sum = pd.read_csv("legacy_policies.csv")["premium"].sum()
openinsure_premium_sum = requests.get(f"{API_URL}/policies/metrics", headers={"X-API-Key": API_KEY}).json()["total_premium"]
assert abs(legacy_premium_sum - openinsure_premium_sum) < 1.0, "Premium sum mismatch!"

# Spot-check 10 random policies
import random
sample_policies = random.sample(legacy_policies["policy_id"].tolist(), 10)
for policy_num in sample_policies:
    legacy_policy = legacy_policies[legacy_policies["policy_id"] == policy_num].iloc[0]
    openinsure_policy = requests.get(f"{API_URL}/policies?policy_number={policy_num}", headers={"X-API-Key": API_KEY}).json()[0]
    
    assert legacy_policy["premium"] == openinsure_policy["premium"], f"Premium mismatch for {policy_num}"
    assert legacy_policy["effective_date"] == openinsure_policy["effective_date"][:10], f"Date mismatch for {policy_num}"

print("✅ Migration validation passed")
```

### Claims Migration

Migrate claims separately after policies are loaded (claims reference `policy_id`):

```python
legacy_claims = pd.read_csv("legacy_claims.csv")

for _, row in legacy_claims.iterrows():
    # Find corresponding policy in OpenInsure
    policy_response = requests.get(
        f"{API_URL}/policies?policy_number={row['policy_number']}",
        headers={"X-API-Key": API_KEY}
    )
    policy_id = policy_response.json()[0]["id"]
    
    claim = {
        "claim_number": row["claim_id"],
        "policy_id": policy_id,
        "loss_date": datetime.strptime(row["loss_date"], "%Y-%m-%d").isoformat(),
        "reported_date": datetime.strptime(row["reported_date"], "%Y-%m-%d").isoformat(),
        "loss_description": row["description"],
        "claim_amount": float(row["amount_paid"]) if row["status"] == "CLOSED" else None,
        "reserve_amount": float(row["reserve"]) if row["status"] != "CLOSED" else 0,
        "status": map_claim_status(row["status"]),
        "claimant_name": row["claimant"]
    }
    
    response = requests.post(
        f"{API_URL}/claims",
        json=claim,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"}
    )
    
    if response.status_code != 201:
        print(f"Failed to migrate claim {row['claim_id']}: {response.text}")
```

### Migration Checklist

- [ ] Export all data from legacy system (policies, claims, parties, billing)
- [ ] Map legacy schema to OpenInsure schema (create mapping document)
- [ ] Create Products in OpenInsure matching legacy products
- [ ] Migrate Parties (brokers, policyholders, vendors)
- [ ] Migrate Policies (with full history: endorsements, cancellations)
- [ ] Migrate Claims (link to migrated policies)
- [ ] Migrate Billing History (if billing module implemented)
- [ ] Validate counts and financial totals
- [ ] Spot-check 5% of records manually
- [ ] Run smoke tests on migrated data
- [ ] Schedule cutover date (stop writing to legacy, start writing to OpenInsure)

---

## 8. Going Live Checklist

Complete this checklist before enabling user access to production.

### Infrastructure

- [ ] All Bicep deployments completed successfully
- [ ] Azure SQL Database provisioned and schema deployed
- [ ] Cosmos DB provisioned with `knowledge-prod` database
- [ ] Azure AI Search provisioned with indexes created
- [ ] Azure Blob Storage provisioned with 3 containers (`submissions`, `policies`, `claims`)
- [ ] Service Bus namespace provisioned with topics and subscriptions
- [ ] Log Analytics Workspace and Application Insights configured
- [ ] 10 Foundry agents deployed on Azure AI Foundry
- [ ] Container Apps deployed (backend + dashboard)
- [ ] Custom domain configured with SSL certificate (if applicable)
- [ ] VNet and private endpoints configured (if applicable)
- [ ] Azure Key Vault provisioned with secrets stored
- [ ] Monitoring alerts configured (CPU > 80%, error rate > 5%, SQL DTU > 80%)

### Security & Identity

- [ ] Azure Entra ID app registration created
- [ ] 11 app roles defined in Entra ID
- [ ] Users assigned to roles
- [ ] JWT authentication configured in backend (`AUTH_MODE=jwt`)
- [ ] `X-User-Role` header mode disabled in production
- [ ] API keys generated for M2M integrations
- [ ] RBAC policies configured in backend (authority limits per role)
- [ ] Managed Identity assigned to Container Apps
- [ ] Managed Identity granted access to SQL, Cosmos, Storage, Service Bus, Key Vault
- [ ] Network security groups configured (if using VNet)
- [ ] Firewall rules configured for SQL Database (allow Azure services)

### Data & Configuration

- [ ] Knowledge base populated (100+ documents: guidelines, rating factors, precedents)
- [ ] AI Search indexes populated and tested
- [ ] Products configured (cyber, property, liability, etc.)
- [ ] Rating tables loaded into knowledge base
- [ ] Regulatory documents loaded (state requirements, exclusions, forms)
- [ ] Policy forms uploaded to Blob Storage and linked to products
- [ ] Authority delegation matrix configured in database
- [ ] Broker/agent licensing data imported (if required)
- [ ] Data migration completed (if applicable)
- [ ] Data migration validated (counts, totals, spot-checks)

### Integrations

- [ ] Payment gateway integration tested (Stripe webhook confirmed)
- [ ] Email notification service configured (Azure Communication Services)
- [ ] Email templates created and tested
- [ ] Document management system integrated (SharePoint, OnBase, or Blob only)
- [ ] CRM integration configured (Salesforce, Dynamics 365, or none)
- [ ] Accounting/GL integration configured (QuickBooks, SAP, or manual)
- [ ] External data providers configured (SecurityScorecard, BitSight, or none)
- [ ] Rating bureau data feeds configured (ISO, AAIS, or none)

### Testing

- [ ] Smoke tests passed on production (`python scripts/smoke_test.py <backend-url>`)
- [ ] End-to-end workflow tested: submission → quote → bind → policy issued
- [ ] Claims workflow tested: FNOL → reserve set → settlement
- [ ] Renewal workflow tested: policy renewed, new policy created
- [ ] Endorsement workflow tested: mid-term change, premium adjustment
- [ ] Cancellation workflow tested: cancel-for-non-payment, reinstatement
- [ ] Authority escalation tested: submission exceeds limit, escalated to CUO
- [ ] AI agent confidence testing: low-confidence decisions escalated
- [ ] Compliance audit tested: decision records generated, bias metrics computed
- [ ] Dashboard accessibility tested (WCAG 2.1 AA compliance)
- [ ] Load testing completed (100 concurrent users, 1000 submissions/day)
- [ ] Security scan completed (OWASP ZAP, Snyk, Bandit)
- [ ] Penetration testing completed (if required by compliance)

### Monitoring & Operations

- [ ] Application Insights dashboards created (requests, exceptions, performance)
- [ ] Azure Monitor alerts configured (CPU, memory, error rate, latency)
- [ ] Log retention policies set (90 days for operational, 7 years for compliance)
- [ ] Backup policies configured (SQL automated backups, Cosmos continuous backup)
- [ ] Disaster recovery plan documented (RPO: 1 hour, RTO: 4 hours)
- [ ] Runbook created for common issues (agent downtime, database failover, deployment rollback)
- [ ] On-call rotation established (PagerDuty, Azure Monitor action groups)
- [ ] Incident response plan documented (security breach, data loss, service outage)

### Documentation & Training

- [ ] User training completed (underwriters, claims adjusters, finance, compliance)
- [ ] Administrator training completed (platform admin, product manager)
- [ ] User guides published (broker portal, underwriting workbench, claims workbench)
- [ ] API documentation published (Swagger at `<backend-url>/docs`)
- [ ] MCP server documentation published (for integrations)
- [ ] Change management process documented (how to update products, guidelines, authority limits)
- [ ] Support escalation process documented (Tier 1: operations, Tier 2: platform admin, Tier 3: engineering)

### Legal & Compliance

- [ ] Data privacy policy published (GDPR, CCPA compliance)
- [ ] Terms of service published (for brokers, policyholders)
- [ ] Consent forms for AI decision-making (EU AI Act, if applicable)
- [ ] Regulatory filings submitted (state DOI notifications of system change)
- [ ] Insurance licenses verified (carrier license, MGA authority)
- [ ] E&O insurance policy in force (covers AI decision errors)
- [ ] Audit trail retention policy set (7 years for financial, 10 years for claims)
- [ ] Bias monitoring enabled (4/5ths rule analysis on underwriting decisions)

### Go/No-Go Decision

**Final approval required from:**
- [ ] CEO (business readiness)
- [ ] CTO (technical readiness)
- [ ] CUO (underwriting readiness)
- [ ] CFO (financial controls readiness)
- [ ] Compliance Officer (regulatory readiness)

**Cutover Plan:**
1. **T-7 days:** Final data migration, freeze legacy system writes
2. **T-3 days:** User training sessions, walkthrough of workflows
3. **T-1 day:** Go/no-go meeting, final smoke tests
4. **T-0 (Go Live Day):**
   - 8:00 AM: Enable user access, announce via email
   - 9:00 AM: Monitor dashboards, watch for errors
   - 12:00 PM: Check-in with CUO, Claims Manager (any issues?)
   - 5:00 PM: End-of-day review, review submission/claim counts
5. **T+1 day:** Morning stand-up, address any overnight issues
6. **T+7 days:** Post-go-live retrospective, document lessons learned

---

## 9. Ongoing Operations

After go-live, the platform requires regular maintenance and continuous improvement.

### Daily Operations

**Operations Lead / Platform Administrator:**

- **Morning:** Review Application Insights dashboard for overnight errors
  - Check error rate (should be < 1%)
  - Review failed API requests
  - Check Foundry agent uptime (all 10 agents running?)
- **Throughout Day:** Monitor escalation queue
  - Review submissions escalated to CUO (agent confidence < 0.7)
  - Review claims escalated to Claims Manager (large reserves, fraud flags)
- **End of Day:** Review submission and claim counts
  - Compare to historical average (flag anomalies)
  - Check that renewals are being generated (90 days before expiry)

**CUO / Senior Underwriters:**

- **Review Escalated Submissions** (typically 5–10% of total volume)
  - Agent provides full context package (risk summary, comparables, recommended terms, confidence score)
  - Approve, modify, or decline
  - Override reason is logged (trains the learning loop)
- **Monitor Portfolio Metrics:**
  - GWP growth vs. plan
  - Loss ratio by LOB
  - Hit ratio (quotes issued / submissions received)
  - Quote-to-bind ratio
- **Adjust Appetite:**
  - If loss ratio climbing, tighten guidelines in knowledge base (agent behavior changes immediately)
  - If hit ratio dropping, review decline reasons (too aggressive? broker feedback?)

**Claims Manager / Adjusters:**

- **Review New FNOLs** (agent handles intake, adjuster reviews and assigns)
- **Approve Reserves** (agent recommends, adjuster confirms if > authority limit)
- **Approve Settlements** (agent negotiates, adjuster approves if > authority limit)
- **Monitor Claims Metrics:**
  - Average time to reserve set (target: < 48 hours)
  - Average time to settlement (target: < 30 days for small claims)
  - Reserve adequacy (actual vs. reserved on closed claims)
  - Fraud flags (agent flags suspicious claims, adjuster investigates)

**Finance Lead:**

- **Daily Reconciliation:**
  - Premiums collected vs. invoices issued
  - Claims paid vs. approved settlements
  - Commission payments to brokers
- **Weekly:**
  - Unearned premium roll-forward (daily pro-rata)
  - Loss reserve adequacy review
  - Cash flow forecast
- **Monthly:**
  - Financial close (premium income, claims expense, underwriting profit)
  - Statutory reporting (if carrier)

**Compliance Officer:**

- **Weekly:** Review bias monitoring report
  - Check 4/5ths rule on underwriting decisions (no protected class < 80% approval rate)
  - Investigate any bias flags
- **Monthly:** Audit decision records
  - Sample 5% of underwriting decisions, verify reasoning chain is complete
  - Sample 5% of claims decisions, verify coverage analysis is documented
- **Quarterly:** Regulatory reporting
  - Submit compliance reports to state DOIs (as required)
  - Update EU AI Act documentation (if applicable)

### Weekly Operations

**Product Manager:**

- **Review Agent Performance:**
  - Agent confidence score distribution (how often are agents uncertain?)
  - Override rate (how often do humans override agent recommendations?)
  - Processing time (how long does each workflow step take?)
- **Refine Knowledge Base:**
  - Add new guidelines for novel risks
  - Update rating factors based on loss experience
  - Add claims precedents from recent settlements
- **Product Configuration:**
  - Adjust product limits, deductibles based on market demand
  - Create new endorsements based on broker requests

**Engineering / DevOps:**

- **Security Patching:** Review Azure Advisor recommendations, apply patches
- **Performance Tuning:** Review Application Insights performance metrics, optimize slow queries
- **Cost Management:** Review Azure Cost Management, identify opportunities to reduce spend
- **Backup Verification:** Test restore from backup (randomly select a snapshot, restore to test environment)

### Monthly Operations

**Platform Review Meeting (all stakeholders):**

- **Volume Metrics:**
  - Submissions received, quoted, bound (by LOB, by broker)
  - Claims reported, reserved, settled, closed
  - Policies renewed, cancelled, reinstated
- **Financial Metrics:**
  - GWP (by LOB, by territory, by product)
  - Loss ratio (by LOB, by cohort)
  - Combined ratio (loss ratio + expense ratio)
  - Commission expense
- **Quality Metrics:**
  - Agent confidence score distribution
  - Override rate by persona
  - Time-to-quote (target: < 24 hours)
  - Time-to-bind (target: < 48 hours after quote acceptance)
- **Compliance Metrics:**
  - Bias monitoring results (any flags?)
  - Audit trail completeness (100% of decisions logged?)
  - Regulatory filings submitted on time

**Continuous Improvement:**

- **Identify Top 3 Pain Points** (based on user feedback, override analysis)
- **Prioritize Knowledge Base Updates** (what guidelines are missing? what causes most escalations?)
- **Roadmap Review:** What features should we build next? (refer to process-completeness.md gap analysis)

### Quarterly Operations

**Agent Retraining (Learning Loop):**

- **Collect Override Data:** Export all human overrides with reasoning
- **Retrain Foundry Agents:** Fine-tune agents using override data as labeled examples
- **A/B Test:** Deploy updated agents to 10% of submissions, compare override rate
- **Rollout:** If override rate decreases, deploy to 100% of submissions

**Knowledge Base Audit:**

- **Verify All Guidelines Are Current:** Check effective dates, flag superseded guidelines
- **Identify Gaps:** What questions do agents struggle with? What triggers low confidence?
- **Add Missing Content:** Underwriting precedents, claims precedents, regulatory updates

**Portfolio Review:**

- **Loss Ratio by Cohort:** Analyze loss ratio by inception quarter (calendar year vs. accident year)
- **Reserve Adequacy:** Compare initial reserves vs. ultimate losses on closed claims
- **Rate Adequacy:** Are current rates producing target loss ratio? Need rate increase/decrease?
- **Reinsurance Utilization:** How much capacity used? Any concentration risk?

**Compliance Audit (External):**

- **Engage Third-Party Auditor** (annually or as required by regulator)
- **Provide Access to Decision Records, Audit Trails**
- **Review Findings, Remediate Any Issues**

### Handling Common Scenarios

**Scenario: Agent is Escalating Too Many Submissions (> 20%)**

**Diagnosis:**
- Check agent confidence scores: Are they consistently low?
- Review escalated submissions: Is there a pattern? (e.g., all healthcare, all large limits)

**Fix:**
1. **Add Missing Guidelines:** If agent is escalating novel risks, add guidelines to knowledge base
2. **Adjust Confidence Threshold:** If agent is overly cautious, lower escalation threshold from 0.7 to 0.6
3. **Retrain Agent:** Collect override data, fine-tune agent

**Scenario: Loss Ratio Climbing on Cyber LOB**

**Diagnosis:**
- Review recent claims: What's driving losses? (ransomware, data breach, business interruption)
- Review recent bindings: Are we writing riskier accounts?

**Fix:**
1. **Tighten Underwriting Guidelines:** Update knowledge base to require higher security standards
2. **Increase Rates:** Update rating table with higher base rates or stronger security score factors
3. **Add Exclusions:** Exclude specific high-risk industries or add security subjectivities
4. **Communicate to Brokers:** Notify brokers of appetite change

**Scenario: Azure AI Search Index is Stale (Agents Returning Outdated Guidelines)**

**Diagnosis:**
- Check AI Search index last updated timestamp
- Compare Cosmos DB document count vs. AI Search document count

**Fix:**
1. **Trigger Full Reindex:**
   ```bash
   az search indexer run \
     --service-name "openinsure-prod-search-<uniqueId>" \
     --resource-group "$RESOURCE_GROUP" \
     --name "knowledge-indexer"
   ```
2. **Verify Indexer Status:**
   ```bash
   az search indexer show \
     --service-name "openinsure-prod-search-<uniqueId>" \
     --resource-group "$RESOURCE_GROUP" \
     --name "knowledge-indexer"
   ```
3. **Automate:** Set up scheduled indexing (every 15 minutes) in AI Search indexer configuration

**Scenario: Foundry Agent Returns 500 Error**

**Diagnosis:**
- Check Application Insights for agent invocation errors
- Check Foundry portal for agent status (running? failed?)

**Fix:**
1. **Restart Agent:**
   ```bash
   az rest --method POST \
     --uri "/subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.MachineLearningServices/workspaces/<workspace>/agents/<agent-name>/restart?api-version=2024-07-01"
   ```
2. **Check Agent Logs** in Foundry portal for error messages
3. **Escalate to Engineering** if issue persists (may be a model API outage)

---

## Appendix: Useful Commands

### Query Azure Resources

```bash
# List all Container Apps
az containerapp list --resource-group "$RESOURCE_GROUP" -o table

# Get Container App logs (last 100 lines)
az containerapp logs show \
  --name "openinsure-backend" \
  --resource-group "$RESOURCE_GROUP" \
  --tail 100

# Get SQL connection string
az sql db show-connection-string \
  --client ado.net \
  --server "<server-name>" \
  --name "<db-name>"

# List Blob containers
az storage container list \
  --account-name "<storage-account-name>" \
  --auth-mode login -o table

# List Service Bus topics
az servicebus topic list \
  --resource-group "$RESOURCE_GROUP" \
  --namespace-name "<namespace-name>" -o table
```

### Foundry Agent Management

```bash
# List all deployed agents
az ml online-endpoint list \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "<foundry-project>" -o table

# Get agent logs
az ml online-endpoint get-logs \
  --name "<agent-name>" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "<foundry-project>"

# Update agent configuration (e.g., change model)
az ml online-deployment update \
  --name "<agent-name>" \
  --endpoint-name "<agent-name>" \
  --resource-group "$RESOURCE_GROUP" \
  --workspace-name "<foundry-project>" \
  --set model=gpt-4o
```

### Database Queries

```sql
-- Check submission volume by status
SELECT status, COUNT(*) as count, SUM(requested_premium) as total_premium
FROM submissions
WHERE received_date >= DATEADD(day, -30, GETDATE())
GROUP BY status;

-- Check claims by status
SELECT status, COUNT(*) as count, SUM(reserve_amount) as total_reserves
FROM claims
WHERE reported_date >= DATEADD(day, -30, GETDATE())
GROUP BY status;

-- Check policy count and GWP
SELECT 
  lob,
  COUNT(*) as policy_count,
  SUM(premium) as gross_written_premium,
  AVG(premium) as average_premium
FROM policies
WHERE status = 'active'
GROUP BY lob;

-- Check authority delegation matrix
SELECT u.name, ad.action_type, ad.limit_amount, ad.lob
FROM authority_delegations ad
JOIN users u ON ad.user_id = u.id
ORDER BY u.name, ad.action_type;
```

---

## Next Steps

After completing this integration guide:

1. **Review Process Completeness:** See `docs/architecture/process-completeness.md` for remaining gaps (billing, document generation, subrogation)
2. **Join the Community:** Contribute to OpenInsure on GitHub, report issues, suggest features
3. **Schedule Training:** Book a session with your team to walk through workflows
4. **Plan Phase 2:** Review the roadmap and prioritize next features (e.g., billing API, rating table UI)

**Questions?** Contact the OpenInsure team or file an issue at https://github.com/<your-org>/openinsure/issues.

---

**Document Version:** 1.0  
**Last Updated:** 2025-01-27  
**Maintained By:** OpenInsure Insurance + Infra Squads
