# Developer Quickstart Guide

Get OpenInsure running locally in under 10 minutes.

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 20+ | [nodejs.org](https://nodejs.org/) |
| Git | 2.40+ | [git-scm.com](https://git-scm.com/) |
| pip | latest | `python -m pip install --upgrade pip` |

**Optional** (for Azure integration):

| Tool | Purpose | Install |
|------|---------|---------|
| Azure CLI | Azure resource management | `winget install Microsoft.AzureCLI` |
| Docker | Container builds | [docker.com](https://www.docker.com/) |

---

## 1. Clone & Install

```bash
# Clone the repository
git clone https://github.com/<your-org>/openinsure.git
cd openinsure

# Create a virtual environment
python -m venv .venv

# Activate it
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install Python dependencies
pip install -e ".[dev]"

# Install dashboard dependencies
cd dashboard && npm ci && cd ..
```

---

## 2. Environment Setup

Create a `.env` file in the project root (or copy `.env.example`):

```env
# Minimal local development config
OPENINSURE_STORAGE_MODE=memory    # In-memory storage (no database needed)
OPENINSURE_DEBUG=true             # Enable debug mode with sample data
OPENINSURE_APP_VERSION=dev
```

The in-memory storage mode seeds sample data on startup — no Azure SQL or Cosmos DB required for local development.

---

## 3. Run the Backend

```bash
# Start the FastAPI server
uvicorn openinsure.main:app --reload --port 8000
```

The API is now running at **http://localhost:8000**.

Verify it works:

```bash
curl http://localhost:8000/health
# → {"status":"healthy","checks":{"api":"ok"}}
```

Browse the interactive API docs at **http://localhost:8000/docs**.

---

## 4. Run the Dashboard

In a separate terminal:

```bash
cd dashboard
npm run dev
```

The dashboard is now running at **http://localhost:5173**.

---

## 5. Your First API Call

### Create a Submission

```bash
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -H "X-User-Role: underwriter" \
  -d '{
    "applicant_name": "Acme Cyber Corp",
    "applicant_email": "risk@acmecyber.com",
    "line_of_business": "cyber",
    "risk_data": {
      "annual_revenue": 5000000,
      "employee_count": 50,
      "industry": "Technology"
    }
  }'
```

### Triage the Submission

```bash
curl -X POST http://localhost:8000/api/v1/submissions/{submission_id}/triage \
  -H "X-User-Role: underwriter"
```

### Generate a Quote

```bash
curl -X POST http://localhost:8000/api/v1/submissions/{submission_id}/quote \
  -H "X-User-Role: underwriter"
```

### List All Submissions

```bash
curl http://localhost:8000/api/v1/submissions \
  -H "X-User-Role: underwriter"
```

> **Note:** In dev mode, `X-User-Role` header selects the role (no auth required).
> Valid roles: `underwriter`, `claims_adjuster`, `broker`, `admin`, `cuo`.

---

## 6. Run Tests

```bash
# Run all tests (fast — uses in-memory storage)
python -m pytest tests/ -x -q --ignore=tests/e2e/test_full_lifecycle.py

# Run with coverage
python -m pytest tests/ --cov=openinsure --cov-report=term-missing

# Lint
python -m ruff check src/ tests/ --fix
python -m ruff format src/ tests/

# Type check
python -m mypy src/openinsure/

# Security scan
python -m bandit -r src/openinsure/ -ll
```

---

## 7. Project Structure

```
openinsure/
├── src/openinsure/        # Backend source
│   ├── agents/            # 10 AI agents + Foundry client
│   ├── api/               # FastAPI routers (24 modules)
│   ├── domain/            # Pydantic entities + state machines
│   ├── infrastructure/    # Azure adapters, repositories, migrations
│   ├── services/          # Business logic (25 services)
│   ├── middleware.py       # HTTP middleware (broker scope, etc.)
│   └── main.py            # App entry point
├── dashboard/             # React 18 + TypeScript + Tailwind
├── infra/                 # Bicep IaC (11 modules)
├── tests/                 # Unit, integration, E2E tests
├── docs/                  # Technical documentation
└── scripts/               # Deploy, smoke test, migration scripts
```

---

## 8. Common Tasks

| Task | Command |
|------|---------|
| Start backend | `uvicorn openinsure.main:app --reload` |
| Start dashboard | `cd dashboard && npm run dev` |
| Run tests | `python -m pytest tests/ -x -q` |
| Lint & format | `python -m ruff check src/ --fix && python -m ruff format src/` |
| Build dashboard | `cd dashboard && npm run build` |
| API docs | http://localhost:8000/docs |

---

## Next Steps

- Read the [Technical Overview](../TECHNICAL_OVERVIEW.md) for architecture details
- Explore the [Feature Guide](feature-guide.md) for all 16 features
- See the [Enterprise Integration Guide](enterprise-integration-guide.md) for Azure setup
- Browse API docs at `/docs` (Swagger UI) or `/redoc` (ReDoc)
