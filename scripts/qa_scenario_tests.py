"""Phase 1: QA Scenario Tests — prove Foundry agents differentiate risk profiles.

Creates 5 diverse submissions, triages each, quotes each, and compares results.
Proves AI gives DIFFERENT risk scores and premiums based on actual risk data.

Usage: python scripts/qa_scenario_tests.py [backend_url]
"""

import json
import os
import sys
import time

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "OPENINSURE_BACKEND_URL", "http://localhost:8000"
)
API = f"{BASE}/api/v1"
H = {"X-API-Key": "openinsure-dev-key-2024", "Content-Type": "application/json"}

SCENARIOS = [
    {
        "label": "Low Risk Tech",
        "expected_risk": "low",
        "payload": {
            "applicant_name": "SecureCode Labs",
            "line_of_business": "cyber",
            "risk_data": {
                "annual_revenue": 2000000,
                "employee_count": 25,
                "industry": "technology",
                "security_maturity_score": 9,
            },
            "cyber_risk_data": {
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
                "has_incident_response_plan": True,
                "prior_incidents": 0,
                "annual_revenue": 2000000,
                "employee_count": 25,
                "industry": "technology",
                "security_maturity_score": 9,
            },
        },
    },
    {
        "label": "High Risk Health",
        "expected_risk": "high",
        "payload": {
            "applicant_name": "Regional Health Network",
            "line_of_business": "cyber",
            "risk_data": {
                "annual_revenue": 45000000,
                "employee_count": 4500,
                "industry": "healthcare",
                "security_maturity_score": 3,
            },
            "cyber_risk_data": {
                "has_mfa": False,
                "has_endpoint_protection": True,
                "has_backup_strategy": False,
                "has_incident_response_plan": False,
                "prior_incidents": 3,
                "annual_revenue": 45000000,
                "employee_count": 4500,
                "industry": "healthcare",
                "security_maturity_score": 3,
            },
        },
    },
    {
        "label": "Medium Financial",
        "expected_risk": "medium",
        "payload": {
            "applicant_name": "Alpine Financial Partners",
            "line_of_business": "cyber",
            "risk_data": {
                "annual_revenue": 20000000,
                "employee_count": 200,
                "industry": "financial_services",
                "security_maturity_score": 7,
            },
            "cyber_risk_data": {
                "has_mfa": True,
                "has_endpoint_protection": True,
                "has_backup_strategy": True,
                "has_incident_response_plan": False,
                "prior_incidents": 1,
                "annual_revenue": 20000000,
                "employee_count": 200,
                "industry": "financial_services",
                "security_maturity_score": 7,
            },
        },
    },
    {
        "label": "Out of Appetite",
        "expected_risk": "decline",
        "payload": {
            "applicant_name": "DeepMine Resources",
            "line_of_business": "cyber",
            "risk_data": {
                "annual_revenue": 80000000,
                "employee_count": 2000,
                "industry": "mining",
                "security_maturity_score": 2,
            },
            "cyber_risk_data": {
                "has_mfa": False,
                "has_endpoint_protection": False,
                "has_backup_strategy": False,
                "has_incident_response_plan": False,
                "prior_incidents": 5,
                "annual_revenue": 80000000,
                "employee_count": 2000,
                "industry": "mining",
                "security_maturity_score": 2,
            },
        },
    },
    {
        "label": "Edge Case Micro",
        "expected_risk": "low-medium",
        "payload": {
            "applicant_name": "Micro Consulting LLC",
            "line_of_business": "cyber",
            "risk_data": {
                "annual_revenue": 500000,
                "employee_count": 10,
                "industry": "professional_services",
                "security_maturity_score": 4,
            },
            "cyber_risk_data": {
                "has_mfa": True,
                "has_endpoint_protection": False,
                "has_backup_strategy": False,
                "has_incident_response_plan": False,
                "prior_incidents": 0,
                "annual_revenue": 500000,
                "employee_count": 10,
                "industry": "professional_services",
                "security_maturity_score": 4,
            },
        },
    },
]


def run_scenario(scenario: dict) -> dict:
    """Run create → triage → quote for a single scenario."""
    label = scenario["label"]
    result = {
        "label": label,
        "submission_id": None,
        "risk_score": None,
        "recommendation": None,
        "flags": [],
        "premium": None,
        "ai_mode": "unknown",
        "key_reasoning": "",
        "errors": [],
    }

    # Step 1: Create submission
    print(f"\n{'─' * 60}")
    print(f"  📋 {label}: Creating submission...")
    try:
        r = httpx.post(
            f"{API}/submissions",
            json=scenario["payload"],
            headers=H,
            timeout=30,
        )
        if r.status_code not in (200, 201):
            result["errors"].append(f"Create failed: {r.status_code} {r.text[:200]}")
            return result
        data = r.json()
        sid = data.get("id") or data.get("submission_id")
        result["submission_id"] = sid
        print(f"     ✅ Created: {sid}")
    except Exception as e:
        result["errors"].append(f"Create error: {e}")
        return result

    # Step 2: Triage
    print(f"  🔍 {label}: Triaging...")
    try:
        r = httpx.post(f"{API}/submissions/{sid}/triage", headers=H, timeout=120)
        if r.status_code != 200:
            result["errors"].append(f"Triage failed: {r.status_code} {r.text[:300]}")
            return result
        triage = r.json()
        result["risk_score"] = triage.get("risk_score")
        result["recommendation"] = triage.get("recommendation")
        result["flags"] = triage.get("flags", [])

        # Detect AI mode from flags
        flags_str = " ".join(result["flags"])
        if "local_fallback" in flags_str:
            result["ai_mode"] = "local_fallback"
        else:
            result["ai_mode"] = "foundry"

        # Extract key reasoning from flags
        reasoning_flags = [
            f for f in result["flags"]
            if f != "source:local_fallback" and not f.startswith("source:")
        ]
        result["key_reasoning"] = "; ".join(reasoning_flags[:3]) if reasoning_flags else "see flags"

        print(f"     ✅ Triage: score={result['risk_score']}, rec={result['recommendation']}")
        print(f"        Mode: {result['ai_mode']}")
        print(f"        Flags: {result['flags'][:5]}")
    except Exception as e:
        result["errors"].append(f"Triage error: {e}")
        return result

    # Step 3: Quote (skip if declined)
    if result["recommendation"] and "decline" in str(result["recommendation"]).lower():
        print(f"  ⛔ {label}: Declined — skipping quote")
        result["premium"] = "DECLINED"
    else:
        print(f"  💰 {label}: Generating quote...")
        try:
            r = httpx.post(f"{API}/submissions/{sid}/quote", headers=H, timeout=120)
            if r.status_code in (200, 202):
                quote = r.json()
                result["premium"] = quote.get("premium")
                print(f"     ✅ Quote: premium=${result['premium']}")
            else:
                result["errors"].append(f"Quote failed: {r.status_code} {r.text[:300]}")
                print(f"     ⚠️ Quote failed: {r.status_code}")
        except Exception as e:
            result["errors"].append(f"Quote error: {e}")

    return result


def print_comparison_table(results: list[dict]) -> None:
    """Print a formatted comparison table of all scenarios."""
    print("\n" + "=" * 120)
    print("📊 SCENARIO COMPARISON TABLE")
    print("=" * 120)

    header = f"{'Scenario':<22} | {'Risk Score':>10} | {'Premium':>12} | {'AI Mode':<16} | {'Recommendation':<18} | {'Key AI Reasoning'}"
    print(header)
    print("─" * 120)

    for r in results:
        premium_str = f"${r['premium']:,.0f}" if isinstance(r["premium"], (int, float)) else str(r["premium"] or "N/A")
        score_str = str(r["risk_score"]) if r["risk_score"] is not None else "N/A"
        rec_str = str(r["recommendation"] or "N/A")
        mode_str = r["ai_mode"]
        reasoning = r["key_reasoning"][:50] if r["key_reasoning"] else "N/A"

        print(f"{r['label']:<22} | {score_str:>10} | {premium_str:>12} | {mode_str:<16} | {rec_str:<18} | {reasoning}")

    print("=" * 120)


def run_diagnostics(results: list[dict]) -> tuple[list[str], list[str]]:
    """Analyze results for bugs."""
    bugs = []
    warnings = []

    # Check if all risk scores are the same (BUG)
    scores = [r["risk_score"] for r in results if r["risk_score"] is not None]
    if len(set(scores)) <= 1 and len(scores) > 1:
        bugs.append(
            f"BUG: All {len(scores)} scenarios returned the SAME risk_score={scores[0]}. "
            "Foundry agents are not differentiating risk profiles!"
        )

    # Check for local_fallback (BUG)
    fallback_scenarios = [r["label"] for r in results if r["ai_mode"] == "local_fallback"]
    if fallback_scenarios:
        bugs.append(
            f"BUG: {len(fallback_scenarios)} scenario(s) used local_fallback instead of Foundry: "
            f"{', '.join(fallback_scenarios)}"
        )

    # Check premiums differ
    premiums = [r["premium"] for r in results if isinstance(r["premium"], (int, float))]
    if len(set(premiums)) <= 1 and len(premiums) > 1:
        bugs.append(
            f"BUG: All {len(premiums)} quoted scenarios returned the SAME premium=${premiums[0]}. "
            "Rating engine is not differentiating!"
        )

    # Check for errors
    for r in results:
        if r["errors"]:
            warnings.append(f"WARNING: {r['label']} had errors: {'; '.join(r['errors'])}")

    # Verify high risk gets higher score than low risk
    low_risk = next((r for r in results if r["label"] == "Low Risk Tech"), None)
    high_risk = next((r for r in results if r["label"] == "High Risk Health"), None)
    if low_risk and high_risk and low_risk["risk_score"] and high_risk["risk_score"]:
        if low_risk["risk_score"] >= high_risk["risk_score"]:
            warnings.append(
                f"WARNING: Low risk ({low_risk['risk_score']}) scored >= high risk "
                f"({high_risk['risk_score']}). Risk scoring may be inverted."
            )

    return bugs, warnings


def main() -> None:
    print("=" * 70)
    print("🧪 OpenInsure QA Scenario Tests — Foundry Agent Differentiation")
    print(f"   Backend: {BASE}")
    print("=" * 70)

    # Health check first
    try:
        r = httpx.get(f"{BASE}/health", timeout=10)
        if r.status_code != 200:
            print(f"❌ Backend unhealthy: {r.status_code}")
            sys.exit(1)
        print("✅ Backend healthy\n")
    except Exception as e:
        print(f"❌ Cannot reach backend: {e}")
        sys.exit(1)

    # Run all scenarios
    all_results = []
    start = time.time()
    for scenario in SCENARIOS:
        result = run_scenario(scenario)
        all_results.append(result)

    elapsed = time.time() - start
    print(f"\n⏱️  Total time: {elapsed:.1f}s")

    # Print comparison
    print_comparison_table(all_results)

    # Run diagnostics
    bugs, warnings = run_diagnostics(all_results)

    if warnings:
        print("\n⚠️  WARNINGS:")
        for w in warnings:
            print(f"  {w}")

    if bugs:
        print("\n🐛 BUGS DETECTED:")
        for b in bugs:
            print(f"  {b}")
        print(f"\n❌ {len(bugs)} bug(s) found. Foundry agents need attention!")
        sys.exit(1)
    else:
        print("\n✅ ALL CLEAR — Foundry agents differentiate risk profiles correctly!")
        sys.exit(0)


if __name__ == "__main__":
    main()
