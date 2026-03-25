"""Seed carrier-module data for OpenInsure deployed backend.

Populates reinsurance treaties / cessions / recoveries, actuarial reserves /
loss triangles / rate adequacy, and billing accounts with realistic 3-year
enterprise data that connects to the existing submissions / policies / claims.

Usage:
    python src/scripts/seed_carrier_modules.py [BASE_URL]

Example:
    python src/scripts/seed_carrier_modules.py os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")
"""

from __future__ import annotations

import sys
from typing import Any

import httpx

BASE_URL = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")"
)

client = httpx.Client(base_url=BASE_URL, timeout=30)

stats: dict[str, int] = {
    "treaties": 0,
    "cessions": 0,
    "recoveries": 0,
    "reserves": 0,
    "triangles": 0,
    "rate_adequacy": 0,
    "billing": 0,
    "errors": 0,
}


def post(endpoint: str, data: dict[str, Any]) -> dict[str, Any] | None:
    """POST to an API endpoint, return JSON on success or None on failure."""
    try:
        r = client.post(f"/api/v1/{endpoint}", json=data)
        if r.status_code in (200, 201):
            return r.json()
        print(f"  WARN {endpoint}: HTTP {r.status_code} — {r.text[:200]}")
        stats["errors"] += 1
        return None
    except Exception as e:
        print(f"  ERROR {endpoint}: {e}")
        stats["errors"] += 1
        return None


def get(endpoint: str) -> dict[str, Any] | list[Any] | None:
    """GET from an API endpoint."""
    try:
        r = client.get(f"/api/v1/{endpoint}")
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Fetch existing IDs from the deployed backend
# ---------------------------------------------------------------------------


def fetch_existing_ids() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Get existing policies, claims, and submissions from the backend."""
    print("  Fetching existing entities...")

    policies_data = get("policies")
    policies = []
    if isinstance(policies_data, dict):
        policies = policies_data.get("items", [])
    elif isinstance(policies_data, list):
        policies = policies_data

    claims_data = get("claims")
    claims = []
    if isinstance(claims_data, dict):
        claims = claims_data.get("items", [])
    elif isinstance(claims_data, list):
        claims = claims_data

    submissions_data = get("submissions")
    submissions = []
    if isinstance(submissions_data, dict):
        submissions = submissions_data.get("items", [])
    elif isinstance(submissions_data, list):
        submissions = submissions_data

    print(f"    Policies: {len(policies)}, Claims: {len(claims)}, Submissions: {len(submissions)}")
    return policies, claims, submissions


# ============================================================================
# 1. REINSURANCE — Treaties, Cessions, Recoveries
# ============================================================================

TREATIES = [
    {
        "treaty_type": "quota_share",
        "reinsurer_name": "Swiss Re",
        "effective_date": "2024-01-01",
        "expiration_date": "2027-01-01",
        "lines_of_business": ["cyber", "tech_eo"],
        "retention": 0.70,
        "limit": 5_000_000,
        "rate": 0.30,
        "capacity_total": 15_000_000,
        "reinstatements": 1,
        "description": "30% quota share on cyber and tech E&O portfolio. 3-year term with annual review.",
    },
    {
        "treaty_type": "excess_of_loss",
        "reinsurer_name": "Munich Re",
        "effective_date": "2024-01-01",
        "expiration_date": "2027-01-01",
        "lines_of_business": ["cyber"],
        "retention": 500_000,
        "limit": 4_500_000,
        "rate": 0.12,
        "capacity_total": 10_000_000,
        "reinstatements": 2,
        "description": "$4.5M xs $500K per-occurrence cyber excess-of-loss. Two reinstatements at 100%.",
    },
    {
        "treaty_type": "facultative",
        "reinsurer_name": "Lloyd's Syndicate 2525",
        "effective_date": "2025-01-01",
        "expiration_date": "2026-01-01",
        "lines_of_business": ["cyber"],
        "retention": 0,
        "limit": 3_000_000,
        "rate": 0.18,
        "capacity_total": 3_000_000,
        "reinstatements": 0,
        "description": "Facultative placement for large healthcare accounts exceeding treaty capacity.",
    },
    {
        "treaty_type": "surplus",
        "reinsurer_name": "Hannover Re",
        "effective_date": "2025-06-01",
        "expiration_date": "2026-06-01",
        "lines_of_business": ["cyber"],
        "retention": 1_000_000,
        "limit": 9_000_000,
        "rate": 0.08,
        "capacity_total": 20_000_000,
        "reinstatements": 1,
        "description": "Surplus share treaty for large-limit cyber accounts. 9 lines of $1M retention.",
    },
    {
        "treaty_type": "excess_of_loss",
        "reinsurer_name": "SCOR SE",
        "effective_date": "2024-07-01",
        "expiration_date": "2027-07-01",
        "lines_of_business": ["cyber", "tech_eo"],
        "retention": 250_000,
        "limit": 2_750_000,
        "rate": 0.15,
        "capacity_total": 8_000_000,
        "reinstatements": 2,
        "description": "Working layer XL for mid-market cyber portfolio. $2.75M xs $250K.",
    },
]


def seed_reinsurance(
    policies: list[dict[str, Any]],
    claims: list[dict[str, Any]],
) -> list[str]:
    """Create treaties, then cessions and recoveries linked to real entities."""
    print(f"\n{'─' * 50}")
    print("  Seeding Reinsurance Module")
    print(f"{'─' * 50}")

    # Check if treaties already exist
    existing = get("reinsurance/treaties")
    if isinstance(existing, dict) and len(existing.get("items", [])) >= 3:
        print("  SKIP: Treaties already seeded")
        return [t["id"] for t in existing["items"]]

    treaty_ids: list[str] = []
    for t in TREATIES:
        result = post("reinsurance/treaties", t)
        if result:
            tid = result.get("id", "")
            treaty_ids.append(tid)
            stats["treaties"] += 1
            tnum = result.get("treaty_number", "?")
            print(f"  + Treaty {tnum} ({t['treaty_type']}) — {t['reinsurer_name']}")
        else:
            treaty_ids.append("")

    # Cessions — link policies to treaties
    if policies and treaty_ids:
        print(f"\n  Creating cessions for {min(len(policies), 12)} policies...")
        # Quota share: cede 30% of all policies to Swiss Re treaty
        qs_treaty = treaty_ids[0] if treaty_ids[0] else None
        xl_treaty = treaty_ids[1] if len(treaty_ids) > 1 and treaty_ids[1] else None

        for i, pol in enumerate(policies[:12]):
            pol_id = pol.get("id", "")
            pol_num = pol.get("policy_number", f"POL-{i}")
            premium = float(pol.get("premium", pol.get("total_premium", 0)) or 0)
            if not pol_id or premium <= 0:
                continue

            # Quota share cession (30% of premium and limit)
            if qs_treaty:
                cession = post(
                    "reinsurance/cessions",
                    {
                        "treaty_id": qs_treaty,
                        "policy_id": pol_id,
                        "policy_number": pol_num,
                        "ceded_premium": round(premium * 0.30, 2),
                        "ceded_limit": round(premium * 40, 2),  # Approximate limit
                    },
                )
                if cession:
                    stats["cessions"] += 1

            # XL cession for larger accounts (premium > $30K)
            if xl_treaty and premium > 30_000:
                cession = post(
                    "reinsurance/cessions",
                    {
                        "treaty_id": xl_treaty,
                        "policy_id": pol_id,
                        "policy_number": pol_num,
                        "ceded_premium": round(premium * 0.12, 2),
                        "ceded_limit": min(4_500_000, round(premium * 60, 2)),
                    },
                )
                if cession:
                    stats["cessions"] += 1

        print(f"    Created {stats['cessions']} cessions")

    # Recoveries — link claims to treaties
    if claims and treaty_ids:
        print(f"\n  Creating recoveries for {min(len(claims), 6)} claims...")
        for i, claim in enumerate(claims[:6]):
            claim_id = claim.get("id", "")
            claim_num = claim.get("claim_number", f"CLM-{i}")
            reserved = float(claim.get("total_reserved", 0) or 0)
            if not claim_id:
                continue

            # Recovery on XL treaty if reserve exceeds retention
            target_treaty = treaty_ids[1] if len(treaty_ids) > 1 else treaty_ids[0]
            if target_treaty and reserved > 0:
                recovery_amt = round(max(reserved * 0.30, 10_000), 2)
                recovery_status = "collected" if i < 2 else ("submitted" if i < 4 else "pending")
                recovery = post(
                    "reinsurance/recoveries",
                    {
                        "treaty_id": target_treaty,
                        "claim_id": claim_id,
                        "claim_number": claim_num,
                        "recovery_amount": recovery_amt,
                        "status": recovery_status,
                    },
                )
                if recovery:
                    stats["recoveries"] += 1

        print(f"    Created {stats['recoveries']} recoveries")

    return treaty_ids


# ============================================================================
# 2. ACTUARIAL — Reserves, Triangles, Rate Adequacy
# ============================================================================


def seed_actuarial() -> None:
    """Populate actuarial reserves and loss triangle data."""
    print(f"\n{'─' * 50}")
    print("  Seeding Actuarial Module")
    print(f"{'─' * 50}")

    # Check if reserves already exist
    existing = get("actuarial/reserves")
    if isinstance(existing, list) and len(existing) >= 4:
        print("  SKIP: Reserves already seeded")
        return

    # Reserves — 3 years of cyber + professional liability
    reserves = [
        # Cyber reserves
        {
            "line_of_business": "cyber",
            "accident_year": 2023,
            "reserve_type": "case",
            "carried_amount": 4_500_000,
            "indicated_amount": 4_800_000,
            "selected_amount": 4_650_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "Michael Torres",
            "notes": "Q1 2026 review — slight deterioration in large-loss corridor.",
        },
        {
            "line_of_business": "cyber",
            "accident_year": 2023,
            "reserve_type": "ibnr",
            "carried_amount": 2_100_000,
            "indicated_amount": 2_350_000,
            "selected_amount": 2_200_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "Michael Torres",
            "notes": "Chain-ladder indication; BF cross-check within 5%.",
        },
        {
            "line_of_business": "cyber",
            "accident_year": 2024,
            "reserve_type": "case",
            "carried_amount": 3_200_000,
            "indicated_amount": 3_400_000,
            "selected_amount": 3_300_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "",
            "notes": "Pending CFO approval.",
        },
        {
            "line_of_business": "cyber",
            "accident_year": 2024,
            "reserve_type": "ibnr",
            "carried_amount": 1_800_000,
            "indicated_amount": 2_000_000,
            "selected_amount": 1_900_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "",
            "notes": "Immature year — BF method preferred over chain-ladder.",
        },
        {
            "line_of_business": "cyber",
            "accident_year": 2025,
            "reserve_type": "case",
            "carried_amount": 2_400_000,
            "indicated_amount": 2_800_000,
            "selected_amount": 2_600_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "",
            "notes": "Early development; frequency elevated but severity moderate.",
        },
        {
            "line_of_business": "cyber",
            "accident_year": 2025,
            "reserve_type": "ibnr",
            "carried_amount": 3_100_000,
            "indicated_amount": 3_600_000,
            "selected_amount": 3_350_000,
            "as_of_date": "2026-03-31",
            "analyst": "Sarah Chen",
            "approved_by": "",
            "notes": "Significant IBNR expected — only 12-month development.",
        },
        # Professional liability reserves
        {
            "line_of_business": "professional_liability",
            "accident_year": 2023,
            "reserve_type": "case",
            "carried_amount": 6_000_000,
            "indicated_amount": 6_200_000,
            "selected_amount": 6_100_000,
            "as_of_date": "2026-03-31",
            "analyst": "James Wright",
            "approved_by": "Michael Torres",
            "notes": "Two large claims driving case reserve increase.",
        },
        {
            "line_of_business": "professional_liability",
            "accident_year": 2023,
            "reserve_type": "ibnr",
            "carried_amount": 3_500_000,
            "indicated_amount": 3_800_000,
            "selected_amount": 3_600_000,
            "as_of_date": "2026-03-31",
            "analyst": "James Wright",
            "approved_by": "Michael Torres",
            "notes": "Long-tail development — monitoring closely.",
        },
        {
            "line_of_business": "professional_liability",
            "accident_year": 2024,
            "reserve_type": "case",
            "carried_amount": 4_200_000,
            "indicated_amount": 4_500_000,
            "selected_amount": 4_350_000,
            "as_of_date": "2026-03-31",
            "analyst": "James Wright",
            "approved_by": "",
            "notes": "Within expectations — no outlier claims.",
        },
        {
            "line_of_business": "professional_liability",
            "accident_year": 2024,
            "reserve_type": "ibnr",
            "carried_amount": 4_800_000,
            "indicated_amount": 5_200_000,
            "selected_amount": 5_000_000,
            "as_of_date": "2026-03-31",
            "analyst": "James Wright",
            "approved_by": "",
            "notes": "Elevated IBNR reflecting professional liability tail.",
        },
    ]

    for r in reserves:
        result = post("actuarial/reserves", r)
        if result:
            stats["reserves"] += 1
    print(f"    Created {stats['reserves']} reserve records")

    # Triangle data is seeded via the in-memory seed_data on startup;
    # the triangle/IBNR/rate-adequacy endpoints read from repos
    # populated by seed_sample_data(). No additional API seeding needed
    # since the actuarial API was refactored to use repositories.
    print("    Triangle & rate adequacy data loaded via application startup seed")


# ============================================================================
# 3. BILLING — Accounts linked to policies
# ============================================================================


def seed_billing(policies: list[dict[str, Any]]) -> None:
    """Create billing accounts for each policy."""
    print(f"\n{'─' * 50}")
    print("  Seeding Billing Module")
    print(f"{'─' * 50}")

    # Check if billing accounts exist
    get("billing/accounts/00000000-0000-0000-0000-000000000000")
    # We can't easily check all accounts, so just try to create

    installment_plans = [1, 2, 4, 4, 12, 1, 4, 2, 1, 4, 4, 12]

    for i, pol in enumerate(policies[:12]):
        pol_id = pol.get("id", "")
        pol_name = pol.get("policyholder_name", pol.get("insured_name", f"Policyholder-{i}"))
        premium = float(pol.get("premium", pol.get("total_premium", 0)) or 0)
        if not pol_id or premium <= 0:
            continue

        installments = installment_plans[i % len(installment_plans)]
        result = post(
            "billing/accounts",
            {
                "policy_id": pol_id,
                "policyholder_name": pol_name,
                "total_premium": premium,
                "installments": installments,
                "currency": "USD",
                "billing_email": f"billing-{i}@example.com",
            },
        )
        if result:
            account_id = result.get("id", "")
            stats["billing"] += 1

            # Record partial payments for some accounts
            if i < 6 and account_id:
                paid_installments = min(i + 1, installments)
                per_installment = premium / installments
                for j in range(paid_installments):
                    methods = ["ach", "wire", "check", "credit_card"]
                    post(
                        f"billing/accounts/{account_id}/payment",
                        {
                            "amount": round(per_installment, 2),
                            "method": methods[j % len(methods)],
                            "reference": f"PMT-{i:03d}-{j + 1:02d}",
                            "notes": f"Installment {j + 1} of {installments}",
                        },
                    )

            print(f"  + {pol_name[:35]:<35} ${premium:>10,.0f}  ({installments} installments)")

    print(f"    Created {stats['billing']} billing accounts")


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    print("=" * 60)
    print("  OpenInsure Carrier Module Seed")
    print(f"  Target: {BASE_URL}")
    print("=" * 60)

    # Health check
    try:
        r = client.get("/health")
        print(f"\n  Health: {r.status_code}")
    except Exception as e:
        print(f"\n  WARN: Health check failed ({e}), continuing...")

    # Fetch existing data to link against
    policies, claims, _submissions = fetch_existing_ids()

    if not policies:
        print("\n  WARNING: No policies found. Run seed_sql_data.py first.")
        print("  Carrier module seeding requires existing policies and claims.")

    # Seed each module
    seed_reinsurance(policies, claims)
    seed_actuarial()
    seed_billing(policies)

    # Summary
    print(f"\n{'=' * 60}")
    print("  CARRIER MODULE SEED COMPLETE")
    print(f"{'=' * 60}")
    for k, v in stats.items():
        if k != "errors":
            print(f"    {k:>15}: {v}")
    print(f"    {'errors':>15}: {stats['errors']}")

    # Verify
    print("\n  Verifying via API...")
    checks = [
        ("reinsurance/treaties", "treaties"),
        ("reinsurance/cessions", "cessions"),
        ("reinsurance/recoveries", "recoveries"),
        ("actuarial/reserves", "reserves"),
    ]
    for endpoint, label in checks:
        data = get(endpoint)
        if isinstance(data, dict):
            total = data.get("total", len(data.get("items", [])))
        elif isinstance(data, list):
            total = len(data)
        else:
            total = "?"
        print(f"    {label:>15}: {total}")
    print()


if __name__ == "__main__":
    main()
