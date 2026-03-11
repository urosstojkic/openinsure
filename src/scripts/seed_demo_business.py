"""Seed OpenInsure with 12 months of realistic insurance business data.

Creates interconnected submissions → policies → claims → reserves/payments
representing a cyber insurance MGA's operations from Apr 2025 to Mar 2026.

Business profile:
    - Company: Cyber insurance MGA with ~$12M GWP
    - Product: Cyber Liability SMB
    - Growth: ~15% YoY, starting slower and ramping up

Usage:
    python src/scripts/seed_demo_business.py [--url URL] [--clean]

    --url    Backend URL (default: deployed Azure instance)
    --clean  Clear existing data first (not implemented — manual SQL truncate)
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import date, timedelta

import httpx

# ---------------------------------------------------------------------------
# Deterministic randomness so reruns produce the same data
# ---------------------------------------------------------------------------
random.seed(42)

DEFAULT_URL = (
    "https://openinsure-backend.braveriver-f92a9f28.swedencentral.azurecontainerapps.io"
)

# ---------------------------------------------------------------------------
# Company names by industry (120+ unique names)
# ---------------------------------------------------------------------------
TECH_COMPANIES = [
    "NovaTech Solutions",
    "Cascade Software Inc",
    "BluePeak Analytics",
    "VertexAI Labs",
    "Prism Digital Corp",
    "Helios Cloud Systems",
    "Zenith DevOps",
    "Orbital Code Works",
    "Luminary SaaS Inc",
    "ByteBridge Technologies",
    "Synapse Data Systems",
    "Nimbus Platform Group",
    "TerraCode Labs",
    "QuantumBit Software",
    "ClearStack Solutions",
    "VelocityDev Inc",
    "ArcLight Computing",
    "Photon Micro Systems",
    "InfiniLoop Tech",
    "NebulaWorks Software",
]

HEALTHCARE_COMPANIES = [
    "Meridian Healthcare Group",
    "Redwood Biotech",
    "Pinnacle Health Systems",
    "CrestView Medical Center",
    "Horizon Diagnostics",
    "Beacon Therapeutics",
    "Sapphire Health Partners",
    "Alder Medical Group",
    "Summit Care Network",
    "TrueNorth Clinical Labs",
    "VitalSign Health Tech",
    "CedarPoint Genomics",
    "OakBridge Health",
    "Pureform Pharma",
    "Encompass Telehealth",
]

FINANCE_COMPANIES = [
    "Quantum Financial Services",
    "Alpine Wealth Management",
    "Ironclad Capital Group",
    "Vanguard Risk Partners",
    "Sterling Advisors LLC",
    "Apex Lending Corp",
    "Bridgeway Financial",
    "Fortis Investment Group",
    "Pinnacle Credit Union",
    "Meridian Savings Bank",
    "Cobalt FinTech",
    "Clearwater Capital",
    "Granite Trust Co",
    "Keystone Financial",
    "Patriot Payments Inc",
]

RETAIL_COMPANIES = [
    "Coastal Properties Management",
    "Harborview Retail Group",
    "Summit Outdoors Co",
    "Urban Market Collective",
    "GreenLeaf Organics",
    "Brightside Home Goods",
    "Evergreen Retail Chain",
    "Pacific Coast Stores",
    "Mapleton Supply Co",
    "Ridgecrest Boutique",
    "TrueBlue Apparel",
    "FreshCart Grocery",
    "SilverLine Retail",
    "Crimson Marketplace",
    "WestEnd Shops Inc",
]

MANUFACTURING_COMPANIES = [
    "Atlas Manufacturing Inc",
    "Precision Dynamics Corp",
    "Ironworks Industrial",
    "SteelBridge Fabrication",
    "NorthStar Components",
    "Titan Machining Group",
    "Cornerstone Materials",
    "Ridgeline Plastics",
    "Alloy Systems Inc",
    "Forgepoint Industries",
    "ClearEdge Composites",
    "Benchmark Mfg Co",
    "ProLine Assembly",
    "Vertex Metal Works",
    "HarborForge Inc",
]

PROFESSIONAL_SERVICES = [
    "Pinnacle Legal Partners LLP",
    "Whitfield & Associates",
    "Clearmont Consulting",
    "Summit Strategy Group",
    "Blackstone CPAs",
    "Ironbridge Advisory",
    "Northwind Architects",
    "Oakmont Engineering",
    "Sterling Compliance Group",
    "Ridgeview Law Offices",
    "Trident HR Solutions",
    "Beacon Accounting",
    "Crestline Partners",
    "Keystone PR Agency",
    "Nexus Talent Group",
]

EDUCATION_COMPANIES = [
    "Horizons Academy",
    "BrightPath Learning",
    "Keystone University",
    "Summit Charter Schools",
    "Pinnacle EdTech",
]

ALL_COMPANIES = {
    "Technology": TECH_COMPANIES,
    "Healthcare": HEALTHCARE_COMPANIES,
    "Financial Services": FINANCE_COMPANIES,
    "Retail": RETAIL_COMPANIES,
    "Manufacturing": MANUFACTURING_COMPANIES,
    "Professional Services": PROFESSIONAL_SERVICES,
    "Education": EDUCATION_COMPANIES,
}

# Flatten for picking
_ALL_COMPANY_LIST: list[tuple[str, str]] = []
for industry, companies in ALL_COMPANIES.items():
    for name in companies:
        _ALL_COMPANY_LIST.append((name, industry))
random.shuffle(_ALL_COMPANY_LIST)

# ---------------------------------------------------------------------------
# Coverage templates for cyber SMB policies
# ---------------------------------------------------------------------------
COVERAGE_TEMPLATES = [
    {
        "coverage_code": "BREACH-RESP",
        "coverage_name": "Breach Response",
        "limit_range": (250_000, 5_000_000),
        "deductible_range": (5_000, 50_000),
    },
    {
        "coverage_code": "THIRD-PARTY",
        "coverage_name": "Third-Party Liability",
        "limit_range": (500_000, 5_000_000),
        "deductible_range": (10_000, 50_000),
    },
    {
        "coverage_code": "REG-DEFENSE",
        "coverage_name": "Regulatory Defense",
        "limit_range": (250_000, 3_000_000),
        "deductible_range": (10_000, 25_000),
    },
    {
        "coverage_code": "BUS-INTRPT",
        "coverage_name": "Business Interruption",
        "limit_range": (250_000, 2_000_000),
        "deductible_range": (10_000, 50_000),
    },
    {
        "coverage_code": "RANSOMWARE",
        "coverage_name": "Ransomware / Extortion",
        "limit_range": (100_000, 2_000_000),
        "deductible_range": (5_000, 25_000),
    },
    {
        "coverage_code": "CYBER-CRIME",
        "coverage_name": "Cyber Crime / Fraud",
        "limit_range": (100_000, 1_000_000),
        "deductible_range": (5_000, 15_000),
    },
]

# ---------------------------------------------------------------------------
# Claim description templates by cause of loss
# ---------------------------------------------------------------------------
CLAIM_DESCRIPTIONS = {
    "ransomware": [
        "Ransomware attack encrypted production databases and file servers. {ransom} ransom demanded via cryptocurrency. Forensics team engaged, breach counsel notified.",
        "LockBit variant deployed via compromised RDP credentials. All on-premise systems encrypted. Backups partially intact — recovery estimated at {days} days.",
        "Ransomware spread through phishing email targeting accounts payable. Encrypted 3 file servers and ERP system. Business operations severely impacted.",
        "BlackCat ransomware deployed after initial access via unpatched VPN appliance. Data exfiltration confirmed before encryption. Double extortion scenario.",
    ],
    "data_breach": [
        "Customer PII data breach via unpatched REST API vulnerability. Approximately {records} records exposed including names, emails, and payment details.",
        "Employee credentials compromised via credential stuffing attack. Attacker accessed internal HR system containing SSNs and salary data for {records} employees.",
        "Third-party vendor breach exposed client data shared via unsecured SFTP. {records} records affected across multiple clients. Notification obligations triggered.",
    ],
    "social_engineering": [
        "Business email compromise targeting CFO. Wire transfer of ${amount} sent to fraudulent account. Bank notified within {hours} hours, partial recovery in progress.",
        "Sophisticated spear-phishing campaign impersonating CEO. Accounts payable processed {count} fraudulent invoices totaling ${amount} before detection.",
        "Vendor impersonation scheme redirected legitimate payments. Attacker modified bank details in email thread. ${amount} diverted over {weeks} weeks.",
    ],
    "denial_of_service": [
        "Sustained DDoS attack caused {hours}-hour service outage for client-facing platform. Estimated ${amount} in business interruption losses and SLA penalties.",
        "Volumetric DDoS attack (peak {gbps} Gbps) overwhelmed ISP-level mitigation. E-commerce platform offline for {hours} hours during peak sales period.",
    ],
    "unauthorized_access": [
        "Former employee accessed analytics platform {weeks} weeks after termination using unrevoked credentials. Downloaded proprietary datasets and client reports.",
        "Unauthorized access detected via anomalous login from foreign IP. Attacker used stolen admin credentials to access cloud infrastructure for {days} days before detection.",
    ],
    "system_failure": [
        "Critical system failure during cloud migration caused {hours}-hour outage. Data integrity issues detected in migrated databases affecting {records} customer records.",
    ],
}

REPORTED_BY_NAMES = [
    "Dr. Sarah Chen, CISO",
    "James Morrison, CFO",
    "Mike Torres, IT Director",
    "Lisa Park, VP Engineering",
    "Tom Bradley, HR Director",
    "Rachel Kim, Cloud Architect",
    "David Chen, CTO",
    "Maria Santos, Controller",
    "Robert Walsh, COO",
    "Jennifer Liu, VP Operations",
    "Mark Thompson, Security Lead",
    "Amy Nguyen, Privacy Officer",
    "Chris Davies, Incident Commander",
    "Nicole Jordan, Risk Manager",
    "Steve Martinez, Compliance Director",
]

# ---------------------------------------------------------------------------
# Month distribution: 12 months Apr 2025 — Mar 2026
# Growth pattern: starts slower, ramps up (~15% YoY)
# ---------------------------------------------------------------------------
MONTHS = [
    date(2025, 4, 1),
    date(2025, 5, 1),
    date(2025, 6, 1),
    date(2025, 7, 1),
    date(2025, 8, 1),
    date(2025, 9, 1),
    date(2025, 10, 1),
    date(2025, 11, 1),
    date(2025, 12, 1),
    date(2026, 1, 1),
    date(2026, 2, 1),
    date(2026, 3, 1),
]

# Submissions per month — ramps up (total = 120)
SUBS_PER_MONTH = [7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13]

# ---------------------------------------------------------------------------
# Status distribution for 120 submissions
# ---------------------------------------------------------------------------
# 30% bound (36), 25% quoted (30), 15% underwriting (18),
# 10% triaging (12), 5% received (6), 15% declined (18)
STATUS_POOL: list[str] = (
    ["bound"] * 36
    + ["quoted"] * 30
    + ["underwriting"] * 18
    + ["triaging"] * 12
    + ["received"] * 6
    + ["declined"] * 18
)
random.shuffle(STATUS_POOL)

# Channel distribution: 40% broker, 30% email, 20% portal, 10% API
CHANNEL_POOL: list[str] = (
    ["broker"] * 48 + ["email"] * 36 + ["portal"] * 24 + ["api"] * 12
)
random.shuffle(CHANNEL_POOL)

# Claim cause distribution
CLAIM_CAUSES = (
    ["ransomware"] * 4
    + ["data_breach"] * 3
    + ["social_engineering"] * 3
    + ["denial_of_service"] * 2
    + ["unauthorized_access"] * 2
    + ["system_failure"] * 1
)
random.shuffle(CLAIM_CAUSES)

# Claim severity distribution
CLAIM_SEVERITIES = (
    ["catastrophe"] * 2 + ["complex"] * 4 + ["moderate"] * 5 + ["simple"] * 4
)
random.shuffle(CLAIM_SEVERITIES)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rand_date_in_month(month_start: date) -> date:
    """Return a random date within the given month."""
    if month_start.month == 12:
        next_month = date(month_start.year + 1, 1, 1)
    else:
        next_month = date(month_start.year, month_start.month + 1, 1)
    days_in_month = (next_month - month_start).days
    return month_start + timedelta(days=random.randint(0, days_in_month - 1))


def _rand_revenue(industry: str) -> int:
    """Generate realistic annual revenue by industry."""
    ranges = {
        "Technology": (2_000_000, 150_000_000),
        "Healthcare": (5_000_000, 200_000_000),
        "Financial Services": (10_000_000, 500_000_000),
        "Retail": (1_000_000, 80_000_000),
        "Manufacturing": (3_000_000, 100_000_000),
        "Professional Services": (500_000, 50_000_000),
        "Education": (2_000_000, 60_000_000),
    }
    lo, hi = ranges.get(industry, (1_000_000, 50_000_000))
    return random.randint(lo, hi)


def _rand_employees(revenue: int) -> int:
    """Approximate employee count from revenue."""
    per_emp = random.randint(50_000, 200_000)
    return max(10, revenue // per_emp)


def _email_domain(company: str) -> str:
    """Generate a plausible email domain from company name."""
    slug = (
        company.lower()
        .replace(" ", "")
        .replace(",", "")
        .replace(".", "")
        .replace("&", "")
    )
    slug = slug[:15]
    return f"{slug}.com"


def _rand_premium() -> float:
    """Random SMB cyber premium $8K-$95K, weighted toward lower end."""
    base = random.triangular(8_000, 95_000, 22_000)
    return round(base / 500) * 500  # round to nearest $500


def _build_coverages(premium: float) -> list[dict]:
    """Build realistic coverage breakdown summing to total premium."""
    n = random.choice([2, 2, 3, 3, 3, 4])
    chosen = random.sample(COVERAGE_TEMPLATES, n)
    remaining = premium
    coverages = []
    for i, tpl in enumerate(chosen):
        if i == len(chosen) - 1:
            cov_premium = remaining
        else:
            cov_premium = round(remaining * random.uniform(0.2, 0.5) / 500) * 500
            cov_premium = max(500, cov_premium)
            remaining -= cov_premium

        lo_lim, hi_lim = tpl["limit_range"]
        lo_ded, hi_ded = tpl["deductible_range"]
        limit = round(random.randint(lo_lim, hi_lim) / 50_000) * 50_000
        deductible = round(random.randint(lo_ded, hi_ded) / 5_000) * 5_000

        coverages.append(
            {
                "coverage_code": tpl["coverage_code"],
                "coverage_name": tpl["coverage_name"],
                "limit": limit,
                "deductible": deductible,
                "premium": max(500, round(cov_premium)),
            }
        )
    return coverages


def _fill_claim_description(cause: str) -> str:
    """Pick and fill a description template for the given cause."""
    templates = CLAIM_DESCRIPTIONS.get(cause, CLAIM_DESCRIPTIONS["system_failure"])
    template = random.choice(templates)
    return template.format(
        ransom=f"${random.choice([25, 50, 75, 100, 150, 200, 500])}K",
        days=random.randint(3, 21),
        records=f"{random.randint(1, 50) * 1000:,}",
        amount=f"{random.randint(15, 500) * 1000:,}",
        hours=random.randint(6, 72),
        count=random.randint(2, 8),
        weeks=random.randint(2, 6),
        gbps=random.choice([15, 40, 80, 120, 200]),
    )


# ---------------------------------------------------------------------------
# HTTP client wrapper
# ---------------------------------------------------------------------------


class APIClient:
    """Thin wrapper around httpx for seeding API calls."""

    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=30)
        self.stats = {
            "submissions": 0,
            "policies": 0,
            "claims": 0,
            "reserves": 0,
            "payments": 0,
            "errors": 0,
        }

    def post(self, endpoint: str, data: dict) -> dict | None:
        """POST to an API endpoint; return JSON on success or None on failure."""
        try:
            r = self.client.post(f"/api/v1/{endpoint}", json=data)
            if r.status_code in (200, 201):
                return r.json()
            print(f"  WARN {endpoint}: HTTP {r.status_code} — {r.text[:200]}")
            self.stats["errors"] += 1
            return None
        except Exception as e:
            print(f"  ERROR {endpoint}: {e}")
            self.stats["errors"] += 1
            return None

    def get(self, endpoint: str) -> dict | None:
        """GET an API endpoint; return JSON on success or None."""
        try:
            r = self.client.get(f"/api/v1/{endpoint}")
            if r.status_code in (200,):
                return r.json()
            return None
        except Exception:
            return None

    def health_check(self) -> bool:
        """Verify the backend is reachable."""
        try:
            r = self.client.get("/health")
            return r.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------


def generate_submissions() -> list[dict]:
    """Generate 120 submission payloads spread across 12 months."""
    submissions = []
    company_idx = 0

    for month_idx, month_start in enumerate(MONTHS):
        count = SUBS_PER_MONTH[month_idx]
        for _ in range(count):
            if company_idx >= len(_ALL_COMPANY_LIST):
                company_idx = 0  # shouldn't happen with 120 companies
            company_name, industry = _ALL_COMPANY_LIST[company_idx]
            company_idx += 1

            status = STATUS_POOL[len(submissions) % len(STATUS_POOL)]
            channel = CHANNEL_POOL[len(submissions) % len(CHANNEL_POOL)]

            eff_date = _rand_date_in_month(month_start)
            revenue = _rand_revenue(industry)
            emp_count = _rand_employees(revenue)

            email = f"risk@{_email_domain(company_name)}"

            # Quoted premium for submissions that reached quoting stage
            quoted_premium = None
            if status in ("quoted", "bound"):
                quoted_premium = _rand_premium()

            submissions.append(
                {
                    "payload": {
                        "applicant_name": company_name,
                        "applicant_email": email,
                        "channel": channel,
                        "line_of_business": "cyber",
                        "risk_data": {
                            "annual_revenue": revenue,
                            "employee_count": emp_count,
                            "industry": industry,
                            "requested_effective_date": eff_date.isoformat(),
                        },
                        "metadata": {
                            "source": "seed_demo_business",
                            "month": month_start.isoformat(),
                        },
                    },
                    "target_status": status,
                    "effective_date": eff_date,
                    "company_name": company_name,
                    "industry": industry,
                    "quoted_premium": quoted_premium,
                }
            )
    return submissions


def generate_policies(
    bound_submissions: list[dict],
) -> list[dict]:
    """Generate policy payloads from bound submissions (36 expected)."""
    policies = []
    for i, sub in enumerate(bound_submissions):
        eff = sub["effective_date"]
        exp = date(eff.year + 1, eff.month, eff.day)
        premium = sub.get("quoted_premium") or _rand_premium()

        # Status: first 5 expired (early months), 3 cancelled, rest active
        if i < 5:
            status_hint = "expired"
        elif i < 8:
            status_hint = "cancelled"
        else:
            status_hint = "active"

        policies.append(
            {
                "submission_id": sub["submission_id"],
                "product_id": "cyber-smb",
                "policyholder_name": sub["company_name"],
                "effective_date": eff.isoformat(),
                "expiration_date": exp.isoformat(),
                "premium": premium,
                "coverages": _build_coverages(premium),
                "_status_hint": status_hint,
                "_company": sub["company_name"],
                "_effective": eff,
            }
        )
    return policies


def generate_claims(
    policy_records: list[dict],
) -> list[tuple[dict, str, str]]:
    """Generate 15 claim payloads from active/expired policies.

    Returns list of (payload, cause, severity) tuples.
    """
    # Pick ~40% of policies to have claims
    eligible = [p for p in policy_records if p.get("_status_hint") != "cancelled"]
    claimable = random.sample(eligible, min(15, len(eligible)))

    claims = []
    for i, pol in enumerate(claimable):
        cause = CLAIM_CAUSES[i % len(CLAIM_CAUSES)]
        severity = CLAIM_SEVERITIES[i % len(CLAIM_SEVERITIES)]
        description = _fill_claim_description(cause)

        # Loss date: within the policy period, biased toward recent
        eff = pol["_effective"]
        days_into = random.randint(30, 300)
        loss_date = eff + timedelta(days=days_into)

        # Map domain cause to API claim_type
        cause_to_type = {
            "ransomware": "ransomware",
            "data_breach": "data_breach",
            "social_engineering": "other",
            "denial_of_service": "business_interruption",
            "unauthorized_access": "data_breach",
            "system_failure": "other",
        }
        claim_type = cause_to_type.get(cause, "other")

        reporter = random.choice(REPORTED_BY_NAMES)

        claims.append(
            (
                {
                    "policy_id": pol["policy_id"],
                    "claim_type": claim_type,
                    "description": description,
                    "date_of_loss": loss_date.isoformat(),
                    "reported_by": reporter,
                    "metadata": {
                        "cause_of_loss": cause,
                        "severity": severity,
                        "source": "seed_demo_business",
                    },
                },
                cause,
                severity,
            )
        )
    return claims


def generate_reserves(severity: str) -> list[dict]:
    """Generate reserve entries based on claim severity."""
    reserve_amounts = {
        "simple": [(5_000, 25_000)],
        "moderate": [(15_000, 75_000), (5_000, 20_000)],
        "complex": [(50_000, 250_000), (10_000, 50_000)],
        "catastrophe": [(200_000, 1_000_000), (50_000, 150_000)],
    }
    ranges = reserve_amounts.get(severity, [(10_000, 50_000)])
    reserves = []
    for i, (lo, hi) in enumerate(ranges):
        category = "indemnity" if i == 0 else "expense"
        amount = round(random.uniform(lo, hi) / 1_000) * 1_000
        reserves.append(
            {
                "category": category,
                "amount": float(amount),
                "currency": "USD",
                "notes": f"Initial {category} reserve — {severity} severity",
            }
        )
    return reserves


def generate_payments(severity: str, company: str) -> list[dict] | None:
    """Generate payment for closed claims (simple/moderate only)."""
    if severity not in ("simple", "moderate"):
        return None
    amount_range = {
        "simple": (3_000, 20_000),
        "moderate": (10_000, 60_000),
    }
    lo, hi = amount_range[severity]
    amount = round(random.uniform(lo, hi) / 500) * 500
    return [
        {
            "payee": company,
            "amount": float(amount),
            "currency": "USD",
            "category": "indemnity",
            "reference": f"CHK-{random.randint(10000, 99999)}",
            "notes": "Settlement payment",
        }
    ]


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed OpenInsure demo data")
    parser.add_argument("--url", default=DEFAULT_URL, help="Backend URL")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clear existing data first (not implemented)",
    )
    args = parser.parse_args()

    api = APIClient(args.url)

    print("=" * 65)
    print("  OpenInsure — 12-Month Demo Business Data Seed")
    print(f"  Target: {args.url}")
    print("=" * 65)

    # Health check
    if api.health_check():
        print("\n  ✓ Backend is reachable")
    else:
        print("\n  ✗ Backend health check failed — continuing anyway...")

    # ------------------------------------------------------------------
    # Step 1: Create 120 submissions
    # ------------------------------------------------------------------
    print(f"\n{'─' * 55}")
    print("  Step 1: Creating 120 submissions (12 months)")
    print(f"{'─' * 55}")

    all_subs = generate_submissions()
    bound_subs: list[dict] = []
    current_month = None

    for sub in all_subs:
        month = sub["payload"]["metadata"]["month"]
        if month != current_month:
            current_month = month
            print(f"\n  ── {month} ──")

        result = api.post("submissions", sub["payload"])
        if result:
            api.stats["submissions"] += 1
            sub_id = result.get("id", "")
            status = sub["target_status"]
            ch = sub["payload"]["channel"]
            name = sub["company_name"]
            print(f"    + {name:<35} {ch:<8} → {status}")

            # Track bound submissions for policy creation
            if status == "bound":
                sub["submission_id"] = sub_id
                bound_subs.append(sub)
        else:
            # Still track for numbering even on failure
            if sub["target_status"] == "bound":
                sub["submission_id"] = ""

        time.sleep(0.05)  # gentle rate limiting

    print(f"\n  Created {api.stats['submissions']} submissions")

    # ------------------------------------------------------------------
    # Step 2: Create 36 policies from bound submissions
    # ------------------------------------------------------------------
    print(f"\n{'─' * 55}")
    print(f"  Step 2: Creating {len(bound_subs)} policies from bound submissions")
    print(f"{'─' * 55}")

    policy_templates = generate_policies(bound_subs)
    policy_records: list[dict] = []

    for pt in policy_templates:
        if not pt["submission_id"]:
            print(f"    SKIP {pt['_company']} — no submission ID")
            continue

        payload = {
            "submission_id": pt["submission_id"],
            "product_id": pt["product_id"],
            "policyholder_name": pt["policyholder_name"],
            "effective_date": pt["effective_date"],
            "expiration_date": pt["expiration_date"],
            "premium": pt["premium"],
            "coverages": pt["coverages"],
        }
        result = api.post("policies", payload)
        if result:
            api.stats["policies"] += 1
            pol_id = result.get("id", "")
            pol_num = result.get("policy_number", "?")
            pt["policy_id"] = pol_id
            pt["policy_number"] = pol_num
            policy_records.append(pt)
            status = pt["_status_hint"]
            print(
                f"    + {pol_num:<20} {pt['_company']:<30} "
                f"${pt['premium']:>10,.0f}  [{status}]"
            )
        time.sleep(0.05)

    print(f"\n  Created {api.stats['policies']} policies")

    # ------------------------------------------------------------------
    # Step 3: Create 15 claims from policies
    # ------------------------------------------------------------------
    print(f"\n{'─' * 55}")
    print("  Step 3: Creating 15 claims with reserves & payments")
    print(f"{'─' * 55}")

    claim_data = generate_claims(policy_records)
    claim_records: list[dict] = []

    for payload, cause, severity in claim_data:
        result = api.post("claims", payload)
        if result:
            api.stats["claims"] += 1
            claim_id = result.get("id", "")
            claim_num = result.get("claim_number", "?")
            print(
                f"    + {claim_num:<18} {cause:<22} [{severity}]"
                f"  {payload['description'][:50]}..."
            )

            claim_records.append(
                {
                    "claim_id": claim_id,
                    "claim_number": claim_num,
                    "cause": cause,
                    "severity": severity,
                    "policy_id": payload["policy_id"],
                }
            )

            # Set reserves for claims that aren't brand new FNOL
            # (skip the last 3 — those stay as FNOL)
            if len(claim_records) <= 12:
                reserves = generate_reserves(severity)
                for res in reserves:
                    r = api.post(f"claims/{claim_id}/reserve", res)
                    if r:
                        api.stats["reserves"] += 1
                        print(
                            f"      ↳ Reserve: ${res['amount']:>10,.0f} "
                            f"({res['category']})"
                        )
                    time.sleep(0.02)

            # Add payments for closed claims (first 3)
            if len(claim_records) <= 3:
                # Find company name from policy
                company = ""
                for pr in policy_records:
                    if pr.get("policy_id") == payload["policy_id"]:
                        company = pr["_company"]
                        break
                payments = generate_payments(severity, company or "Insured")
                if payments:
                    for pmt in payments:
                        r = api.post(f"claims/{claim_id}/payment", pmt)
                        if r:
                            api.stats["payments"] += 1
                            print(
                                f"      ↳ Payment: ${pmt['amount']:>10,.0f} "
                                f"to {pmt['payee'][:30]}"
                            )
                        time.sleep(0.02)

        time.sleep(0.05)

    print(f"\n  Created {api.stats['claims']} claims")
    print(f"  Set {api.stats['reserves']} reserves")
    print(f"  Recorded {api.stats['payments']} payments")

    # ------------------------------------------------------------------
    # Summary & Verification
    # ------------------------------------------------------------------
    print(f"\n{'=' * 65}")
    print("  SEED COMPLETE — Summary")
    print(f"{'=' * 65}")
    print(f"  Submissions created:  {api.stats['submissions']}")
    print(f"  Policies created:     {api.stats['policies']}")
    print(f"  Claims created:       {api.stats['claims']}")
    print(f"  Reserves set:         {api.stats['reserves']}")
    print(f"  Payments recorded:    {api.stats['payments']}")
    print(f"  Errors encountered:   {api.stats['errors']}")

    print(f"\n  Verifying totals via API...")
    for entity in ("submissions", "policies", "claims"):
        data = api.get(entity)
        if data:
            total = data.get("total", len(data.get("items", [])))
            print(f"    {entity:>14}: {total} total in database")
        else:
            print(f"    {entity:>14}: verification failed")

    # Verify compliance decisions
    data = api.get("compliance/decisions")
    if data:
        total = data.get("total", len(data.get("items", [])))
        print(f"    {'decisions':>14}: {total} total in database")

    print()

    if api.stats["errors"] > 0:
        print(f"  ⚠  {api.stats['errors']} errors occurred — review output above")
        sys.exit(1)
    else:
        print("  ✓  All data seeded successfully!")


if __name__ == "__main__":
    main()
