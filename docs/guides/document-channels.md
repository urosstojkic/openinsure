# Document & Channel Integration Guide

How documents flow into OpenInsure — upload, OCR extraction, ACORD ingestion,
and what an email-to-submission pipeline would look like.

---

## 1. Upload a Document to a Submission

**Endpoint:** `POST /api/v1/documents/upload`

The upload endpoint accepts any file up to **50 MB**, classifies it, extracts
key fields via Azure Document Intelligence (or a regex fallback), and stores
the file in Azure Blob Storage.

### curl example

```bash
curl -X POST \
  "https://<backend>/api/v1/documents/upload?submission_id=SUB-001&document_type=application" \
  -H "X-API-Key: dev-key-change-me" \
  -F "file=@commercial_application.pdf"
```

### Query parameters

| Parameter       | Required | Description |
|-----------------|----------|-------------|
| `submission_id` | No       | Link the document to a submission |
| `policy_id`     | No       | Link to a policy |
| `claim_id`      | No       | Link to a claim |
| `document_type` | No       | Hint: `application`, `policy`, `claim`, `endorsement`, `other` |

### Response (abbreviated)

```json
{
  "filename": "commercial_application.pdf",
  "blob_name": "documents/SUB-001/commercial_application.pdf",
  "size": 245120,
  "storage": "azure",
  "classification": {
    "detected_type": "application",
    "confidence": 0.92
  },
  "extraction": {
    "source": "document_intelligence",
    "fields": {
      "applicant_name": "Acme Corp",
      "annual_revenue": "12000000",
      "employee_count": "150",
      "effective_date": "2026-01-01"
    }
  }
}
```

### Other document endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/v1/documents/list?prefix=documents/SUB-001` | List documents for a submission |
| `GET`  | `/api/v1/documents/download/{blob_name}` | Get a 1-hour signed download URL |

---

## 2. Ingest an ACORD XML Application

**Endpoint:** `POST /api/v1/submissions/acord-ingest`

Upload an ACORD 125/126 XML file and the system parses it into a submission
automatically.  Supports both namespaced (`urn:ACORD`) and plain XML.

### curl example

```bash
curl -X POST \
  "https://<backend>/api/v1/submissions/acord-ingest" \
  -H "X-API-Key: dev-key-change-me" \
  -F "file=@acord125.xml"
```

### What gets extracted

| Field | Source XPath (simplified) |
|-------|--------------------------|
| Applicant name | `InsuredOrPrincipal/GeneralPartyInfo/NameInfo/CommlName/CommercialName` |
| Email / phone | `Communications/EmailAddr`, `PhoneNumber` |
| Annual revenue | `CommlSubEntity/AnnualRevenue` or `NumEmployees` |
| SIC / NAICS | `SICCd`, `NAICSCd` |
| Policy dates | `ContractTerm/EffectiveDt`, `ExpirationDt` |
| Limits / deductibles | `Limit/FormatCurrencyAmt`, `Deductible` |
| Loss history | `LossCd`, `ClaimAmt`, `DateOfLoss` |
| Coverages | `Coverage/CoverageCd`, `CoverageDesc` |

### Response

Returns a full `SubmissionResponse` (same as `POST /submissions`) with
`metadata.source = "acord_xml"` and `channel = "api"`.

---

## 3. How Document Intelligence OCR Works

OpenInsure uses **Azure AI Document Intelligence** (`prebuilt-document` model)
to extract structured data from uploaded files.

### Processing flow

```
Upload file
  ↓
DocumentIntelligenceAdapter.analyze_document(content, content_type)
  ↓
Azure DI returns:
  • pages — page count
  • text  — full OCR text
  • key_value_pairs — extracted KV pairs with confidence scores
  • tables — structured tabular data
  • fields — typed document-level fields
  ↓
DocumentProcessingService maps extracted data → insurance fields
```

### Fallback mode

When Azure Document Intelligence is not configured (no
`OPENINSURE_DOCUMENT_INTELLIGENCE_ENDPOINT`), the system falls back to
**regex-based extraction** that looks for common patterns:

- `Applicant:`, `Insured Name:` → applicant/insured name
- `Policy Number:`, `Policy #:` → policy number
- `Premium:`, `Annual Premium:` → premium amount
- `Revenue:`, `Annual Revenue:` → revenue
- Date patterns (`MM/DD/YYYY`, `YYYY-MM-DD`) → effective/expiration dates
- `SIC:`, `NAICS:` → industry codes

### Configuration

```bash
# Set in environment or .env
OPENINSURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://<resource>.cognitiveservices.azure.com
# Authentication via DefaultAzureCredential (Managed Identity in Azure)
```

---

## 4. Email-to-Submission Flow (Not Yet Built)

The domain model already supports `channel = "email"` as a submission source,
but there is **no inbound email processing** in the current codebase.  Here is
the recommended architecture:

### Target architecture

```
Incoming email (broker/applicant)
  ↓
Azure Communication Services  ←or→  Microsoft 365 + Power Automate
  ↓
Azure Event Grid / Service Bus topic
  ↓
OpenInsure event consumer (ServiceBusAdapter.subscribe)
  ↓
Parse email → extract attachments
  ↓
POST /api/v1/documents/upload   (each attachment)
POST /api/v1/submissions        (create submission from email body)
  ↓
Submission created with channel="email"
```

### What already exists

| Component | Status | Notes |
|-----------|--------|-------|
| `SubmissionChannel.EMAIL` | ✅ Defined | Enum value in domain model |
| Event Bus adapter | ✅ Built | `EventBusAdapter` publishes to Event Grid, consumes from Service Bus |
| Service Bus consumer | ✅ Built | `subscribe()` and `process_events()` methods |
| Document upload + OCR | ✅ Built | Full pipeline for attachment processing |
| ACORD XML parser | ✅ Built | Handles ACORD 125/126 attachments |
| Email parsing / SMTP listener | ❌ Not built | Need email → event bridge |
| Email reply / notification sending | ❌ Not built | Would use Azure Communication Services |

### What needs to be built

1. **Email ingestion bridge** — Azure Logic App or Function that receives
   emails (via Exchange connector or Azure Communication Services), extracts
   the body + attachments, and publishes to the `openinsure-events` Service Bus
   queue.

2. **Email event handler** — A new service
   (`src/openinsure/services/email_handler.py`) that subscribes to the Service
   Bus queue, parses the event payload, uploads attachments via the document
   pipeline, and creates a submission with `channel="email"`.

3. **Outbound notifications** — Optional: send email confirmations back to the
   broker/applicant when the submission is received, triaged, or quoted.  Use
   Azure Communication Services Email or SendGrid.

### Configuration needed

```bash
# Service Bus (already in config.py)
OPENINSURE_SERVICEBUS_CONNECTION_STRING=Endpoint=sb://...
OPENINSURE_SERVICEBUS_QUEUE_NAME=openinsure-events

# Event Grid (already in config.py)
OPENINSURE_EVENTGRID_ENDPOINT=https://<topic>.swedencentral-1.eventgrid.azure.net

# Email (new — would need to add to config.py)
OPENINSURE_EMAIL_CONNECTION_STRING=endpoint=https://...
OPENINSURE_EMAIL_SENDER=noreply@openinsure.example.com
```

---

## 5. Channel Summary

| Channel | Ingest Method | Status |
|---------|--------------|--------|
| **Portal** | React dashboard → `POST /submissions` | ✅ Working |
| **API** | Direct REST calls | ✅ Working |
| **Broker** | API with `channel="broker"` | ✅ Working |
| **ACORD XML** | `POST /submissions/acord-ingest` | ✅ Working |
| **Document upload** | `POST /documents/upload` with OCR | ✅ Working |
| **Email** | Service Bus consumer → submission | ❌ Planned |
| **Agent** | API with `channel="agent"` | ✅ Working |
