"""Post-deploy smoke test for Foundry agent connectivity.

Run after every deploy to verify agents are being invoked (not falling back).
Exit code 0 = all good, 1 = Foundry fallback detected.

Usage: python scripts/foundry_smoke_test.py [backend_url]
"""

import os
import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "OPENINSURE_BACKEND_URL", "http://localhost:8000"
)
API = f"{BASE}/api/v1"
H = {"X-API-Key": "openinsure-dev-key-2024", "Content-Type": "application/json"}

TEST_SUBMISSION = {
    "applicant_name": "Foundry Smoke Test Corp",
    "line_of_business": "cyber",
    "cyber_risk_data": {
        "annual_revenue": 5000000,
        "employee_count": 50,
        "industry": "technology",
        "security_maturity_score": 7,
        "prior_incidents": 0,
        "has_mfa": True,
        "has_endpoint_protection": True,
        "has_backup_strategy": True,
        "has_incident_response_plan": True,
    },
}


def main() -> int:
    print(f"🔍 Foundry Smoke Test — {BASE}")
    print("=" * 50)

    # 1. Health check
    try:
        r = httpx.get(f"{BASE}/health", timeout=10)
        if r.status_code != 200:
            print(f"❌ Backend unhealthy: {r.status_code}")
            return 1
        print("✅ Backend healthy")
    except Exception as e:
        print(f"❌ Cannot reach backend: {e}")
        return 1

    # 2. Create test submission
    print("\n📋 Creating test submission...")
    try:
        r = httpx.post(f"{API}/submissions", json=TEST_SUBMISSION, headers=H, timeout=30)
        if r.status_code not in (200, 201):
            print(f"❌ Create failed: {r.status_code} {r.text[:200]}")
            return 1
        data = r.json()
        sid = data.get("id") or data.get("submission_id")
        print(f"   Created: {sid}")
    except Exception as e:
        print(f"❌ Create error: {e}")
        return 1

    # 3. Triage — check for local_fallback
    print("\n🔍 Triaging (checking Foundry connectivity)...")
    try:
        r = httpx.post(f"{API}/submissions/{sid}/triage", headers=H, timeout=120)
        if r.status_code != 200:
            print(f"❌ Triage failed: {r.status_code} {r.text[:300]}")
            return 1
        triage = r.json()
        flags = triage.get("flags", [])
        risk_score = triage.get("risk_score")
        recommendation = triage.get("recommendation")

        print(f"   Risk score: {risk_score}")
        print(f"   Recommendation: {recommendation}")
        print(f"   Flags: {flags}")

        flags_str = " ".join(str(f) for f in flags)
        if "local_fallback" in flags_str:
            print("\n❌ FOUNDRY FALLBACK DETECTED!")
            print("   The triage agent is using local_fallback instead of Foundry.")
            print("   This means Foundry agents are NOT being invoked.")
            print("   Check: FOUNDRY_PROJECT_ENDPOINT env var, Azure credentials,")
            print("   agent deployment status in Azure AI Foundry portal.")
            return 1

        print("   ✅ No local_fallback — Foundry agent responded")
    except Exception as e:
        print(f"❌ Triage error: {e}")
        return 1

    # 4. Quote — verify rating engine works
    print("\n💰 Generating quote...")
    try:
        r = httpx.post(f"{API}/submissions/{sid}/quote", headers=H, timeout=120)
        if r.status_code in (200, 202):
            quote = r.json()
            premium = quote.get("premium")
            print(f"   Premium: ${premium}")
            print("   ✅ Quote generated successfully")
        else:
            print(f"   ⚠️ Quote returned {r.status_code} (may be expected for referrals)")
    except Exception as e:
        print(f"   ⚠️ Quote error: {e}")

    print("\n" + "=" * 50)
    print("✅ FOUNDRY SMOKE TEST PASSED — agents are responding")
    return 0


if __name__ == "__main__":
    sys.exit(main())
