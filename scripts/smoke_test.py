"""Pre-deploy smoke test — runs locally before any Azure deploy.

Usage: python scripts/smoke_test.py [backend_url]
Default: tests against local server at http://localhost:8000
"""

import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
API = f"{BASE}/api/v1"
H = {"X-API-Key": "dev-key-change-me"}
PASS = 0
FAIL = 0


def check(name: str, fn) -> None:  # noqa: ANN001
    global PASS, FAIL  # noqa: PLW0603
    try:
        fn()
        PASS += 1
        print(f"  ✅ {name}")
    except Exception as e:
        FAIL += 1
        print(f"  ❌ {name}: {e}")


def test_health() -> None:
    r = httpx.get(f"{BASE}/health", timeout=10)
    assert r.status_code == 200, f"health returned {r.status_code}"


def test_submissions_list() -> None:
    r = httpx.get(f"{API}/submissions", params={"limit": 2}, headers=H, timeout=15)
    assert r.status_code == 200, f"submissions returned {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert "items" in data or isinstance(data, list), "no items in response"


def test_policies_list() -> None:
    r = httpx.get(f"{API}/policies", params={"limit": 2}, headers=H, timeout=15)
    assert r.status_code == 200, f"policies returned {r.status_code}: {r.text[:200]}"


def test_claims_list() -> None:
    r = httpx.get(f"{API}/claims", params={"limit": 2}, headers=H, timeout=15)
    assert r.status_code == 200, f"claims returned {r.status_code}: {r.text[:200]}"


def test_metrics_summary() -> None:
    r = httpx.get(f"{API}/metrics/summary", headers=H, timeout=15)
    assert r.status_code == 200, f"metrics returned {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data.get("submissions", {}).get("total", 0) > 0, "no submissions in metrics"


def test_metrics_executive() -> None:
    r = httpx.get(f"{API}/metrics/executive", headers=H, timeout=15)
    assert r.status_code == 200, f"executive returned {r.status_code}: {r.text[:200]}"


def test_actuarial_reserves() -> None:
    r = httpx.get(f"{API}/actuarial/reserves", headers=H, timeout=15)
    assert r.status_code == 200, f"actuarial returned {r.status_code}: {r.text[:200]}"


def test_finance_summary() -> None:
    r = httpx.get(f"{API}/finance/summary", headers=H, timeout=15)
    assert r.status_code == 200, f"finance returned {r.status_code}: {r.text[:200]}"


def test_compliance_decisions() -> None:
    r = httpx.get(f"{API}/compliance/decisions", headers=H, timeout=15)
    assert r.status_code == 200, f"compliance returned {r.status_code}: {r.text[:200]}"


def test_compliance_audit_trail() -> None:
    r = httpx.get(f"{API}/compliance/audit-trail", headers=H, timeout=15)
    assert r.status_code == 200, f"audit-trail returned {r.status_code}: {r.text[:200]}"


def test_reinsurance_treaties() -> None:
    r = httpx.get(f"{API}/reinsurance/treaties", headers=H, timeout=15)
    assert r.status_code == 200, f"treaties returned {r.status_code}: {r.text[:200]}"


def test_escalations() -> None:
    r = httpx.get(f"{API}/escalations", headers=H, timeout=15)
    assert r.status_code == 200, f"escalations returned {r.status_code}: {r.text[:200]}"


def test_products() -> None:
    r = httpx.get(f"{API}/products", headers=H, timeout=15)
    assert r.status_code == 200, f"products returned {r.status_code}: {r.text[:200]}"


def test_demo_workflow() -> None:
    r = httpx.post(f"{API}/demo/full-workflow", headers=H, timeout=30)
    assert r.status_code == 200, f"demo returned {r.status_code}: {r.text[:200]}"


def test_submission_lifecycle() -> None:
    """Create → triage → quote → bind — the core workflow."""
    # Create
    r = httpx.post(
        f"{API}/submissions",
        json={
            "applicant_name": "Smoke Test Corp",
            "line_of_business": "cyber",
            "effective_date": "2026-08-01",
            "expiration_date": "2027-08-01",
            "cyber_risk_data": {
                "annual_revenue": 5000000,
                "employee_count": 50,
                "industry": "Software",
                "sic_code": "7372",
                "security_maturity_score": 7,
                "prior_incidents": 0,
            },
        },
        headers=H,
        timeout=30,
    )
    assert r.status_code in (200, 201), f"create failed: {r.status_code}: {r.text[:200]}"
    sid = r.json().get("id") or r.json().get("submission_id")
    assert sid, "no submission id returned"

    # Triage
    r = httpx.post(f"{API}/submissions/{sid}/triage", headers=H, timeout=120)
    assert r.status_code == 200, f"triage failed: {r.status_code}: {r.text[:200]}"

    # Quote
    r = httpx.post(f"{API}/submissions/{sid}/quote", headers=H, timeout=120)
    assert r.status_code in (200, 202), f"quote failed: {r.status_code}: {r.text[:200]}"

    # Bind (skip if escalated)
    if r.status_code == 200:
        r = httpx.post(f"{API}/submissions/{sid}/bind", headers=H, timeout=120)
        assert r.status_code in (200, 202), f"bind failed: {r.status_code}: {r.text[:200]}"


def main() -> None:
    print(f"🔍 OpenInsure Smoke Test — {BASE}")
    print("=" * 50)

    print("\n📋 Core endpoints:")
    check("Health", test_health)
    check("Submissions list", test_submissions_list)
    check("Policies list", test_policies_list)
    check("Claims list", test_claims_list)
    check("Products list", test_products)

    print("\n📊 Metrics & dashboards:")
    check("Metrics summary", test_metrics_summary)
    check("Executive metrics", test_metrics_executive)
    check("Actuarial reserves", test_actuarial_reserves)
    check("Finance summary", test_finance_summary)

    print("\n🔒 Compliance:")
    check("Compliance decisions", test_compliance_decisions)
    check("Audit trail", test_compliance_audit_trail)

    print("\n📑 Carrier modules:")
    check("Reinsurance treaties", test_reinsurance_treaties)
    check("Escalations", test_escalations)

    print("\n🔄 Workflows:")
    check("Demo workflow", test_demo_workflow)
    check("Submission lifecycle (create→triage→quote→bind)", test_submission_lifecycle)

    print("\n" + "=" * 50)
    total = PASS + FAIL
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    if FAIL > 0:
        print("❌ SMOKE TEST FAILED — do NOT deploy")
        sys.exit(1)
    else:
        print("✅ ALL CLEAR — safe to deploy")


if __name__ == "__main__":
    main()
