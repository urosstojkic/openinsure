"""Test script to verify role-based escalations work end-to-end.

Creates a submission as 'underwriter' (UW Analyst, $50K quote limit),
triages it, quotes it, and checks that escalations fire for premiums > $50K.
"""

import json
import sys
import uuid

import httpx

BASE = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
HEADERS = {"Content-Type": "application/json", "X-User-Role": "underwriter"}


def main() -> None:
    client = httpx.Client(base_url=BASE, headers=HEADERS, timeout=30)

    # 1. Create submission
    print("\n=== Step 1: Create submission as underwriter ===")
    submission = {
        "applicant_name": f"Escalation Test {uuid.uuid4().hex[:6]}",
        "applicant_email": "test@example.com",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {
            "company_name": "Large Corp Inc",
            "annual_revenue": 50_000_000,
            "employee_count": 5000,
            "industry": "financial_services",
            "years_in_business": 20,
            "prior_claims": 3,
            "coverage_limit_requested": 10_000_000,
        },
    }
    r = client.post("/api/v1/submissions", json=submission)
    print(f"  Status: {r.status_code}")
    if r.status_code not in (200, 201):
        print(f"  Error: {r.text}")
        sys.exit(1)
    data = r.json()
    sub_id = data["id"]
    print(f"  Submission ID: {sub_id}")

    # 2. Triage
    print("\n=== Step 2: Triage submission ===")
    r = client.post(f"/api/v1/submissions/{sub_id}/triage")
    print(f"  Status: {r.status_code}")
    if r.status_code not in (200, 201):
        print(f"  Error: {r.text}")
        sys.exit(1)
    triage = r.json()
    print(f"  Risk score: {triage.get('risk_score')}")
    print(f"  Recommendation: {triage.get('recommendation')}")

    # 3. Quote
    print("\n=== Step 3: Quote submission (expecting escalation for > $50K) ===")
    r = client.post(f"/api/v1/submissions/{sub_id}/quote")
    print(f"  Status: {r.status_code}")
    quote = r.json()
    print(f"  Response: {json.dumps(quote, indent=2, default=str)[:500]}")

    escalated = r.status_code == 202
    premium = quote.get("premium")
    authority = quote.get("authority", {})

    if escalated:
        print(f"\n  ✅ ESCALATION TRIGGERED (202)!")
        print(f"     Premium: ${premium:,.2f}" if premium else "")
        print(f"     Decision: {authority.get('decision')}")
        print(f"     Reason: {authority.get('reason')}")
    elif premium and float(premium) <= 50_000:
        print(f"\n  ℹ️  Premium ${premium:,.2f} is within UW Analyst limit — no escalation expected")
        print("  Creating high-value submission to force escalation...")
        _force_escalation(client)
    else:
        print(f"\n  ⚠️  Premium ${premium:,.2f} but no escalation? Checking authority...")
        print(f"     Authority: {authority}")

    # 4. Check escalations
    print("\n=== Step 4: Check escalations ===")
    r = client.get("/api/v1/escalations")
    print(f"  Status: {r.status_code}")
    esc_data = r.json()
    items = esc_data.get("items", [])
    total = esc_data.get("total", len(items))
    print(f"  Total escalations: {total}")
    for item in items[:3]:
        print(f"    - [{item.get('status')}] {item.get('action')} | amount=${item.get('amount')} | {item.get('reason', '')[:80]}")

    if total > 0:
        print("\n✅ Escalation system is working!")
    else:
        print("\n⚠️  No escalations found — may need a higher-premium scenario")

    print()


def _force_escalation(client: httpx.Client) -> None:
    """Create a high-risk submission that should produce a premium > $50K."""
    submission = {
        "applicant_name": f"HighRisk Escalation {uuid.uuid4().hex[:6]}",
        "applicant_email": "highrisk@example.com",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {
            "company_name": "Mega Financial Corp",
            "annual_revenue": 500_000_000,
            "employee_count": 25_000,
            "industry": "financial_services",
            "years_in_business": 5,
            "prior_claims": 10,
            "coverage_limit_requested": 50_000_000,
            "data_records": 100_000_000,
            "has_prior_breaches": True,
            "security_rating": "poor",
        },
    }
    r = client.post("/api/v1/submissions", json=submission)
    if r.status_code not in (200, 201):
        print(f"  Error creating high-risk sub: {r.text}")
        return
    sub_id = r.json()["id"]
    print(f"  High-risk submission: {sub_id}")

    r = client.post(f"/api/v1/submissions/{sub_id}/triage")
    print(f"  Triage: {r.status_code} — risk={r.json().get('risk_score')}")

    r = client.post(f"/api/v1/submissions/{sub_id}/quote")
    print(f"  Quote: {r.status_code}")
    q = r.json()
    if r.status_code == 202:
        print(f"  ✅ ESCALATION TRIGGERED! Premium: ${q.get('premium', '?')}")
    else:
        print(f"  Premium: ${q.get('premium', '?')} — authority: {q.get('authority', {})}")


if __name__ == "__main__":
    main()
