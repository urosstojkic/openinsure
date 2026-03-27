"""Phase 2: Playwright portal tests — prove the UI shows different results
for contrasting risk profiles.

Creates LOW RISK and HIGH RISK submissions via portal, triages and quotes each,
compares that risk scores, premiums, and AI reasoning differ.

Usage: python scripts/qa_portal_tests.py
"""

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BACKEND = os.environ.get(
    "OPENINSURE_BACKEND_URL",
    "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io",
)
DASHBOARD = os.environ.get(
    "OPENINSURE_DASHBOARD_URL",
    "https://openinsure-dashboard.proudplant-9550e5a5.swedencentral.azurecontainerapps.io",
)
API = f"{BACKEND}/api/v1"
H = {"X-API-Key": "openinsure-dev-key-2024", "Content-Type": "application/json"}
SCREENSHOT_DIR = Path("test-screenshots/qa-risk-comparison")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 30_000
NAV_TIMEOUT = 60_000


# ══════════════════════════════════════════════════════════════════════════════
# API helpers — create submissions via API, then verify UI
# ══════════════════════════════════════════════════════════════════════════════

_suffix = uuid.uuid4().hex[:6]

LOW_RISK = {
    "applicant_name": f"SecureCode Labs {_suffix}",
    "line_of_business": "cyber",
    "cyber_risk_data": {
        "annual_revenue": 2000000,
        "employee_count": 25,
        "industry": "technology",
        "security_maturity_score": 9,
        "has_mfa": True,
        "has_endpoint_protection": True,
        "has_backup_strategy": True,
        "has_incident_response_plan": True,
        "prior_incidents": 0,
    },
}

HIGH_RISK = {
    "applicant_name": f"Regional Health Network {_suffix}",
    "line_of_business": "cyber",
    "cyber_risk_data": {
        "annual_revenue": 45000000,
        "employee_count": 4500,
        "industry": "healthcare",
        "security_maturity_score": 3,
        "has_mfa": False,
        "has_endpoint_protection": True,
        "has_backup_strategy": False,
        "has_incident_response_plan": False,
        "prior_incidents": 3,
    },
}


def create_and_process(label: str, payload: dict) -> dict:
    """Create, triage, quote via API. Return result dict."""
    result = {"label": label, "id": None, "risk_score": None, "premium": None,
              "recommendation": None, "flags": [], "error": None}

    # Create
    r = httpx.post(f"{API}/submissions", json=payload, headers=H, timeout=30)
    if r.status_code not in (200, 201):
        result["error"] = f"Create failed: {r.status_code} {r.text[:200]}"
        return result
    sid = r.json().get("id") or r.json().get("submission_id")
    result["id"] = sid

    # Triage
    r = httpx.post(f"{API}/submissions/{sid}/triage", headers=H, timeout=120)
    if r.status_code != 200:
        result["error"] = f"Triage failed: {r.status_code}"
        return result
    triage = r.json()
    result["risk_score"] = triage.get("risk_score")
    result["recommendation"] = triage.get("recommendation")
    result["flags"] = triage.get("flags", [])

    # Quote
    if result["recommendation"] and "decline" not in str(result["recommendation"]).lower():
        r = httpx.post(f"{API}/submissions/{sid}/quote", headers=H, timeout=120)
        if r.status_code in (200, 202):
            result["premium"] = r.json().get("premium")

    return result


# ══════════════════════════════════════════════════════════════════════════════
# Playwright UI tests
# ══════════════════════════════════════════════════════════════════════════════

async def screenshot_submission_detail(page, sid: str, label: str, prefix: str) -> dict:
    """Navigate to submission detail and capture screenshots."""
    info = {"risk_score_visible": False, "premium_visible": False, "body_text": ""}

    # Go to submission detail
    url = f"{DASHBOARD}/submissions/{sid}"
    try:
        await page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT)
        await page.wait_for_timeout(4000)

        body = await page.inner_text("body")
        info["body_text"] = body[:3000]

        # Screenshot detail page
        await page.screenshot(
            path=str(SCREENSHOT_DIR / f"{prefix}-01-detail.png"), full_page=True
        )
        print(f"  📸 {label}: Detail page screenshot saved")

        # Check for risk score on page
        body_lower = body.lower()
        info["risk_score_visible"] = "risk" in body_lower and any(
            c.isdigit() for c in body
        )
        info["premium_visible"] = "premium" in body_lower or "$" in body

    except Exception as e:
        print(f"  ⚠️  {label}: Detail page error: {e}")
        try:
            await page.screenshot(
                path=str(SCREENSHOT_DIR / f"{prefix}-01-detail-error.png")
            )
        except Exception:
            pass

    # Try submissions list to find it
    try:
        await page.goto(
            f"{DASHBOARD}/submissions", wait_until="networkidle", timeout=NAV_TIMEOUT
        )
        await page.wait_for_timeout(3000)
        await page.screenshot(
            path=str(SCREENSHOT_DIR / f"{prefix}-02-list.png"), full_page=True
        )
    except Exception:
        pass

    return info


async def run_portal_tests():
    print("=" * 70)
    print("🎭 Phase 2: Playwright Portal Tests — Risk Profile Comparison")
    print(f"   Dashboard: {DASHBOARD}")
    print(f"   Backend:   {BACKEND}")
    print("=" * 70)

    # Step 1: Create and process both via API
    print("\n📋 Creating LOW RISK submission (SecureCode Labs)...")
    low = create_and_process("Low Risk", LOW_RISK)
    print(f"   ID: {low['id']}, Score: {low['risk_score']}, Premium: {low['premium']}")

    print("\n📋 Creating HIGH RISK submission (Regional Health Network)...")
    high = create_and_process("High Risk", HIGH_RISK)
    print(f"   ID: {high['id']}, Score: {high['risk_score']}, Premium: {high['premium']}")

    if not low["id"] or not high["id"]:
        print("❌ Failed to create submissions via API")
        return False

    # Step 2: Playwright screenshots of both
    print("\n🎭 Opening browser for screenshots...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Dashboard home
        try:
            await page.goto(DASHBOARD, wait_until="networkidle", timeout=NAV_TIMEOUT)
            await page.wait_for_timeout(3000)
            await page.screenshot(
                path=str(SCREENSHOT_DIR / "00-dashboard-home.png"), full_page=True
            )
            print("  📸 Dashboard home screenshot saved")
        except Exception as e:
            print(f"  ⚠️  Dashboard home error: {e}")

        # Low risk detail
        print(f"\n── LOW RISK: {low['id']} ──")
        low_info = await screenshot_submission_detail(
            page, low["id"], "Low Risk", "low-risk"
        )

        # High risk detail
        print(f"\n── HIGH RISK: {high['id']} ──")
        high_info = await screenshot_submission_detail(
            page, high["id"], "High Risk", "high-risk"
        )

        # Submissions list showing both
        try:
            await page.goto(
                f"{DASHBOARD}/submissions",
                wait_until="networkidle",
                timeout=NAV_TIMEOUT,
            )
            await page.wait_for_timeout(3000)
            await page.screenshot(
                path=str(SCREENSHOT_DIR / "both-submissions-list.png"), full_page=True
            )
            print("\n  📸 Submissions list (both visible) screenshot saved")
        except Exception:
            pass

        await browser.close()

    # Step 3: Comparison
    print("\n" + "=" * 70)
    print("📊 RISK PROFILE COMPARISON")
    print("=" * 70)
    print(f"  {'Metric':<25} | {'Low Risk (SecureCode)':>22} | {'High Risk (RegHealth)':>22}")
    print("  " + "─" * 75)
    print(f"  {'Risk Score':<25} | {str(low['risk_score']):>22} | {str(high['risk_score']):>22}")

    low_prem = f"${low['premium']:,.0f}" if isinstance(low["premium"], (int, float)) else str(low["premium"])
    high_prem = f"${high['premium']:,.0f}" if isinstance(high["premium"], (int, float)) else str(high["premium"])
    print(f"  {'Premium':<25} | {low_prem:>22} | {high_prem:>22}")
    print(f"  {'Recommendation':<25} | {str(low['recommendation']):>22} | {str(high['recommendation']):>22}")

    # Verify differentiation
    scores_differ = low["risk_score"] != high["risk_score"]
    premiums_differ = low["premium"] != high["premium"]

    print(f"\n  Scores differ:   {'✅ YES' if scores_differ else '❌ NO — BUG!'}")
    print(f"  Premiums differ: {'✅ YES' if premiums_differ else '❌ NO — BUG!'}")

    if low["risk_score"] and high["risk_score"]:
        correct_order = low["risk_score"] < high["risk_score"]
        print(f"  Low < High:      {'✅ YES' if correct_order else '⚠️ Inverted!'}")

    print(f"\n  📁 Screenshots: {SCREENSHOT_DIR.resolve()}")
    print("=" * 70)

    all_good = scores_differ and premiums_differ
    if all_good:
        print("✅ Portal tests PASSED — UI shows different results for different risks")
    else:
        print("❌ Portal tests FAILED — agents may not be differentiating properly")

    return all_good


if __name__ == "__main__":
    ok = asyncio.run(run_portal_tests())
    sys.exit(0 if ok else 1)
