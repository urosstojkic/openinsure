"""Test the document upload API with the synthetic PDF."""

import httpx

BE = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io/api/v1"
H = {"X-API-Key": "dev-key-change-me"}

# Create submission
r = httpx.post(
    f"{BE}/submissions",
    json={
        "applicant_name": "Meridian Health Technologies",
        "line_of_business": "cyber",
        "effective_date": "2026-07-01",
        "expiration_date": "2027-07-01",
        "cyber_risk_data": {
            "annual_revenue": 28500000,
            "employee_count": 215,
            "industry": "Healthcare IT",
            "sic_code": "8071",
            "security_maturity_score": 7,
            "prior_incidents": 2,
        },
    },
    headers=H,
    timeout=30,
)
sid = r.json().get("id")
print(f"Created submission: {sid}")

# Upload PDF
with open("test-data/sample-submission.pdf", "rb") as f:
    r = httpx.post(
        f"{BE}/submissions/{sid}/documents",
        files={"files": ("sample-submission.pdf", f, "application/pdf")},
        headers={"X-API-Key": "dev-key-change-me"},
        timeout=60,
    )

print(f"Upload status: {r.status_code}")
if r.status_code in (200, 201):
    data = r.json()
    doc_ids = data.get("document_ids", [])
    print(f"Document IDs: {doc_ids}")
    print(f"Full response: {data}")
else:
    print(f"Error: {r.text[:500]}")
