"""Run 3 end-to-end processes for manual testing in the portal."""

import httpx

BE = os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")/api/v1"
H = {"X-API-Key": "dev-key-change-me"}


def process_1():
    print("=" * 70)
    print("PROCESS 1: Mid-size tech company — full triage → quote → bind")
    print("=" * 70)

    r = httpx.post(
        f"{BE}/submissions",
        json={
            "applicant_name": "Quantum Analytics Corp",
            "line_of_business": "cyber",
            "effective_date": "2026-05-01",
            "expiration_date": "2027-05-01",
            "cyber_risk_data": {
                "annual_revenue": 15000000,
                "employee_count": 120,
                "industry": "Data Analytics",
                "sic_code": "7372",
                "security_maturity_score": 7,
                "prior_incidents": 1,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
            },
        },
        headers=H,
        timeout=30,
    )
    sub = r.json()
    sid = sub.get("id") or sub.get("submission_id")
    print(f"  Created submission: {sid}")

    r = httpx.post(f"{BE}/submissions/{sid}/triage", headers=H, timeout=120)
    t = r.json()
    score = t.get("risk_score", "?")
    rec = t.get("recommendation", "?")
    print(f"  Triage → risk_score={score}, recommendation={rec}")
    for f in t.get("flags", [])[:2]:
        print(f"    Agent: {str(f)[:140]}")

    r = httpx.post(f"{BE}/submissions/{sid}/quote", headers=H, timeout=120)
    q = r.json()
    premium = q.get("premium", 0)
    print(f"  Quote → premium=${premium:,.2f}, quote_id={str(q.get('quote_id', '?'))[:12]}")

    r = httpx.post(f"{BE}/submissions/{sid}/bind", headers=H, timeout=120)
    if r.status_code == 200:
        b = r.json()
        print(f"  Bind → policy_id={b.get('policy_id', '?')}")
    elif r.status_code == 202:
        print(f"  Bind → ESCALATED: {r.json().get('reason', '?')}")
    else:
        print(f"  Bind → {r.status_code}: {r.text[:150]}")

    return sid


def process_2():
    print()
    print("=" * 70)
    print("PROCESS 2: Hospital — high risk, ransomware claim filed")
    print("=" * 70)

    r = httpx.post(
        f"{BE}/submissions",
        json={
            "applicant_name": "CareFirst Regional Hospital",
            "line_of_business": "cyber",
            "effective_date": "2026-05-01",
            "expiration_date": "2027-05-01",
            "cyber_risk_data": {
                "annual_revenue": 50000000,
                "employee_count": 800,
                "industry": "Healthcare",
                "sic_code": "8062",
                "security_maturity_score": 5,
                "prior_incidents": 3,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": False,
                "hipaa_compliant": True,
            },
        },
        headers=H,
        timeout=30,
    )
    sub = r.json()
    sid = sub.get("id") or sub.get("submission_id")
    print(f"  Created submission: {sid}")

    r = httpx.post(f"{BE}/submissions/{sid}/triage", headers=H, timeout=120)
    t = r.json()
    print(f"  Triage → risk_score={t.get('risk_score', '?')}, rec={t.get('recommendation', '?')}")
    for f in t.get("flags", [])[:2]:
        print(f"    Agent: {str(f)[:140]}")

    r = httpx.post(f"{BE}/submissions/{sid}/quote", headers=H, timeout=120)
    q = r.json()
    print(f"  Quote → premium=${q.get('premium', 0):,.2f}")

    r = httpx.post(f"{BE}/submissions/{sid}/bind", headers=H, timeout=120)
    pid = None
    if r.status_code == 200:
        b = r.json()
        pid = b.get("policy_id")
        print(f"  Bind → policy_id={pid}")
    elif r.status_code == 202:
        print(f"  Bind → ESCALATED: {r.json().get('reason', '?')}")
        return sid, None, None
    else:
        print(f"  Bind → {r.status_code}: {r.text[:150]}")
        return sid, None, None

    # File ransomware claim
    print("  Filing ransomware claim...")
    r = httpx.post(
        f"{BE}/claims",
        json={
            "policy_id": pid,
            "claim_type": "ransomware",
            "date_of_loss": "2026-06-15",
            "reported_by": "CISO at CareFirst",
            "description": "Ransomware attack encrypted patient records across 3 facilities. Attackers demanding 50 BTC.",
            "metadata": {"severity": "critical", "facilities_affected": 3},
        },
        headers=H,
        timeout=30,
    )
    c = r.json()
    cid = c.get("id") or c.get("claim_id")
    cnum = c.get("claim_number", "?")
    print(f"  Claim filed: {cid} ({cnum})")

    # Set reserve
    r = httpx.post(
        f"{BE}/claims/{cid}/reserves",
        json={
            "category": "indemnity",
            "amount": 350000,
            "currency": "USD",
            "notes": "Initial reserve for ransomware - 3 facilities, patient data encrypted",
        },
        headers=H,
        timeout=30,
    )
    if r.status_code == 200:
        print("  Reserve set: $350,000")
    else:
        print(f"  Reserve: {r.status_code} - {r.text[:100]}")

    return sid, pid, cid


def process_3():
    print()
    print("=" * 70)
    print("PROCESS 3: Demo workflow — single API call, full lifecycle")
    print("=" * 70)

    r = httpx.post(f"{BE}/demo/full-workflow", headers=H, timeout=30)
    if r.status_code != 200:
        print(f"  Failed: {r.status_code} - {r.text[:200]}")
        return

    demo = r.json()
    print(f"  Outcome: {demo.get('status', demo.get('outcome', '?'))}")
    premium = demo.get("premium", demo.get("quoted_premium", "?"))
    print(f"  Premium: ${premium}")
    pol = demo.get("policy_id", demo.get("policy_number", "?"))
    print(f"  Policy: {pol}")

    steps = demo.get("steps", demo.get("trace", []))
    if isinstance(steps, list):
        for s in steps:
            if isinstance(s, dict):
                name = s.get("step", s.get("name", "?"))
                result = s.get("result", s.get("status", s.get("outcome", "?")))
                print(f"    Step: {name} → {str(result)[:80]}")
    elif isinstance(steps, dict):
        for name, detail in steps.items():
            print(f"    Step: {name} → {str(detail)[:80]}")


if __name__ == "__main__":
    sid1 = process_1()
    sid2, pid2, cid2 = process_2()
    process_3()

    print()
    print("=" * 70)
    print("YOUR TEST DATA — verify in the portal:")
    print("=" * 70)
    print(f"  Submission 1 (Quantum Analytics):    {sid1}")
    print(f"  Submission 2 (CareFirst Hospital):   {sid2}")
    if pid2:
        print(f"  Policy (CareFirst):                  {pid2}")
    if cid2:
        print(f"  Claim (Ransomware):                  {cid2}")
    print()
    print("  Dashboard: https://openinsure-dashboard.proudplant-9550e5a5.swedencentral.azurecontainerapps.io")
    print("  API Docs:  os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")/docs")
