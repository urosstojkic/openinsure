"""Run 5 diverse scenarios through Foundry agents to showcase different assessments."""

import httpx

BE = os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")/api/v1"
H = {"X-API-Key": "dev-key-change-me"}

SCENARIOS = [
    {
        "name": "High-risk: Large fintech with breach history",
        "payload": {
            "applicant_name": "MegaPay Financial Services",
            "line_of_business": "cyber",
            "effective_date": "2026-04-01",
            "expiration_date": "2027-04-01",
            "cyber_risk_data": {
                "annual_revenue": 45000000,
                "employee_count": 400,
                "industry": "Fintech",
                "sic_code": "6159",
                "security_maturity_score": 4,
                "prior_incidents": 5,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": False,
                "pci_compliant": True,
            },
        },
    },
    {
        "name": "Low-risk: Cybersecurity firm, pristine record",
        "payload": {
            "applicant_name": "IronShield Cybersecurity",
            "line_of_business": "cyber",
            "effective_date": "2026-04-01",
            "expiration_date": "2027-04-01",
            "cyber_risk_data": {
                "annual_revenue": 8000000,
                "employee_count": 50,
                "industry": "Cybersecurity",
                "sic_code": "7371",
                "security_maturity_score": 10,
                "prior_incidents": 0,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
            },
        },
    },
    {
        "name": "Edge case: Tiny startup, minimal security",
        "payload": {
            "applicant_name": "TinyApp Studios",
            "line_of_business": "cyber",
            "effective_date": "2026-04-01",
            "expiration_date": "2027-04-01",
            "cyber_risk_data": {
                "annual_revenue": 200000,
                "employee_count": 5,
                "industry": "Software",
                "sic_code": "7372",
                "security_maturity_score": 2,
                "prior_incidents": 0,
                "has_mfa": False,
                "has_endpoint_protection": False,
                "has_backup_strategy": False,
            },
        },
    },
    {
        "name": "Healthcare: HIPAA-sensitive, moderate risk",
        "payload": {
            "applicant_name": "NorthStar Medical Group",
            "line_of_business": "cyber",
            "effective_date": "2026-04-01",
            "expiration_date": "2027-04-01",
            "cyber_risk_data": {
                "annual_revenue": 25000000,
                "employee_count": 200,
                "industry": "Healthcare",
                "sic_code": "8011",
                "security_maturity_score": 6,
                "prior_incidents": 2,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
                "hipaa_compliant": True,
            },
        },
    },
    {
        "name": "Full workflow: Retail chain (orchestrator+all agents)",
        "payload": {
            "applicant_name": "ShopMart International",
            "line_of_business": "cyber",
            "effective_date": "2026-04-01",
            "expiration_date": "2027-04-01",
            "cyber_risk_data": {
                "annual_revenue": 80000000,
                "employee_count": 1200,
                "industry": "Retail",
                "sic_code": "5411",
                "security_maturity_score": 5,
                "prior_incidents": 3,
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
                "pci_compliant": True,
            },
        },
    },
]


def run() -> None:
    print("=" * 70)
    print("Running 5 diverse submissions through Foundry agents")
    print("=" * 70)

    for i, s in enumerate(SCENARIOS):
        print(f"\n--- Scenario {i + 1}: {s['name']} ---")

        # Create
        r = httpx.post(f"{BE}/submissions", json=s["payload"], headers=H, timeout=30)
        if r.status_code not in (200, 201):
            print(f"  CREATE FAILED: {r.status_code} - {r.text[:150]}")
            continue
        data = r.json()
        sid = data.get("id") or data.get("submission_id")
        print(f"  Created: {sid}")

        if i == 4:
            # Full workflow for last scenario
            print("  Running full multi-agent workflow...")
            r = httpx.post(f"{BE}/submissions/{sid}/process", headers=H, timeout=180)
            if r.status_code == 200:
                wf = r.json()
                print(f"  WORKFLOW outcome: {wf.get('outcome', wf.get('status', '?'))}")
                for step in wf.get("steps", []):
                    name = step.get("name", "?")
                    status = step.get("status", "?")
                    agent = step.get("agent", "?")
                    print(f"    {name}: {status} (agent: {agent})")
            else:
                print(f"  WORKFLOW: {r.status_code} - {r.text[:200]}")
        else:
            # Step by step: triage -> quote -> bind
            r = httpx.post(f"{BE}/submissions/{sid}/triage", headers=H, timeout=120)
            if r.status_code == 200:
                t = r.json()
                print(f"  TRIAGE: risk_score={t.get('risk_score')}, rec={t.get('recommendation')}")
                flags = t.get("flags", [])
                if flags:
                    for f in flags[:2]:
                        print(f"    Flag: {str(f)[:120]}")
            else:
                print(f"  TRIAGE: {r.status_code} - {r.text[:150]}")
                continue

            r = httpx.post(f"{BE}/submissions/{sid}/quote", headers=H, timeout=120)
            if r.status_code == 200:
                q = r.json()
                auth = q.get("authority", {})
                print(f"  QUOTE: premium=${q.get('premium', '?'):,} authority={auth.get('decision', '?')}")
            elif r.status_code == 202:
                esc = r.json()
                print(f"  QUOTE ESCALATED: {esc.get('reason', '?')} -> needs {esc.get('required_role', '?')}")
                continue
            else:
                print(f"  QUOTE: {r.status_code} - {r.text[:150]}")
                continue

            r = httpx.post(f"{BE}/submissions/{sid}/bind", headers=H, timeout=120)
            if r.status_code == 200:
                b = r.json()
                print(f"  BOUND: policy_id={b.get('policy_id', '?')[:24]}...")
            elif r.status_code == 202:
                print(f"  BIND ESCALATED: {r.json().get('reason', '?')}")
            else:
                print(f"  BIND: {r.status_code} - {r.text[:150]}")

    print("\n" + "=" * 70)
    print("Done! Check Foundry traces for detailed agent reasoning.")
    print("=" * 70)


if __name__ == "__main__":
    run()
