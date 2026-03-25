"""Create fresh test submissions at each workflow stage for manual testing."""

import httpx

BE = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io/api/v1"
H = {"X-API-Key": "dev-key-change-me"}

COMPANIES = [
    ("TEST-Triage: Acme Software Inc", 5000000, 50, "Software", "7372", 7, 0),
    ("TEST-Triage: Global Payments Ltd", 20000000, 200, "Fintech", "6159", 6, 1),
    ("TEST-Triage: NorthWest Logistics", 10000000, 100, "Logistics", "4215", 5, 0),
    ("TEST-Quote: DataVault Security", 8000000, 60, "IT Services", "7371", 8, 0),
    ("TEST-Quote: Pacific Trading Co", 15000000, 150, "Financial", "6022", 6, 2),
    ("TEST-Bind: Horizon Analytics", 12000000, 80, "Analytics", "7372", 7, 1),
]


def create_submission(
    name: str, revenue: int, employees: int, industry: str, sic: str, security: int, incidents: int
) -> str:
    r = httpx.post(
        f"{BE}/submissions",
        json={
            "applicant_name": name,
            "line_of_business": "cyber",
            "effective_date": "2026-07-01",
            "expiration_date": "2027-07-01",
            "cyber_risk_data": {
                "annual_revenue": revenue,
                "employee_count": employees,
                "industry": industry,
                "sic_code": sic,
                "security_maturity_score": security,
                "prior_incidents": incidents,
                "has_mfa": security >= 6,
                "has_endpoint_protection": security >= 5,
                "has_backup_strategy": security >= 4,
            },
        },
        headers=H,
        timeout=30,
    )
    data = r.json()
    return data.get("id") or data.get("submission_id")


def main() -> None:
    print("=" * 60)
    print("Creating test submissions at each workflow stage")
    print("=" * 60)

    # 3 submissions left at RECEIVED (ready to Triage)
    print("\n--- RECEIVED (ready for Triage button) ---")
    for name, rev, emp, ind, sic, sec, inc in COMPANIES[:3]:
        sid = create_submission(name, rev, emp, ind, sic, sec, inc)
        print(f"  {name}: {sid}")

    # 2 submissions advanced to UNDERWRITING (ready for Quote button)
    print("\n--- UNDERWRITING (ready for Quote button) ---")
    for name, rev, emp, ind, sic, sec, inc in COMPANIES[3:5]:
        sid = create_submission(name, rev, emp, ind, sic, sec, inc)
        r = httpx.post(f"{BE}/submissions/{sid}/triage", headers=H, timeout=120)
        t = r.json()
        print(f"  {name}: {sid}")
        print(f"    Triaged: risk={t.get('risk_score')}, rec={t.get('recommendation')}")

    # 1 submission advanced to QUOTED (ready for Bind button)
    print("\n--- QUOTED (ready for Bind button) ---")
    name, rev, emp, ind, sic, sec, inc = COMPANIES[5]
    sid = create_submission(name, rev, emp, ind, sic, sec, inc)
    r = httpx.post(f"{BE}/submissions/{sid}/triage", headers=H, timeout=120)
    r = httpx.post(f"{BE}/submissions/{sid}/quote", headers=H, timeout=120)
    q = r.json()
    premium = q.get("premium", "?")
    print(f"  {name}: {sid}")
    print(f"    Quoted: premium=${premium}")

    print("\n" + "=" * 60)
    print("DONE! Filter submissions by 'received' to see Triage buttons.")
    print("Filter by 'underwriting' for Quote buttons.")
    print("Filter by 'quoted' for Bind buttons.")
    print("Look for names starting with 'TEST-' to find them easily.")
    print("=" * 60)


if __name__ == "__main__":
    main()
