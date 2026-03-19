"""Generate 20 diverse Foundry agent traces for observability testing.

Creates submissions with varied risk profiles, then runs them through
triage (submission agent), quote (underwriting agent), bind (policy agent),
claims assessment (claims agent), and compliance checks.
This touches all 6 Foundry agents to produce rich traces.
"""

import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timezone

import httpx

BASE_URL = "https://openinsure-backend.braveriver-f92a9f28.swedencentral.azurecontainerapps.io"
API = f"{BASE_URL}/api/v1"
HEADERS = {"X-API-Key": "dev-key-change-me", "Content-Type": "application/json"}

# 20 diverse cyber insurance scenarios
SCENARIOS = [
    {"name": "TechStart AI Inc", "revenue": 2_500_000, "employees": 45, "industry": "SaaS/AI", "sic": "7372", "security_score": 8, "incidents": 0},
    {"name": "MidWest Manufacturing", "revenue": 15_000_000, "employees": 320, "industry": "Manufacturing", "sic": "3599", "security_score": 4, "incidents": 2},
    {"name": "Pacific Financial Group", "revenue": 50_000_000, "employees": 180, "industry": "Financial Services", "sic": "6022", "security_score": 7, "incidents": 1},
    {"name": "HealthFirst Clinics", "revenue": 8_000_000, "employees": 95, "industry": "Healthcare", "sic": "8011", "security_score": 5, "incidents": 3},
    {"name": "GreenEnergy Solutions", "revenue": 12_000_000, "employees": 75, "industry": "Energy", "sic": "4911", "security_score": 6, "incidents": 0},
    {"name": "Urban Retail Chain", "revenue": 35_000_000, "employees": 500, "industry": "Retail", "sic": "5411", "security_score": 3, "incidents": 4},
    {"name": "CloudSecure Labs", "revenue": 5_000_000, "employees": 30, "industry": "Cybersecurity", "sic": "7371", "security_score": 9, "incidents": 0},
    {"name": "Alpha Legal Partners", "revenue": 20_000_000, "employees": 60, "industry": "Legal", "sic": "8111", "security_score": 6, "incidents": 1},
    {"name": "EduTech Academy", "revenue": 3_000_000, "employees": 40, "industry": "Education", "sic": "8211", "security_score": 5, "incidents": 0},
    {"name": "FastLogistics Corp", "revenue": 28_000_000, "employees": 250, "industry": "Logistics", "sic": "4215", "security_score": 4, "incidents": 2},
    {"name": "BioPharm Research", "revenue": 45_000_000, "employees": 200, "industry": "Pharma", "sic": "2836", "security_score": 7, "incidents": 1},
    {"name": "Metro Construction Inc", "revenue": 18_000_000, "employees": 150, "industry": "Construction", "sic": "1522", "security_score": 3, "incidents": 3},
    {"name": "Digital Media House", "revenue": 7_000_000, "employees": 55, "industry": "Media", "sic": "7812", "security_score": 6, "incidents": 0},
    {"name": "Precision Aerospace", "revenue": 60_000_000, "employees": 400, "industry": "Aerospace", "sic": "3721", "security_score": 8, "incidents": 1},
    {"name": "FoodChain Distributors", "revenue": 22_000_000, "employees": 180, "industry": "Food Distribution", "sic": "5141", "security_score": 4, "incidents": 2},
    {"name": "NanoTech Innovations", "revenue": 4_000_000, "employees": 25, "industry": "Nanotechnology", "sic": "3674", "security_score": 7, "incidents": 0},
    {"name": "Coastal Hospitality Group", "revenue": 30_000_000, "employees": 350, "industry": "Hospitality", "sic": "7011", "security_score": 5, "incidents": 3},
    {"name": "AutoDrive Systems", "revenue": 40_000_000, "employees": 280, "industry": "Automotive Tech", "sic": "3714", "security_score": 8, "incidents": 0},
    {"name": "QuickPay Fintech", "revenue": 10_000_000, "employees": 65, "industry": "Fintech", "sic": "6159", "security_score": 9, "incidents": 1},
    {"name": "Heritage Insurance Brokers", "revenue": 6_000_000, "employees": 35, "industry": "Insurance Brokerage", "sic": "6411", "security_score": 6, "incidents": 0},
]


async def create_submission(client: httpx.AsyncClient, scenario: dict, idx: int) -> str | None:
    """Create a submission and return its ID."""
    payload = {
        "applicant_name": scenario["name"],
        "line_of_business": "cyber",
        "effective_date": "2025-07-01",
        "expiration_date": "2026-07-01",
        "cyber_risk_data": {
            "annual_revenue": scenario["revenue"],
            "employee_count": scenario["employees"],
            "industry": scenario["industry"],
            "sic_code": scenario["sic"],
            "security_maturity_score": scenario["security_score"],
            "prior_incidents": scenario["incidents"],
            "has_mfa": scenario["security_score"] >= 6,
            "has_endpoint_protection": scenario["security_score"] >= 5,
            "has_backup_strategy": scenario["security_score"] >= 4,
            "pci_compliant": scenario["industry"] in ("Retail", "Fintech", "Financial Services"),
            "hipaa_compliant": scenario["industry"] == "Healthcare",
        },
    }
    try:
        resp = await client.post(f"{API}/submissions", json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            sid = data.get("id") or data.get("submission_id")
            print(f"  [{idx+1:2d}/20] ✅ Created submission for {scenario['name']}: {sid}")
            return sid
        else:
            print(f"  [{idx+1:2d}/20] ❌ Create failed ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"  [{idx+1:2d}/20] ❌ Create error: {e}")
        return None


async def run_triage(client: httpx.AsyncClient, sid: str, name: str) -> bool:
    """Triage → invokes openinsure-submission agent."""
    try:
        resp = await client.post(f"{API}/submissions/{sid}/triage", timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            score = data.get("risk_score", "?")
            rec = data.get("recommendation", "?")
            print(f"       🔍 Triage {name}: score={score}, rec={rec}")
            return True
        print(f"       ⚠️  Triage {name}: {resp.status_code} - {resp.text[:150]}")
        return resp.status_code in (200, 409)  # 409 = already triaged
    except Exception as e:
        print(f"       ❌ Triage {name}: {e}")
        return False


async def run_quote(client: httpx.AsyncClient, sid: str, name: str) -> bool:
    """Quote → invokes openinsure-underwriting agent."""
    try:
        resp = await client.post(f"{API}/submissions/{sid}/quote", timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            premium = data.get("premium", "?")
            print(f"       💰 Quote {name}: premium=${premium}")
            return True
        elif resp.status_code == 202:
            print(f"       ⬆️  Quote {name}: escalated (authority limit)")
            return True  # Escalation is a valid Foundry-touched path
        print(f"       ⚠️  Quote {name}: {resp.status_code} - {resp.text[:150]}")
        return False
    except Exception as e:
        print(f"       ❌ Quote {name}: {e}")
        return False


async def run_bind(client: httpx.AsyncClient, sid: str, name: str) -> str | None:
    """Bind → invokes openinsure-policy agent, creates policy."""
    try:
        resp = await client.post(f"{API}/submissions/{sid}/bind", timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            pid = data.get("policy_id", "?")
            print(f"       📋 Bind {name}: policy={pid}")
            return pid
        elif resp.status_code == 202:
            print(f"       ⬆️  Bind {name}: escalated")
            return None
        print(f"       ⚠️  Bind {name}: {resp.status_code} - {resp.text[:150]}")
        return None
    except Exception as e:
        print(f"       ❌ Bind {name}: {e}")
        return None


async def run_process_workflow(client: httpx.AsyncClient, sid: str, name: str) -> bool:
    """Full workflow → invokes submission + underwriting + policy agents sequentially."""
    try:
        resp = await client.post(f"{API}/submissions/{sid}/process", timeout=180)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "?")
            print(f"       🔄 Workflow {name}: status={status}")
            return True
        print(f"       ⚠️  Workflow {name}: {resp.status_code} - {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"       ❌ Workflow {name}: {e}")
        return False


async def create_and_assess_claim(client: httpx.AsyncClient, policy_id: str, name: str, idx: int) -> bool:
    """Create a claim and set reserve → invokes openinsure-claims agent."""
    claim_type = random.choice(["data_breach", "ransomware", "business_interruption", "social_engineering"])
    payload = {
        "policy_id": policy_id,
        "claim_type": claim_type,
        "date_of_loss": "2025-06-15",
        "reported_by": f"Risk Manager at {name}",
        "contact_email": f"claims@{name.lower().replace(' ', '')}.com",
        "description": f"Cyber incident at {name} - {random.choice(['unauthorized access to customer DB', 'ransomware encryption of file servers', 'phishing attack on finance team', 'DDoS attack on e-commerce platform'])}",
        "metadata": {"source": "trace_generator", "severity": random.choice(["low", "medium", "high", "critical"])},
    }
    try:
        resp = await client.post(f"{API}/claims", json=payload, timeout=60)
        if resp.status_code in (200, 201):
            data = resp.json()
            cid = data.get("id") or data.get("claim_id")
            print(f"       🏥 Claim [{idx}] {name}: {cid}")

            # Set reserve → triggers claims Foundry agent
            reserve_payload = {
                "category": "indemnity",
                "amount": random.randint(10000, 200000),
                "currency": "USD",
                "notes": f"Initial reserve for {name} cyber incident",
            }
            resp2 = await client.post(f"{API}/claims/{cid}/reserves", json=reserve_payload, timeout=120)
            if resp2.status_code == 200:
                print(f"       💵 Reserve set for claim {cid}")
            else:
                print(f"       ⚠️  Reserve {cid}: {resp2.status_code}")
            return True
        print(f"       ⚠️  Claim create {name}: {resp.status_code} - {resp.text[:150]}")
        return False
    except Exception as e:
        print(f"       ❌ Claim {name}: {e}")
        return False


async def main():
    print("=" * 70)
    print("🚀 OpenInsure Foundry Agent Trace Generator")
    print(f"   Target: {BASE_URL}")
    print(f"   Scenarios: {len(SCENARIOS)}")
    print("=" * 70)

    # Check backend health
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        try:
            health = await client.get(f"{BASE_URL}/health")
            print(f"\n✅ Backend health: {health.status_code}")
        except Exception as e:
            print(f"\n❌ Backend unreachable: {e}")
            sys.exit(1)

    stats = {"created": 0, "triaged": 0, "quoted": 0, "bound": 0, "workflows": 0, "claims": 0}
    submission_ids: list[tuple[str, str]] = []  # (id, name)
    policy_ids: list[tuple[str, str]] = []  # (id, name)

    async with httpx.AsyncClient(headers=HEADERS, timeout=180) as client:
        # --- Phase 1: Create 20 submissions ---
        print("\n📝 Phase 1: Creating 20 submissions...")
        for i, scenario in enumerate(SCENARIOS):
            sid = await create_submission(client, scenario, i)
            if sid:
                submission_ids.append((sid, scenario["name"]))
                stats["created"] += 1
            await asyncio.sleep(0.3)

        # --- Phase 2: Triage first 10 (submission agent) + full workflow last 10 ---
        print(f"\n🔍 Phase 2: Triage + Quote + Bind (first 10 — sequential agent calls)...")
        for sid, name in submission_ids[:10]:
            ok = await run_triage(client, sid, name)
            if ok:
                stats["triaged"] += 1
            await asyncio.sleep(0.5)

            ok = await run_quote(client, sid, name)
            if ok:
                stats["quoted"] += 1
            await asyncio.sleep(0.5)

            pid = await run_bind(client, sid, name)
            if pid:
                stats["bound"] += 1
                policy_ids.append((pid, name))
            await asyncio.sleep(0.5)

        print(f"\n🔄 Phase 3: Full multi-agent workflows (last 10 — orchestrator + all agents)...")
        for sid, name in submission_ids[10:]:
            ok = await run_process_workflow(client, sid, name)
            if ok:
                stats["workflows"] += 1
            await asyncio.sleep(1)

        # --- Phase 4: Claims on bound policies (claims agent) ---
        print(f"\n🏥 Phase 4: Claims assessment (on {len(policy_ids)} bound policies)...")
        for i, (pid, name) in enumerate(policy_ids[:5]):
            ok = await create_and_assess_claim(client, pid, name, i + 1)
            if ok:
                stats["claims"] += 1
            await asyncio.sleep(0.5)

    # --- Summary ---
    print("\n" + "=" * 70)
    print("📊 Trace Generation Summary")
    print("=" * 70)
    print(f"  Submissions created:   {stats['created']:3d} / 20")
    print(f"  Triaged (submission):  {stats['triaged']:3d} / 10  → openinsure-submission agent")
    print(f"  Quoted (underwriting): {stats['quoted']:3d} / 10  → openinsure-underwriting agent")
    print(f"  Bound (policy):        {stats['bound']:3d} / 10  → openinsure-policy agent")
    print(f"  Workflows (all agents):{stats['workflows']:3d} / 10  → orchestrator + all 3")
    print(f"  Claims assessed:       {stats['claims']:3d} / 5   → openinsure-claims agent")
    total = stats["triaged"] + stats["quoted"] + stats["bound"] + stats["workflows"] * 3 + stats["claims"]
    print(f"\n  Total Foundry agent invocations: ~{total}")
    print("\n💡 Check traces in Azure AI Foundry → Tracing → Recent traces")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
