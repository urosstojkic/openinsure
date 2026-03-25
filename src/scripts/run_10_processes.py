"""Run 10 realistic insurance processes covering diverse scenarios.

Each process represents a real-world insurance workflow:
- New business submissions with varied risk profiles
- Claims filed against bound policies
- Different outcomes: approved, declined, escalated

Results are documented in test-screenshots/PROCESS_LOG.md
"""

from datetime import datetime

import httpx

BE = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io/api/v1"
H = {"X-API-Key": "dev-key-change-me"}
LOG: list[dict] = []


def api(method: str, path: str, body: dict | None = None, timeout: int = 120) -> dict:
    if method == "POST":
        r = httpx.post(f"{BE}{path}", json=body, headers=H, timeout=timeout)
    else:
        r = httpx.get(f"{BE}{path}", headers=H, timeout=timeout)
    return {"status": r.status_code, "data": r.json() if r.status_code < 500 else {"error": r.text[:300]}}


def log_step(process: int, step: str, detail: str) -> None:
    entry = {
        "process": process,
        "step": step,
        "detail": detail,
        "time": datetime.now(tz=datetime.now().astimezone().tzinfo).strftime("%H:%M:%S"),
    }
    LOG.append(entry)
    print(f"  [{process:02d}] {step}: {detail}")


def run_new_business(num: int, company: str, payload: dict, file_claim: dict | None = None) -> None:
    print(f"\n{'=' * 60}")
    print(f"Process {num}: {company}")
    print(f"{'=' * 60}")

    # Create submission
    r = api("POST", "/submissions", payload)
    if r["status"] not in (200, 201):
        log_step(num, "CREATE", f"FAILED: {r['data']}")
        return
    sid = r["data"].get("id") or r["data"].get("submission_id")
    log_step(num, "CREATE", f"Submission {sid[:12]}... for {company}")

    # Triage
    r = api("POST", f"/submissions/{sid}/triage")
    if r["status"] == 200:
        t = r["data"]
        score = t.get("risk_score", "?")
        rec = t.get("recommendation", "?")
        flags = t.get("flags", [])
        flag_text = flags[0][:100] if flags else "none"
        log_step(num, "TRIAGE", f"Risk={score}, Rec={rec}, Agent: {flag_text}")
    else:
        log_step(num, "TRIAGE", f"FAILED ({r['status']}): {str(r['data'])[:150]}")
        return

    # Quote
    r = api("POST", f"/submissions/{sid}/quote")
    if r["status"] == 200:
        premium = r["data"].get("premium", 0)
        auth = r["data"].get("authority", {}).get("decision", "?")
        log_step(num, "QUOTE", f"Premium=${premium:,.2f}, Authority={auth}")
    elif r["status"] == 202:
        log_step(num, "QUOTE", f"ESCALATED: {r['data'].get('reason', '?')}")
        return
    else:
        log_step(num, "QUOTE", f"FAILED ({r['status']}): {str(r['data'])[:150]}")
        return

    # Bind
    r = api("POST", f"/submissions/{sid}/bind")
    if r["status"] == 200:
        pid = r["data"].get("policy_id", "?")
        log_step(num, "BIND", f"Policy {pid[:12]}... created")
    elif r["status"] == 202:
        log_step(num, "BIND", f"ESCALATED: {r['data'].get('reason', '?')}")
        return
    else:
        log_step(num, "BIND", f"FAILED ({r['status']}): {str(r['data'])[:150]}")
        return

    # Optional: file claim
    if file_claim and pid:
        claim_payload = {**file_claim, "policy_id": pid}
        r = api("POST", "/claims", claim_payload)
        if r["status"] in (200, 201):
            cid = r["data"].get("id") or r["data"].get("claim_id")
            cnum = r["data"].get("claim_number", "?")
            log_step(num, "CLAIM", f"Filed {cnum} ({cid[:12]}...): {file_claim['claim_type']}")

            # Set reserve
            reserve_amt = file_claim.get("_reserve", 50000)
            r2 = api(
                "POST",
                f"/claims/{cid}/reserve",
                {
                    "category": "indemnity",
                    "amount": reserve_amt,
                    "currency": "USD",
                    "notes": file_claim["description"][:100],
                },
            )
            if r2["status"] in (200, 201):
                log_step(num, "RESERVE", f"Set ${reserve_amt:,.0f} on {cnum}")
            else:
                log_step(num, "RESERVE", f"FAILED ({r2['status']})")
        else:
            log_step(num, "CLAIM", f"FAILED ({r['status']}): {str(r['data'])[:150]}")


def make_submission(
    name: str, revenue: int, employees: int, industry: str, sic: str, security: int, incidents: int, **extra: object
) -> dict:
    cyber = {
        "annual_revenue": revenue,
        "employee_count": employees,
        "industry": industry,
        "sic_code": sic,
        "security_maturity_score": security,
        "prior_incidents": incidents,
        "has_mfa": security >= 6,
        "has_endpoint_protection": security >= 5,
        "has_backup_strategy": security >= 4,
        **{k: v for k, v in extra.items() if not k.startswith("_")},
    }
    return {
        "applicant_name": name,
        "line_of_business": "cyber",
        "effective_date": "2026-07-01",
        "expiration_date": "2027-07-01",
        "cyber_risk_data": cyber,
    }


def write_log() -> None:
    with open("test-screenshots/PROCESS_LOG.md", "w") as f:
        f.write("# OpenInsure Process Execution Log\n\n")
        f.write(
            f"**Generated**: {datetime.now(tz=datetime.now().astimezone().tzinfo).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        )
        f.write("## Summary\n\n")
        f.write("| # | Company | Outcome | Key Detail |\n")
        f.write("|---|---------|---------|------------|\n")

        # Group by process
        processes: dict[int, list[dict]] = {}
        for entry in LOG:
            processes.setdefault(entry["process"], []).append(entry)

        for pnum, steps in sorted(processes.items()):
            company = steps[0]["detail"].split(" for ")[-1] if " for " in steps[0]["detail"] else "?"
            last_step = steps[-1]
            outcome = last_step["step"]
            detail = last_step["detail"][:60]
            f.write(f"| {pnum} | {company} | {outcome} | {detail} |\n")

        f.write("\n## Detailed Steps\n\n")
        for pnum, steps in sorted(processes.items()):
            company = steps[0]["detail"].split(" for ")[-1] if " for " in steps[0]["detail"] else f"Process {pnum}"
            f.write(f"### Process {pnum}: {company}\n\n")
            f.write("| Time | Step | Detail |\n")
            f.write("|------|------|--------|\n")
            for s in steps:
                f.write(f"| {s['time']} | **{s['step']}** | {s['detail']} |\n")
            f.write("\n")

        f.write("## How to Verify in Portal\n\n")
        f.write(
            "**Dashboard**: https://openinsure-dashboard.proudplant-9550e5a5.swedencentral.azurecontainerapps.io\n\n"
        )
        f.write("| Role | What to Check |\n")
        f.write("|------|---------------|\n")
        f.write(
            "| **Sarah Chen (Underwriter)** | Submissions page — filter by 'received' to see new submissions, 'bound' to see completed |\n"
        )
        f.write("| **David Park (Claims Adjuster)** | Claims page — new claims with reserves set |\n")
        f.write("| **Alexandra Reed (CEO)** | Executive Dashboard — updated GWP, loss ratio |\n")
        f.write("| **Anna Kowalski (Compliance)** | Agent Decisions — real Foundry agent decision records |\n")
        f.write("| **Emily Davis (Finance)** | Finance page — updated premium written |\n")
        f.write("| **Thomas Anderson (Broker)** | Broker Portal — new submissions and policies |\n")

    print("\n📄 Log saved to test-screenshots/PROCESS_LOG.md")


def main() -> None:
    print("=" * 60)
    print("Running 10 Realistic Insurance Processes")
    print("=" * 60)

    # 1. Standard tech company — clean profile, should be approved
    run_new_business(
        1,
        "Vertex Cloud Solutions",
        make_submission("Vertex Cloud Solutions", 12_000_000, 95, "Cloud Computing", "7372", 8, 0),
    )

    # 2. Financial services — high revenue, moderate risk
    run_new_business(
        2,
        "Sterling Capital Advisors",
        make_submission(
            "Sterling Capital Advisors", 35_000_000, 180, "Investment Advisory", "6282", 7, 1, pci_compliant=True
        ),
    )

    # 3. Healthcare — outside typical appetite, higher risk
    run_new_business(
        3,
        "Midwest Regional Medical Center",
        make_submission(
            "Midwest Regional Medical Center", 60_000_000, 1500, "Hospital", "8062", 5, 3, hipaa_compliant=True
        ),
        file_claim={
            "claim_type": "data_breach",
            "date_of_loss": "2026-08-10",
            "reported_by": "CISO Dr. Sarah Walsh",
            "description": "Unauthorized access to 50,000 patient records via compromised vendor portal. PHI exposure includes SSN, medical records, and insurance details.",
            "metadata": {"records_exposed": 50000, "severity": "critical", "regulatory_notification": True},
            "_reserve": 450_000,
        },
    )

    # 4. Small law firm — professional services, low revenue
    run_new_business(
        4,
        "Morrison & Associates LLP",
        make_submission("Morrison & Associates LLP", 3_000_000, 25, "Legal Services", "8111", 6, 0),
    )

    # 5. E-commerce retailer — PCI scope, ransomware history
    run_new_business(
        5,
        "ShopDirect Global",
        make_submission("ShopDirect Global", 45_000_000, 400, "E-Commerce", "5961", 5, 2, pci_compliant=True),
        file_claim={
            "claim_type": "ransomware",
            "date_of_loss": "2026-09-15",
            "reported_by": "VP IT Operations Mike Chen",
            "description": "LockBit ransomware encrypted order management system and customer database. 72-hour business interruption across all fulfillment centers.",
            "metadata": {"ransom_demanded": "75 BTC", "systems_affected": 12, "downtime_hours": 72},
            "_reserve": 650_000,
        },
    )

    # 6. Cybersecurity startup — excellent security, should be easy approve
    run_new_business(
        6,
        "CyberShield Technologies",
        make_submission("CyberShield Technologies", 8_000_000, 45, "Cybersecurity", "7371", 10, 0),
    )

    # 7. Manufacturing — IoT/OT exposure, moderate security
    run_new_business(
        7,
        "Precision Machining Corp",
        make_submission("Precision Machining Corp", 25_000_000, 350, "Industrial Manufacturing", "3599", 4, 1),
        file_claim={
            "claim_type": "business_interruption",
            "date_of_loss": "2026-10-01",
            "reported_by": "Plant Manager Robert Torres",
            "description": "Cyber attack on SCADA/OT systems halted production line for 5 days. Estimated lost revenue $2M. Industrial control systems required full rebuild.",
            "metadata": {"production_days_lost": 5, "estimated_revenue_loss": 2_000_000},
            "_reserve": 800_000,
        },
    )

    # 8. University — education sector, large attack surface
    run_new_business(
        8,
        "Pacific State University",
        make_submission("Pacific State University", 150_000_000, 5000, "Higher Education", "8221", 4, 2),
    )

    # 9. Fintech startup — high security but regulatory complexity
    run_new_business(
        9,
        "PayStream Digital",
        make_submission("PayStream Digital", 18_000_000, 120, "Payment Processing", "6153", 9, 0, pci_compliant=True),
        file_claim={
            "claim_type": "social_engineering",
            "date_of_loss": "2026-11-20",
            "reported_by": "CFO Jennifer Park",
            "description": "Business email compromise attack impersonating CEO resulted in $180,000 wire transfer to fraudulent account. Funds partially recovered ($45,000).",
            "metadata": {"amount_lost": 180_000, "amount_recovered": 45_000},
            "_reserve": 135_000,
        },
    )

    # 10. Large consulting firm — professional services, global ops
    run_new_business(
        10,
        "Deloraine Consulting Group",
        make_submission("Deloraine Consulting Group", 80_000_000, 2000, "Management Consulting", "7389", 6, 1),
    )

    write_log()

    print("\n" + "=" * 60)
    print("All 10 processes complete. Check PROCESS_LOG.md for details.")
    print("=" * 60)


if __name__ == "__main__":
    main()
