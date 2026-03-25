"""Seed the deployed OpenInsure backend with realistic insurance data.

Creates submissions, policies, claims, and compliance records that make
the dashboards look like a real cyber insurance MGA's operations.

Usage:
    python src/scripts/seed_sql_data.py [BASE_URL]

Example:
    python src/scripts/seed_sql_data.py os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")
"""

import sys

import httpx

BASE_URL = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")"
)

client = httpx.Client(base_url=BASE_URL, timeout=30)

# --- Counters ---
stats = {"submissions": 0, "policies": 0, "claims": 0, "errors": 0}


def create(endpoint: str, data: dict) -> dict | None:
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


# ---------------------------------------------------------------------------
# 1. SUBMISSIONS — 20 companies, various channels & risk profiles
# ---------------------------------------------------------------------------
SUBMISSIONS = [
    {
        "applicant_name": "Meridian Healthcare Group",
        "applicant_email": "underwriting@meridianhg.com",
        "channel": "email",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 85_000_000, "employee_count": 1200, "industry": "Healthcare"},
    },
    {
        "applicant_name": "Quantum Financial Services",
        "applicant_email": "risk@quantumfs.com",
        "channel": "broker",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 250_000_000, "employee_count": 3500, "industry": "Financial Services"},
    },
    {
        "applicant_name": "Atlas Manufacturing Inc",
        "applicant_email": "cfo@atlasmfg.com",
        "channel": "portal",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 42_000_000, "employee_count": 600, "industry": "Manufacturing"},
    },
    {
        "applicant_name": "Pinnacle Legal Partners LLP",
        "applicant_email": "managing@pinnaclellp.com",
        "channel": "email",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 18_000_000, "employee_count": 120, "industry": "Legal"},
    },
    {
        "applicant_name": "NovaTech Solutions",
        "applicant_email": "ciso@novatechsol.com",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 15_000_000, "employee_count": 200, "industry": "Technology"},
    },
    {
        "applicant_name": "Emerald Retail Group",
        "applicant_email": "ops@emeraldretail.com",
        "channel": "broker",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 120_000_000, "employee_count": 2800, "industry": "Retail"},
    },
    {
        "applicant_name": "Horizon Education Trust",
        "applicant_email": "admin@horizonedu.org",
        "channel": "portal",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 8_000_000, "employee_count": 350, "industry": "Education"},
    },
    {
        "applicant_name": "Sterling Construction Co",
        "applicant_email": "finance@sterlingcc.com",
        "channel": "email",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 65_000_000, "employee_count": 900, "industry": "Construction"},
    },
    {
        "applicant_name": "BluePeak Analytics",
        "applicant_email": "security@bluepeak.io",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 12_000_000, "employee_count": 85, "industry": "Technology"},
    },
    {
        "applicant_name": "Pacific Coast Logistics",
        "applicant_email": "risk@paccoast.com",
        "channel": "broker",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 95_000_000, "employee_count": 1500, "industry": "Transportation"},
    },
    {
        "applicant_name": "Redwood Biotech",
        "applicant_email": "compliance@redwoodbio.com",
        "channel": "email",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 180_000_000, "employee_count": 2200, "industry": "Biotechnology"},
    },
    {
        "applicant_name": "Summit Advisory Group",
        "applicant_email": "partner@summitadvisory.com",
        "channel": "portal",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 32_000_000, "employee_count": 180, "industry": "Consulting"},
    },
    {
        "applicant_name": "Ironclad Security Systems",
        "applicant_email": "cto@ironcladsec.com",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 55_000_000, "employee_count": 400, "industry": "Cybersecurity"},
    },
    {
        "applicant_name": "Coastal Properties Management",
        "applicant_email": "admin@coastalpm.com",
        "channel": "broker",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 22_000_000, "employee_count": 150, "industry": "Real Estate"},
    },
    {
        "applicant_name": "Vertex Energy Solutions",
        "applicant_email": "it@vertexenergy.com",
        "channel": "email",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 140_000_000, "employee_count": 1800, "industry": "Energy"},
    },
    {
        "applicant_name": "Keystone Medical Devices",
        "applicant_email": "regulatory@keystonemd.com",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 75_000_000, "employee_count": 500, "industry": "Medical Devices"},
    },
    {
        "applicant_name": "Alpine Wealth Management",
        "applicant_email": "compliance@alpinewm.com",
        "channel": "broker",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 28_000_000, "employee_count": 95, "industry": "Financial Services"},
    },
    {
        "applicant_name": "Cascade Software Inc",
        "applicant_email": "devops@cascadesw.com",
        "channel": "portal",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 9_000_000, "employee_count": 60, "industry": "Technology"},
    },
    {
        "applicant_name": "Granite Insurance Brokers",
        "applicant_email": "ops@granitebrok.com",
        "channel": "email",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 5_000_000, "employee_count": 35, "industry": "Insurance"},
    },
    {
        "applicant_name": "Sapphire Cloud Services",
        "applicant_email": "sec@sapphirecloud.io",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 20_000_000, "employee_count": 110, "industry": "Cloud Services"},
    },
]

# ---------------------------------------------------------------------------
# 2. POLICIES — 12 bound policies with realistic premiums & coverages
#    (We create these using submission IDs from step 1)
# ---------------------------------------------------------------------------
POLICY_TEMPLATES = [
    {
        "sub_index": 0,
        "product_id": "cyber-smb",
        "policyholder_name": "Meridian Healthcare Group",
        "effective_date": "2026-01-01",
        "expiration_date": "2027-01-01",
        "premium": 45000.00,
        "coverages": [
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 2000000,
                "deductible": 25000,
                "premium": 15000,
            },
            {
                "coverage_code": "REG-DEFENSE",
                "coverage_name": "Regulatory Defense",
                "limit": 1000000,
                "deductible": 10000,
                "premium": 12000,
            },
            {
                "coverage_code": "BUS-INTRPT",
                "coverage_name": "Business Interruption",
                "limit": 1500000,
                "deductible": 50000,
                "premium": 18000,
            },
        ],
    },
    {
        "sub_index": 1,
        "product_id": "cyber-smb",
        "policyholder_name": "Quantum Financial Services",
        "effective_date": "2026-02-01",
        "expiration_date": "2027-02-01",
        "premium": 78000.00,
        "coverages": [
            {
                "coverage_code": "THIRD-PARTY",
                "coverage_name": "Third-Party Liability",
                "limit": 5000000,
                "deductible": 50000,
                "premium": 35000,
            },
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 3000000,
                "deductible": 25000,
                "premium": 22000,
            },
            {
                "coverage_code": "CYBER-CRIME",
                "coverage_name": "Cyber Crime / Fraud",
                "limit": 2000000,
                "deductible": 25000,
                "premium": 21000,
            },
        ],
    },
    {
        "sub_index": 2,
        "product_id": "cyber-smb",
        "policyholder_name": "Atlas Manufacturing Inc",
        "effective_date": "2026-01-15",
        "expiration_date": "2027-01-15",
        "premium": 32000.00,
        "coverages": [
            {
                "coverage_code": "BUS-INTRPT",
                "coverage_name": "Business Interruption",
                "limit": 2000000,
                "deductible": 75000,
                "premium": 18000,
            },
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 1000000,
                "deductible": 15000,
                "premium": 14000,
            },
        ],
    },
    {
        "sub_index": 4,
        "product_id": "cyber-smb",
        "policyholder_name": "NovaTech Solutions",
        "effective_date": "2026-03-01",
        "expiration_date": "2027-03-01",
        "premium": 18500.00,
        "coverages": [
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 1000000,
                "deductible": 10000,
                "premium": 9500,
            },
            {
                "coverage_code": "THIRD-PARTY",
                "coverage_name": "Third-Party Liability",
                "limit": 1000000,
                "deductible": 15000,
                "premium": 9000,
            },
        ],
    },
    {
        "sub_index": 8,
        "product_id": "cyber-smb",
        "policyholder_name": "BluePeak Analytics",
        "effective_date": "2025-06-01",
        "expiration_date": "2026-06-01",
        "premium": 22000.00,
        "coverages": [
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 1000000,
                "deductible": 10000,
                "premium": 12000,
            },
            {
                "coverage_code": "BUS-INTRPT",
                "coverage_name": "Business Interruption",
                "limit": 500000,
                "deductible": 25000,
                "premium": 10000,
            },
        ],
    },
    {
        "sub_index": 12,
        "product_id": "cyber-smb",
        "policyholder_name": "Ironclad Security Systems",
        "effective_date": "2025-09-01",
        "expiration_date": "2026-09-01",
        "premium": 55000.00,
        "coverages": [
            {
                "coverage_code": "THIRD-PARTY",
                "coverage_name": "Third-Party Liability",
                "limit": 5000000,
                "deductible": 50000,
                "premium": 30000,
            },
            {
                "coverage_code": "CYBER-CRIME",
                "coverage_name": "Cyber Crime / Fraud",
                "limit": 2000000,
                "deductible": 25000,
                "premium": 25000,
            },
        ],
    },
    {
        "sub_index": 5,
        "product_id": "cyber-smb",
        "policyholder_name": "Emerald Retail Group",
        "effective_date": "2026-01-01",
        "expiration_date": "2027-01-01",
        "premium": 28000.00,
        "coverages": [
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 2000000,
                "deductible": 25000,
                "premium": 16000,
            },
            {
                "coverage_code": "PCI-DSS",
                "coverage_name": "PCI-DSS Fines & Penalties",
                "limit": 500000,
                "deductible": 10000,
                "premium": 12000,
            },
        ],
    },
    {
        "sub_index": 11,
        "product_id": "cyber-smb",
        "policyholder_name": "Summit Advisory Group",
        "effective_date": "2025-11-01",
        "expiration_date": "2026-11-01",
        "premium": 41000.00,
        "coverages": [
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 2000000,
                "deductible": 20000,
                "premium": 18000,
            },
            {
                "coverage_code": "THIRD-PARTY",
                "coverage_name": "Third-Party Liability",
                "limit": 3000000,
                "deductible": 25000,
                "premium": 23000,
            },
        ],
    },
    {
        "sub_index": 3,
        "product_id": "cyber-smb",
        "policyholder_name": "Pinnacle Legal Partners LLP",
        "effective_date": "2025-01-01",
        "expiration_date": "2026-01-01",
        "premium": 35000.00,
        "coverages": [
            {
                "coverage_code": "THIRD-PARTY",
                "coverage_name": "Third-Party Liability",
                "limit": 3000000,
                "deductible": 25000,
                "premium": 20000,
            },
            {
                "coverage_code": "REG-DEFENSE",
                "coverage_name": "Regulatory Defense",
                "limit": 1000000,
                "deductible": 15000,
                "premium": 15000,
            },
        ],
    },
    {
        "sub_index": 13,
        "product_id": "cyber-smb",
        "policyholder_name": "Coastal Properties Management",
        "effective_date": "2025-06-01",
        "expiration_date": "2026-06-01",
        "premium": 19000.00,
        "coverages": [
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 500000,
                "deductible": 10000,
                "premium": 11000,
            },
            {
                "coverage_code": "BUS-INTRPT",
                "coverage_name": "Business Interruption",
                "limit": 500000,
                "deductible": 25000,
                "premium": 8000,
            },
        ],
    },
    {
        "sub_index": 10,
        "product_id": "cyber-smb",
        "policyholder_name": "Redwood Biotech",
        "effective_date": "2026-02-15",
        "expiration_date": "2027-02-15",
        "premium": 62000.00,
        "coverages": [
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 5000000,
                "deductible": 50000,
                "premium": 28000,
            },
            {
                "coverage_code": "REG-DEFENSE",
                "coverage_name": "Regulatory Defense",
                "limit": 2000000,
                "deductible": 25000,
                "premium": 18000,
            },
            {
                "coverage_code": "THIRD-PARTY",
                "coverage_name": "Third-Party Liability",
                "limit": 3000000,
                "deductible": 25000,
                "premium": 16000,
            },
        ],
    },
    {
        "sub_index": 17,
        "product_id": "cyber-smb",
        "policyholder_name": "Cascade Software Inc",
        "effective_date": "2026-03-01",
        "expiration_date": "2027-03-01",
        "premium": 15000.00,
        "coverages": [
            {
                "coverage_code": "BREACH-RESP",
                "coverage_name": "Breach Response",
                "limit": 500000,
                "deductible": 5000,
                "premium": 8000,
            },
            {
                "coverage_code": "CYBER-CRIME",
                "coverage_name": "Cyber Crime / Fraud",
                "limit": 250000,
                "deductible": 5000,
                "premium": 7000,
            },
        ],
    },
]

# ---------------------------------------------------------------------------
# 3. CLAIMS — 8 claims against policies with realistic cyber scenarios
#    (We create these using policy IDs from step 2)
# ---------------------------------------------------------------------------
CLAIM_TEMPLATES = [
    {
        "pol_index": 0,
        "claim_type": "ransomware",
        "description": "Ransomware attack encrypted production databases and EHR systems. $50K ransom demanded via Bitcoin. Forensics team engaged, breach counsel notified, regulatory clock started for HIPAA notification.",
        "date_of_loss": "2026-02-15",
        "reported_by": "Dr. Sarah Chen, CISO",
    },
    {
        "pol_index": 1,
        "claim_type": "other",
        "description": "Sophisticated spear-phishing campaign targeted CFO. Wire transfer of $125,000 sent to fraudulent account in Singapore. Bank notified within 4 hours, partial recovery in progress.",
        "date_of_loss": "2026-01-20",
        "reported_by": "James Morrison, CFO",
    },
    {
        "pol_index": 2,
        "claim_type": "data_breach",
        "description": "Customer PII data breach via unpatched REST API vulnerability (CVE-2026-1234). Approximately 15,000 customer records exposed including names, addresses, and order history.",
        "date_of_loss": "2026-03-01",
        "reported_by": "Mike Torres, IT Director",
    },
    {
        "pol_index": 3,
        "claim_type": "business_interruption",
        "description": "Sustained DDoS attack caused 48-hour service outage for client-facing SaaS platform. Estimated $80,000 in business interruption losses and SLA penalty payments.",
        "date_of_loss": "2026-02-28",
        "reported_by": "Lisa Park, VP Engineering",
    },
    {
        "pol_index": 4,
        "claim_type": "data_breach",
        "description": "Former data analyst accessed analytics platform 3 weeks after termination using unrevoked credentials. Downloaded client datasets containing proprietary market research.",
        "date_of_loss": "2025-11-15",
        "reported_by": "Tom Bradley, HR Director",
    },
    {
        "pol_index": 5,
        "claim_type": "data_breach",
        "description": "AWS S3 bucket misconfiguration exposed internal security audit documents for approximately 72 hours. No PII confirmed, but confidential vulnerability assessments were publicly accessible.",
        "date_of_loss": "2025-10-01",
        "reported_by": "Rachel Kim, Cloud Architect",
    },
    {
        "pol_index": 6,
        "claim_type": "other",
        "description": "Supply chain attack via compromised npm package in POS system update. Malicious code exfiltrated payment card tokens from 12 retail locations. PCI forensic investigation underway.",
        "date_of_loss": "2026-01-05",
        "reported_by": "David Chen, CTO",
    },
    {
        "pol_index": 7,
        "claim_type": "other",
        "description": "Business email compromise targeting accounts payable. Fraudulent invoices totaling $45,000 paid to attacker-controlled accounts before detection by internal audit.",
        "date_of_loss": "2025-12-20",
        "reported_by": "Maria Santos, Controller",
    },
]


def main() -> None:
    print(f"{'=' * 60}")
    print(f"  OpenInsure Data Seed — {BASE_URL}")
    print(f"{'=' * 60}")

    # Quick health check
    try:
        r = client.get("/health")
        print(f"\nHealth check: {r.status_code}")
    except Exception as e:
        print(f"\nWARN: Health check failed ({e}), continuing anyway...")

    # ── Step 1: Submissions ──────────────────────────────────────────────
    print(f"\n{'─' * 40}")
    print(f"  Creating {len(SUBMISSIONS)} submissions...")
    print(f"{'─' * 40}")
    sub_ids: list[str] = []
    for s in SUBMISSIONS:
        result = create("submissions", s)
        if result:
            sid = result.get("id", "")
            sub_ids.append(sid)
            stats["submissions"] += 1
            print(f"  + {s['applicant_name']:<35} id={sid[:8]}...")
        else:
            sub_ids.append("")

    # ── Step 2: Policies ─────────────────────────────────────────────────
    print(f"\n{'─' * 40}")
    print(f"  Creating {len(POLICY_TEMPLATES)} policies...")
    print(f"{'─' * 40}")
    pol_ids: list[str] = []
    for pt in POLICY_TEMPLATES:
        idx = pt["sub_index"]
        submission_id = sub_ids[idx] if idx < len(sub_ids) else ""
        if not submission_id:
            print(f"  SKIP {pt['policyholder_name']} — no submission ID")
            pol_ids.append("")
            continue

        payload = {
            "submission_id": submission_id,
            "product_id": pt["product_id"],
            "policyholder_name": pt["policyholder_name"],
            "effective_date": pt["effective_date"],
            "expiration_date": pt["expiration_date"],
            "premium": pt["premium"],
            "coverages": pt.get("coverages", []),
        }
        result = create("policies", payload)
        if result:
            pid = result.get("id", "")
            pol_ids.append(pid)
            stats["policies"] += 1
            pnum = result.get("policy_number", "?")
            print(f"  + {pnum:<18} {pt['policyholder_name']:<30} ${pt['premium']:>10,.0f}")
        else:
            pol_ids.append("")

    # ── Step 3: Claims ───────────────────────────────────────────────────
    print(f"\n{'─' * 40}")
    print(f"  Creating {len(CLAIM_TEMPLATES)} claims...")
    print(f"{'─' * 40}")
    for ct in CLAIM_TEMPLATES:
        idx = ct["pol_index"]
        policy_id = pol_ids[idx] if idx < len(pol_ids) else ""
        if not policy_id:
            print(f"  SKIP claim (pol_index={idx}) — no policy ID")
            continue

        payload = {
            "policy_id": policy_id,
            "claim_type": ct["claim_type"],
            "description": ct["description"],
            "date_of_loss": ct["date_of_loss"],
            "reported_by": ct["reported_by"],
        }
        result = create("claims", payload)
        if result:
            stats["claims"] += 1
            cnum = result.get("claim_number", "?")
            print(f"  + {cnum:<18} {ct['claim_type']:<25} {ct['description'][:45]}...")

    # ── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  SEED COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Submissions created: {stats['submissions']}")
    print(f"  Policies created:    {stats['policies']}")
    print(f"  Claims created:      {stats['claims']}")
    print(f"  Errors:              {stats['errors']}")

    # Verify counts via API
    print("\n  Verifying via API...")
    for entity in ("submissions", "policies", "claims"):
        try:
            r = client.get(f"/api/v1/{entity}")
            body = r.json()
            total = body.get("total", len(body.get("items", [])))
            print(f"    {entity:>12}: {total} total in database")
        except Exception as e:
            print(f"    {entity:>12}: verify failed ({e})")

    print()


if __name__ == "__main__":
    main()
