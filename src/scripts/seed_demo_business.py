"""Seed OpenInsure with 3+ years of realistic insurance business data.

Creates ~1,200 submissions, ~420 policies, ~85 claims, and ~200 decision
records representing a growing cyber insurance MGA from Jan 2023 to Mar 2026.

Business profile:
    - Company: Cyber insurance MGA growing from start-up to scale
    - 2023: Start-up year — ~15 submissions/month, ~$3M GWP
    - 2024: Growth year  — ~30 submissions/month, ~$8M GWP
    - 2025: Scale year   — ~50 submissions/month, ~$15M GWP
    - 2026 Q1: Continued — ~60 submissions/month

Usage:
    python src/scripts/seed_demo_business.py [--url URL] [--force]

    --url    Backend URL (default: deployed Azure instance)
    --force  Bypass the "already seeded" check
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import date, timedelta
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Deterministic randomness so reruns produce the same data
# ---------------------------------------------------------------------------
random.seed(42)

DEFAULT_URL = "https://openinsure-backend.braveriver-f92a9f28.swedencentral.azurecontainerapps.io"

# ---------------------------------------------------------------------------
# Company names by industry (170+ unique names across 8 industries)
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
    "Cipher Logic Corp",
    "DataWeave Inc",
    "PulseGrid Technologies",
    "CloudForge Systems",
    "Nextera AI Labs",
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
    "ProVita Medical Inc",
    "AscendCare Partners",
    "BioNexus Health",
    "EliteMed Solutions",
    "PacificWell Clinics",
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
    "TrueVault Banking",
    "SilverOak Investments",
    "Crestline Capital",
    "Paragon FinServ",
    "DigitalEdge Payments",
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
    "PrimeChoice Retail",
    "Sunrise Goods Co",
    "BlueStar Commerce",
    "EcoVista Brands",
    "TrailMark Outfitters",
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
    "SolidCore Manufacturing",
    "PeakForm Industries",
    "IronEdge Fabricators",
    "TrueBuild Components",
    "AlloyTech Systems",
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
    "Paramount Legal Group",
    "Horizon Advisory LLC",
    "TrueNorth Consulting",
    "Granite Partners LLP",
    "BlueRidge Strategy",
]

EDUCATION_COMPANIES = [
    "Horizons Academy",
    "BrightPath Learning",
    "Keystone University",
    "Summit Charter Schools",
    "Pinnacle EdTech",
    "EverLearn Institute",
    "Pacific Academy Network",
    "ClearView Education",
    "TrueScholar Inc",
    "Northstar Learning Group",
    "Meridian University",
    "Crestwood Academy",
    "InnovaEd Solutions",
    "Aspire Charter Network",
    "BlueSky Schools",
]

ENERGY_COMPANIES = [
    "SolarPeak Energy",
    "Windcrest Power Corp",
    "GreenGrid Utilities",
    "Apex Renewables Inc",
    "TerraWatt Energy",
    "ClearSky Solar",
    "BlueTide Power",
    "IronFlame Energy",
    "PeakVolt Systems",
    "Meridian Energy Group",
    "SunForge Power",
    "WindBridge Renewables",
    "EcoCharge Utilities",
    "BrightWatt Inc",
    "HydroNova Energy",
]

ALL_COMPANIES: dict[str, list[str]] = {
    "Technology": TECH_COMPANIES,
    "Healthcare": HEALTHCARE_COMPANIES,
    "Financial Services": FINANCE_COMPANIES,
    "Retail": RETAIL_COMPANIES,
    "Manufacturing": MANUFACTURING_COMPANIES,
    "Professional Services": PROFESSIONAL_SERVICES,
    "Education": EDUCATION_COMPANIES,
    "Energy": ENERGY_COMPANIES,
}

# Build flat list of (name, industry) pairs and shuffle
_ALL_COMPANY_LIST: list[tuple[str, str]] = []
for _ind, _names in ALL_COMPANIES.items():
    for _n in _names:
        _ALL_COMPANY_LIST.append((_n, _ind))
random.shuffle(_ALL_COMPANY_LIST)

TOTAL_COMPANIES = len(_ALL_COMPANY_LIST)  # should be 170+

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
CLAIM_DESCRIPTIONS: dict[str, list[str]] = {
    "ransomware": [
        "Ransomware attack encrypted production databases and file servers. {ransom} ransom demanded via cryptocurrency. Forensics team engaged, breach counsel notified.",
        "LockBit variant deployed via compromised RDP credentials. All on-premise systems encrypted. Backups partially intact — recovery estimated at {days} days.",
        "Ransomware spread through phishing email targeting accounts payable. Encrypted 3 file servers and ERP system. Business operations severely impacted.",
        "BlackCat ransomware deployed after initial access via unpatched VPN appliance. Data exfiltration confirmed before encryption. Double extortion scenario.",
        "Play ransomware group exploited exposed Citrix gateway. Encrypted file shares across 4 departments. Demanding {ransom} in Bitcoin within 72 hours.",
        "Akira ransomware variant entered via compromised service account. Domain controller encrypted. Full AD rebuild required. {days}-day estimated recovery.",
    ],
    "data_breach": [
        "Customer PII data breach via unpatched REST API vulnerability. Approximately {records} records exposed including names, emails, and payment details.",
        "Employee credentials compromised via credential stuffing attack. Attacker accessed internal HR system containing SSNs and salary data for {records} employees.",
        "Third-party vendor breach exposed client data shared via unsecured SFTP. {records} records affected across multiple clients. Notification obligations triggered.",
        "SQL injection attack against customer portal exposed {records} records including names, addresses, and partial payment card numbers. PCI-DSS notification required.",
        "Misconfigured cloud storage bucket publicly exposed {records} customer records for {days} days before discovery. PHI data involved — HIPAA notification required.",
    ],
    "social_engineering": [
        "Business email compromise targeting CFO. Wire transfer of ${amount} sent to fraudulent account. Bank notified within {hours} hours, partial recovery in progress.",
        "Sophisticated spear-phishing campaign impersonating CEO. Accounts payable processed {count} fraudulent invoices totaling ${amount} before detection.",
        "Vendor impersonation scheme redirected legitimate payments. Attacker modified bank details in email thread. ${amount} diverted over {weeks} weeks.",
        "Deepfake voice phishing call impersonating CFO directed urgent wire transfer of ${amount}. Finance team bypassed dual-control procedures.",
    ],
    "denial_of_service": [
        "Sustained DDoS attack caused {hours}-hour service outage for client-facing platform. Estimated ${amount} in business interruption losses and SLA penalties.",
        "Volumetric DDoS attack (peak {gbps} Gbps) overwhelmed ISP-level mitigation. E-commerce platform offline for {hours} hours during peak sales period.",
        "Application-layer DDoS targeting API endpoints. Legitimate traffic indistinguishable from attack. Service degradation lasted {hours} hours. SLA credits issued.",
    ],
    "unauthorized_access": [
        "Former employee accessed analytics platform {weeks} weeks after termination using unrevoked credentials. Downloaded proprietary datasets and client reports.",
        "Unauthorized access detected via anomalous login from foreign IP. Attacker used stolen admin credentials to access cloud infrastructure for {days} days before detection.",
        "Compromised contractor VPN credentials used to access production databases. Lateral movement detected across {count} systems before containment.",
    ],
    "system_failure": [
        "Critical system failure during cloud migration caused {hours}-hour outage. Data integrity issues detected in migrated databases affecting {records} customer records.",
        "Cascading infrastructure failure after failed firmware update bricked {count} network switches. Full data center outage for {hours} hours.",
    ],
    "other": [
        "Cryptojacking malware detected on {count} servers consuming excessive compute resources for {weeks} weeks before detection. Performance degradation impacted customer-facing services.",
        "Insider threat — employee exfiltrated proprietary source code to personal cloud storage over {weeks} weeks. Detected during routine DLP audit.",
        "Supply chain attack via compromised software update affected {count} internal systems. Malicious code established persistent backdoor.",
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
    "Karen White, CISO",
    "Brian O'Sullivan, IT Manager",
    "Patricia Gomez, CRO",
    "Andrew Kim, Security Analyst",
    "Diana Foster, VP Technology",
]

# ---------------------------------------------------------------------------
# Month-by-month submission volumes (Jan 2023 → Mar 2026 = 39 months)
#
# 2023 (12 months): ~15 avg → total ~180  (start-up, ramping up)
# 2024 (12 months): ~30 avg → total ~360  (growth, investor milestone)
# 2025 (12 months): ~50 avg → total ~600  (scale, large broker partnerships)
# 2026 Q1 (3 months): ~60 avg → total ~180 (continued momentum)
# Grand total: ~1,320  (will be trimmed to ~1,200 via distribution)
# ---------------------------------------------------------------------------


def _build_month_list() -> list[date]:
    """Return first-of-month dates from Jan 2023 through Mar 2026."""
    months: list[date] = []
    for year in range(2023, 2027):
        end_month = 3 if year == 2026 else 12
        for m in range(1, end_month + 1):
            months.append(date(year, m, 1))
    return months


MONTHS = _build_month_list()  # 39 entries


def _build_subs_per_month() -> list[int]:
    """Submission counts per month following a realistic growth curve.

    Returns a list of 39 ints totalling ~1,200.
    """
    counts: list[int] = []

    # 2023: 8 → 18, gentle ramp (avg ~12.5, total 150)
    _2023 = [8, 9, 10, 10, 11, 12, 13, 14, 14, 15, 16, 18]
    counts.extend(_2023)

    # 2024: 20 → 29, stronger growth (avg ~26, total 310)
    _2024 = [20, 21, 23, 24, 25, 26, 27, 28, 29, 29, 29, 29]
    counts.extend(_2024)

    # 2025: 38 → 52, scale phase (avg ~47, total 560)
    _2025 = [38, 40, 42, 44, 46, 48, 49, 50, 51, 52, 50, 50]
    counts.extend(_2025)

    # 2026 Q1: 58 → 62 (avg ~60, total 180)
    _2026q1 = [58, 60, 62]
    counts.extend(_2026q1)

    return counts  # total = 1,200


SUBS_PER_MONTH = _build_subs_per_month()
TOTAL_SUBMISSIONS = sum(SUBS_PER_MONTH)  # ~1,198

# ---------------------------------------------------------------------------
# Status distribution (applied globally to all submissions)
#
# 35% bound (~420), 20% declined (~240), 15% quoted (~180),
# 10% underwriting (~120), 10% triaging (~120), 10% received (~120)
# ---------------------------------------------------------------------------


def _build_status_pool(n: int) -> list[str]:
    """Build a shuffled pool of target statuses for *n* submissions."""
    bound = round(n * 0.35)
    declined = round(n * 0.20)
    quoted = round(n * 0.15)
    underwriting = round(n * 0.10)
    triaging = round(n * 0.10)
    received = n - bound - declined - quoted - underwriting - triaging

    pool = (
        ["bound"] * bound
        + ["declined"] * declined
        + ["quoted"] * quoted
        + ["underwriting"] * underwriting
        + ["triaging"] * triaging
        + ["received"] * received
    )
    random.shuffle(pool)
    return pool


STATUS_POOL = _build_status_pool(TOTAL_SUBMISSIONS)


# Channel distribution: 40% broker, 25% email, 20% portal, 15% API
def _build_channel_pool(n: int) -> list[str]:
    pool = (
        ["broker"] * round(n * 0.40)
        + ["email"] * round(n * 0.25)
        + ["portal"] * round(n * 0.20)
        + ["api"] * (n - round(n * 0.40) - round(n * 0.25) - round(n * 0.20))
    )
    random.shuffle(pool)
    return pool


CHANNEL_POOL = _build_channel_pool(TOTAL_SUBMISSIONS)

# Claim cause distribution (for 85 claims)
NUM_CLAIMS = 85


def _build_claim_cause_pool(n: int) -> list[str]:
    """25% ransomware, 25% data_breach, 20% social_engineering,
    10% denial_of_service, 10% unauthorized_access, 5% system_failure, 5% other."""
    pool = (
        ["ransomware"] * round(n * 0.25)
        + ["data_breach"] * round(n * 0.25)
        + ["social_engineering"] * round(n * 0.20)
        + ["denial_of_service"] * round(n * 0.10)
        + ["unauthorized_access"] * round(n * 0.10)
        + ["system_failure"] * round(n * 0.05)
    )
    # Fill remainder with "other"
    pool += ["other"] * (n - len(pool))
    random.shuffle(pool)
    return pool


CLAIM_CAUSES = _build_claim_cause_pool(NUM_CLAIMS)


# Claim severity distribution: catastrophe 5%, complex 20%, moderate 40%, simple 35%
def _build_severity_pool(n: int) -> list[str]:
    pool = (
        ["catastrophe"] * round(n * 0.05)
        + ["complex"] * round(n * 0.20)
        + ["moderate"] * round(n * 0.40)
        + ["simple"] * (n - round(n * 0.05) - round(n * 0.20) - round(n * 0.40))
    )
    random.shuffle(pool)
    return pool


CLAIM_SEVERITIES = _build_severity_pool(NUM_CLAIMS)


# Claim status distribution: closed 40%, reserved 25%, investigating 20%, fnol 15%
def _build_claim_status_pool(n: int) -> list[str]:
    pool = (
        ["closed"] * round(n * 0.40)
        + ["reserved"] * round(n * 0.25)
        + ["investigating"] * round(n * 0.20)
        + ["fnol"] * (n - round(n * 0.40) - round(n * 0.25) - round(n * 0.20))
    )
    random.shuffle(pool)
    return pool


CLAIM_STATUS_POOL = _build_claim_status_pool(NUM_CLAIMS)


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
        "Energy": (5_000_000, 300_000_000),
    }
    lo, hi = ranges.get(industry, (1_000_000, 50_000_000))
    return random.randint(lo, hi)


def _rand_employees(revenue: int) -> int:
    """Approximate employee count from revenue."""
    per_emp = random.randint(50_000, 200_000)
    return max(10, revenue // per_emp)


def _email_domain(company: str) -> str:
    """Generate a plausible email domain from company name."""
    slug = company.lower().replace(" ", "").replace(",", "").replace(".", "").replace("&", "")
    return f"{slug[:15]}.com"


def _rand_premium() -> float:
    """Random SMB cyber premium $5K–$120K, median ~$25K."""
    base = random.triangular(5_000, 120_000, 25_000)
    return round(base / 500) * 500  # round to nearest $500


def _build_coverages(premium: float) -> list[dict[str, Any]]:
    """Build realistic coverage breakdown summing to total premium."""
    n = random.choice([2, 2, 3, 3, 3, 3, 4, 4, 5])
    chosen = random.sample(COVERAGE_TEMPLATES, min(n, len(COVERAGE_TEMPLATES)))
    remaining = premium
    coverages: list[dict[str, Any]] = []
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
        ransom=f"${random.choice([25, 50, 75, 100, 150, 200, 300, 500])}K",
        days=random.randint(3, 21),
        records=f"{random.randint(1, 500) * 1000:,}",
        amount=f"{random.randint(15, 500) * 1000:,}",
        hours=random.randint(4, 96),
        count=random.randint(2, 12),
        weeks=random.randint(2, 8),
        gbps=random.choice([15, 40, 80, 120, 200, 400]),
    )


# ---------------------------------------------------------------------------
# HTTP client wrapper
# ---------------------------------------------------------------------------


class APIClient:
    """Thin wrapper around httpx for seeding API calls."""

    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=30)
        self.stats: dict[str, int] = {
            "submissions": 0,
            "policies": 0,
            "claims": 0,
            "reserves": 0,
            "payments": 0,
            "decisions": 0,
            "errors": 0,
        }

    def post(self, endpoint: str, data: dict[str, Any]) -> dict[str, Any] | None:
        """POST to an API endpoint; return JSON on success or None."""
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

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """GET an API endpoint; return JSON on success or None."""
        try:
            r = self.client.get(f"/api/v1/{endpoint}", params=params)
            if r.status_code == 200:
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

    def existing_count(self) -> int:
        """Return total submissions already in the database."""
        data = self.get("submissions", {"limit": 1})
        if data and "total" in data:
            return data["total"]
        return 0


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------


def generate_submissions() -> list[dict[str, Any]]:
    """Generate ~1,200 submission payloads spread across 39 months."""
    submissions: list[dict[str, Any]] = []
    company_idx = 0

    for month_idx, month_start in enumerate(MONTHS):
        count = SUBS_PER_MONTH[month_idx]
        for _ in range(count):
            company_name, industry = _ALL_COMPANY_LIST[company_idx % TOTAL_COMPANIES]
            company_idx += 1

            idx = len(submissions)
            status = STATUS_POOL[idx % len(STATUS_POOL)]
            channel = CHANNEL_POOL[idx % len(CHANNEL_POOL)]

            eff_date = _rand_date_in_month(month_start)
            revenue = _rand_revenue(industry)
            emp_count = _rand_employees(revenue)
            email = f"risk@{_email_domain(company_name)}"

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


def generate_policies(bound_submissions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Generate policy payloads from bound submissions (~420 expected).

    Distributes policy statuses:
        ~67% active (280), ~21% expired (90), ~7% cancelled (30), ~5% pending renewal (20)
    Earlier policies are more likely to be expired; recent ones are active.
    """
    total = len(bound_submissions)
    # Sort by effective date to assign statuses chronologically
    sorted_subs = sorted(bound_submissions, key=lambda s: s["effective_date"])

    # First ~21% expired, next ~7% cancelled, next ~5% pending, rest active
    n_expired = round(total * 0.21)
    n_cancelled = round(total * 0.07)
    n_pending = round(total * 0.05)

    policies: list[dict[str, Any]] = []
    for i, sub in enumerate(sorted_subs):
        eff = sub["effective_date"]
        # Handle leap year edge cases
        try:
            exp = date(eff.year + 1, eff.month, eff.day)
        except ValueError:
            exp = date(eff.year + 1, eff.month, eff.day - 1)

        premium = sub.get("quoted_premium") or _rand_premium()

        if i < n_expired:
            status_hint = "expired"
        elif i < n_expired + n_cancelled:
            status_hint = "cancelled"
        elif i < n_expired + n_cancelled + n_pending:
            status_hint = "pending"
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
                "_expiration": exp,
            }
        )
    return policies


def generate_claims(policy_records: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str, str, str]]:
    """Generate 85 claim payloads from policies.

    Returns list of (payload, cause, severity, target_claim_status) tuples.
    Picks from non-cancelled policies, spreading claims across the portfolio.
    """
    eligible = [p for p in policy_records if p.get("_status_hint") != "cancelled"]
    # Pick policies to have claims — some may have >1
    claimable = random.sample(eligible, min(NUM_CLAIMS, len(eligible)))

    claims: list[tuple[dict[str, Any], str, str, str]] = []
    for i in range(NUM_CLAIMS):
        pol = claimable[i % len(claimable)]
        cause = CLAIM_CAUSES[i]
        severity = CLAIM_SEVERITIES[i]
        claim_status = CLAIM_STATUS_POOL[i]
        description = _fill_claim_description(cause)

        # Loss date within the policy period
        eff = pol["_effective"]
        exp = pol["_expiration"]
        period_days = max(30, (exp - eff).days - 30)
        days_into = random.randint(15, period_days)
        loss_date = eff + timedelta(days=days_into)

        # Map domain cause to API claim_type
        cause_to_type = {
            "ransomware": "ransomware",
            "data_breach": "data_breach",
            "social_engineering": "other",
            "denial_of_service": "business_interruption",
            "unauthorized_access": "data_breach",
            "system_failure": "other",
            "other": "other",
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
                claim_status,
            )
        )
    return claims


def generate_reserves(severity: str) -> list[dict[str, Any]]:
    """Generate reserve entries based on claim severity."""
    reserve_amounts = {
        "simple": [(5_000, 25_000)],
        "moderate": [(15_000, 75_000), (5_000, 20_000)],
        "complex": [(50_000, 250_000), (10_000, 50_000)],
        "catastrophe": [(200_000, 1_000_000), (50_000, 150_000)],
    }
    ranges = reserve_amounts.get(severity, [(10_000, 50_000)])
    reserves: list[dict[str, Any]] = []
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


def generate_payments(severity: str, company: str) -> list[dict[str, Any]] | None:
    """Generate payment for closed claims."""
    amount_range = {
        "simple": (3_000, 20_000),
        "moderate": (10_000, 60_000),
        "complex": (25_000, 150_000),
        "catastrophe": (100_000, 500_000),
    }
    lo, hi = amount_range.get(severity, (5_000, 30_000))
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
# Decision record generation
# ---------------------------------------------------------------------------

DECISION_AGENT_TYPES = [
    ("triage", "submission", "triage-agent-v2", "2.1.0"),
    ("underwriting", "submission", "underwriting-agent-v3", "3.0.1"),
    ("claims", "claim", "claims-agent-v2", "2.4.0"),
    ("pricing", "submission", "pricing-model-v4", "4.2.0"),
    ("fraud_detection", "claim", "fraud-detector-v1", "1.3.2"),
]


def _generate_decision_record(
    entity_id: str,
    entity_type: str,
    decision_type: str,
    model_id: str,
    model_version: str,
) -> dict[str, Any]:
    """Build a single decision record payload."""
    confidence = round(random.uniform(0.55, 0.99), 3)
    human_override = random.random() < 0.12  # ~12% overridden

    explanations = {
        "triage": [
            "Risk profile within appetite. Industry and revenue within acceptable parameters.",
            "Elevated risk indicators detected. Prior incidents and security posture require manual review.",
            "Automated triage complete. Low-risk profile with strong security controls.",
            "Flagged for review: revenue exceeds automated authority threshold.",
        ],
        "underwriting": [
            "Standard risk accepted. Security maturity score meets minimum threshold.",
            "Substandard risk — recommend higher deductible or reduced limits.",
            "Preferred risk classification. Strong security controls and incident response plan.",
            "Referral to senior underwriter — complex risk profile with prior claims.",
        ],
        "claims": [
            "Claim validated against policy terms. Coverage confirmed for reported incident.",
            "Initial assessment: moderate severity. Recommend forensics engagement.",
            "Claim investigation flagged — timeline inconsistencies require further review.",
            "Fast-track assessment complete. Simple claim within delegated authority.",
        ],
        "pricing": [
            "Base rate applied with industry-specific loading factor. No adverse experience.",
            "Experience-rated premium reflects prior loss history. 15% surcharge applied.",
            "Competitive rate generated. Risk score within preferred tier parameters.",
            "Manual rate required — automated model confidence below threshold.",
        ],
        "fraud_detection": [
            "No fraud indicators detected. Claim patterns consistent with reported incident.",
            "Low fraud score. All documentation verified and consistent.",
            "Elevated fraud risk — claim timing and description warrant investigation.",
            "Standard fraud check passed. No anomalous patterns identified.",
        ],
    }

    return {
        "decision_type": decision_type,
        "entity_id": entity_id,
        "entity_type": entity_type,
        "model_id": model_id,
        "model_version": model_version,
        "input_summary": {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "features_evaluated": random.randint(12, 45),
        },
        "output_summary": {
            "recommendation": random.choice(["approve", "decline", "refer", "accept"]),
            "score": round(random.uniform(0.1, 9.8), 2),
            "flags": random.sample(
                [
                    "high_revenue",
                    "prior_claims",
                    "low_security",
                    "new_customer",
                    "large_limit",
                    "complex_risk",
                    "standard_risk",
                    "preferred_risk",
                ],
                k=random.randint(0, 3),
            ),
        },
        "confidence": confidence,
        "explanation": random.choice(explanations.get(decision_type, explanations["triage"])),
        "human_override": human_override,
        "override_reason": "Senior underwriter review required per authority matrix" if human_override else None,
    }


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed OpenInsure with multi-year demo data")
    parser.add_argument("--url", default=DEFAULT_URL, help="Backend URL")
    parser.add_argument("--force", action="store_true", help="Bypass already-seeded check")
    args = parser.parse_args()

    api = APIClient(args.url)

    print("=" * 70)
    print("  OpenInsure — Multi-Year Demo Business Data Seed (Jan 2023 – Mar 2026)")
    print(f"  Target: {args.url}")
    print(f"  Plan: ~{TOTAL_SUBMISSIONS} submissions, ~{round(TOTAL_SUBMISSIONS * 0.35)} policies,")
    print(f"         ~{NUM_CLAIMS} claims, ~200 decision records")
    print("=" * 70)

    # Health check
    if api.health_check():
        print("\n  ✓ Backend is reachable")
    else:
        print("\n  ✗ Backend health check failed — continuing anyway...")

    # Already-seeded guard
    if not args.force:
        existing = api.existing_count()
        if existing > 500:
            print(f"\n  ⚠ Database already contains {existing} submissions.")
            print("    Looks like it's already seeded. Use --force to override.")
            sys.exit(0)
        elif existing > 0:
            print(f"\n  ℹ Database has {existing} existing submissions. Proceeding with seed...")

    # ------------------------------------------------------------------
    # Step 1: Create ~1,200 submissions across 39 months
    # ------------------------------------------------------------------
    print(f"\n{'─' * 60}")
    print(f"  Step 1: Creating ~{TOTAL_SUBMISSIONS} submissions (Jan 2023 – Mar 2026)")
    print(f"{'─' * 60}")

    all_subs = generate_submissions()
    bound_subs: list[dict[str, Any]] = []
    current_month: str | None = None
    month_count = 0

    for _sub_idx, sub in enumerate(all_subs):
        month = sub["payload"]["metadata"]["month"]
        if month != current_month:
            if current_month is not None:
                print(f"    ({month_count} submissions)")
            current_month = month
            month_count = 0
            print(f"\n  ── {month} ──")

        result = api.post("submissions", sub["payload"])
        month_count += 1
        if result:
            api.stats["submissions"] += 1
            sub_id = result.get("id", "")

            if sub["target_status"] == "bound":
                sub["submission_id"] = sub_id
                bound_subs.append(sub)

            # Progress indicator every 50 records
            if api.stats["submissions"] % 50 == 0:
                print(f"    ... {api.stats['submissions']} submissions created")
        else:
            if sub["target_status"] == "bound":
                sub["submission_id"] = ""

        time.sleep(0.03)  # gentle rate limiting

    if current_month is not None:
        print(f"    ({month_count} submissions)")

    print(f"\n  ✓ Created {api.stats['submissions']} submissions ({len(bound_subs)} bound)")

    # ------------------------------------------------------------------
    # Step 2: Create ~420 policies from bound submissions
    # ------------------------------------------------------------------
    # Filter out bound subs that failed
    bound_subs = [s for s in bound_subs if s.get("submission_id")]

    print(f"\n{'─' * 60}")
    print(f"  Step 2: Creating {len(bound_subs)} policies from bound submissions")
    print(f"{'─' * 60}")

    policy_templates = generate_policies(bound_subs)
    policy_records: list[dict[str, Any]] = []

    for pt in policy_templates:
        if not pt["submission_id"]:
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
            pt["policy_id"] = result.get("id", "")
            pt["policy_number"] = result.get("policy_number", "?")
            policy_records.append(pt)

            if api.stats["policies"] % 50 == 0:
                print(f"    ... {api.stats['policies']} policies created")

        time.sleep(0.03)

    print(f"\n  ✓ Created {api.stats['policies']} policies")

    # Print status distribution
    status_counts: dict[str, int] = {}
    for pr in policy_records:
        s = pr["_status_hint"]
        status_counts[s] = status_counts.get(s, 0) + 1
    for s, c in sorted(status_counts.items()):
        print(f"      {s}: {c}")

    # ------------------------------------------------------------------
    # Step 3: Create 85 claims with reserves & payments
    # ------------------------------------------------------------------
    print(f"\n{'─' * 60}")
    print(f"  Step 3: Creating {NUM_CLAIMS} claims with reserves & payments")
    print(f"{'─' * 60}")

    claim_data = generate_claims(policy_records)
    claim_records: list[dict[str, Any]] = []

    for payload, cause, severity, target_status in claim_data:
        result = api.post("claims", payload)
        if result:
            api.stats["claims"] += 1
            claim_id = result.get("id", "")
            claim_num = result.get("claim_number", "?")

            claim_records.append(
                {
                    "claim_id": claim_id,
                    "claim_number": claim_num,
                    "cause": cause,
                    "severity": severity,
                    "target_status": target_status,
                    "policy_id": payload["policy_id"],
                }
            )

            # Set reserves for claims that aren't FNOL
            if target_status != "fnol":
                reserves = generate_reserves(severity)
                for res in reserves:
                    r = api.post(f"claims/{claim_id}/reserve", res)
                    if r:
                        api.stats["reserves"] += 1
                    time.sleep(0.02)

            # Add payments and close for closed claims
            if target_status == "closed":
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
                        time.sleep(0.02)

                # Close the claim
                api.post(
                    f"claims/{claim_id}/close",
                    {
                        "reason": f"Claim resolved — {cause} incident. Settlement and recovery complete.",
                        "outcome": "resolved",
                    },
                )

            if api.stats["claims"] % 10 == 0:
                print(f"    ... {api.stats['claims']} claims created")

        time.sleep(0.03)

    print(f"\n  ✓ Created {api.stats['claims']} claims")
    print(f"    Reserves set: {api.stats['reserves']}")
    print(f"    Payments recorded: {api.stats['payments']}")

    # Print claim status distribution
    claim_status_counts: dict[str, int] = {}
    for cr in claim_records:
        s = cr["target_status"]
        claim_status_counts[s] = claim_status_counts.get(s, 0) + 1
    for s, c in sorted(claim_status_counts.items()):
        print(f"      {s}: {c}")

    # ------------------------------------------------------------------
    # Step 4: Generate ~200 decision records
    # ------------------------------------------------------------------
    print(f"\n{'─' * 60}")
    print("  Step 4: Generating ~200 decision records")
    print(f"{'─' * 60}")

    # Decisions are created as side-effects of triage/quote/bind/claim operations.
    # We'll try POSTing to the compliance decisions endpoint if it exists, otherwise
    # just count the decisions already auto-created by the API pipeline.
    decisions_created = 0

    # Gather entity IDs for decision generation
    all_entity_ids: list[tuple[str, str]] = []  # (entity_id, entity_type)

    # Submissions that went through triage
    triaged_subs = [
        s
        for s in all_subs
        if s.get("submission_id") and s["target_status"] in ("underwriting", "quoted", "bound", "declined")
    ]
    for sub in triaged_subs[:120]:
        if sub.get("submission_id"):
            all_entity_ids.append((sub["submission_id"], "submission"))

    # Claims
    for cr in claim_records[:50]:
        all_entity_ids.append((cr["claim_id"], "claim"))

    # Policies
    for pr in policy_records[:30]:
        if pr.get("policy_id"):
            all_entity_ids.append((pr["policy_id"], "policy"))

    random.shuffle(all_entity_ids)

    # Try to POST decision records — many APIs auto-create them during triage/quote/etc.
    # We try posting up to 200 and count successes.
    target_decisions = 200
    for i in range(min(target_decisions, len(all_entity_ids))):
        entity_id, entity_type = all_entity_ids[i % len(all_entity_ids)]
        agent = random.choice(DECISION_AGENT_TYPES)
        decision_type, _expected_entity_type, model_id, model_version = agent

        # Use the actual entity type
        record = _generate_decision_record(
            entity_id=entity_id,
            entity_type=entity_type,
            decision_type=decision_type,
            model_id=model_id,
            model_version=model_version,
        )

        result = api.post("compliance/decisions", record)
        if result:
            decisions_created += 1
            api.stats["decisions"] += 1
        # If the POST endpoint doesn't exist, count will stay at 0

        if (i + 1) % 50 == 0:
            print(f"    ... {i + 1} decision records attempted ({decisions_created} created)")

        time.sleep(0.02)

    # Check how many decisions exist (including auto-created)
    dec_data = api.get("compliance/decisions", {"limit": 1})
    total_decisions = dec_data.get("total", 0) if dec_data else decisions_created

    if decisions_created == 0 and total_decisions > 0:
        print("\n  ℹ Decision records are auto-generated by the API pipeline.")
        print(f"    {total_decisions} decision records exist in the database.")
    elif decisions_created > 0:
        print(f"\n  ✓ Created {decisions_created} decision records")
    else:
        print("\n  ℹ Decision record POST not available — decisions created via pipeline operations.")

    # ------------------------------------------------------------------
    # Summary & Verification
    # ------------------------------------------------------------------
    print(f"\n{'=' * 70}")
    print("  SEED COMPLETE — Summary")
    print(f"{'=' * 70}")
    print(f"  Submissions created:  {api.stats['submissions']:>6,}")
    print(f"  Policies created:     {api.stats['policies']:>6,}")
    print(f"  Claims created:       {api.stats['claims']:>6,}")
    print(f"  Reserves set:         {api.stats['reserves']:>6,}")
    print(f"  Payments recorded:    {api.stats['payments']:>6,}")
    print(f"  Decision records:     {max(api.stats['decisions'], total_decisions):>6,}")
    print(f"  Errors encountered:   {api.stats['errors']:>6,}")

    print("\n  Verifying totals via API...")
    for entity in ("submissions", "policies", "claims"):
        data = api.get(entity, {"limit": 1})
        if data:
            total = data.get("total", len(data.get("items", [])))
            print(f"    {entity:>14}: {total:,} total in database")
        else:
            print(f"    {entity:>14}: verification failed")

    dec_data = api.get("compliance/decisions", {"limit": 1})
    if dec_data:
        total = dec_data.get("total", len(dec_data.get("items", [])))
        print(f"    {'decisions':>14}: {total:,} total in database")

    print()

    if api.stats["errors"] > 0:
        print(f"  ⚠  {api.stats['errors']} errors occurred — review output above")
        sys.exit(1)
    else:
        print("  ✓  All data seeded successfully!")


if __name__ == "__main__":
    main()
