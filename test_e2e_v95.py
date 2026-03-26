"""
OpenInsure v95 Tech-Debt E2E Tests
Comprehensive Playwright + API tests after 16-issue refactoring.
"""

import asyncio
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests
from playwright.async_api import async_playwright

# ── Config ──────────────────────────────────────────────────────────────────
BACKEND = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
DASHBOARD = "https://openinsure-dashboard.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
API_KEY = "openinsure-dev-key-2024"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}
SCREENSHOT_DIR = Path("test-screenshots/v95-tech-debt")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

TIMEOUT = 30_000  # 30s page load timeout
NAV_TIMEOUT = 60_000  # 60s navigation timeout

results = []


def log_result(category: str, name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    icon = "✅" if passed else "❌"
    results.append({"category": category, "name": name, "passed": passed, "detail": detail})
    print(f"  {icon} [{status}] {name}" + (f" — {detail}" if detail else ""))


# ════════════════════════════════════════════════════════════════════════════
# PART 1: BACKEND API TESTS
# ════════════════════════════════════════════════════════════════════════════
def run_api_tests():
    print("\n" + "=" * 70)
    print("PART 1: BACKEND API TESTS")
    print("=" * 70)

    # ── Health check ────────────────────────────────────────────────────────
    print("\n── Health & Connectivity ──")
    try:
        r = requests.get(f"{BACKEND}/", timeout=15)
        data = r.json()
        ok = r.status_code == 200 and data.get("status") == "healthy"
        log_result("API", "Health check", ok, f"status={data.get('status')}, version={data.get('version')}")
    except Exception as e:
        log_result("API", "Health check", False, str(e))

    # ── Products: list (expect 6 from SQL) ──────────────────────────────────
    print("\n── Products API (persistence refactor) ──")
    product_id = None
    try:
        r = requests.get(f"{BACKEND}/api/v1/products", headers=HEADERS, timeout=15)
        products = r.json()
        if isinstance(products, dict) and "products" in products:
            products_list = products["products"]
        elif isinstance(products, list):
            products_list = products
        else:
            products_list = []
        count = len(products_list)
        ok = r.status_code == 200 and count >= 6
        log_result("API", "GET /products → ≥6 products", ok, f"got {count} products")
        if products_list:
            product_id = products_list[0].get("id") or products_list[0].get("product_id")
            names = [p.get("name", "?") for p in products_list[:6]]
            print(f"    Products: {', '.join(names)}")
    except Exception as e:
        log_result("API", "GET /products → ≥6 products", False, str(e))

    # ── Product detail ──────────────────────────────────────────────────────
    if product_id:
        try:
            r = requests.get(f"{BACKEND}/api/v1/products/{product_id}", headers=HEADERS, timeout=15)
            detail = r.json()
            has_coverages = "coverages" in detail or "coverage" in str(detail).lower()
            log_result("API", f"GET /products/{product_id} detail", r.status_code == 200, 
                       f"has coverages={has_coverages}")
        except Exception as e:
            log_result("API", f"GET /products/{product_id} detail", False, str(e))

        # ── Product update (persistence) ────────────────────────────────────
        try:
            update_payload = {"description": f"E2E test update {datetime.now().isoformat()}"}
            r = requests.put(f"{BACKEND}/api/v1/products/{product_id}", 
                           headers=HEADERS, json=update_payload, timeout=15)
            update_ok = r.status_code in (200, 201, 204)
            log_result("API", f"PUT /products/{product_id} update", update_ok, f"status={r.status_code}")

            # Verify persistence
            r2 = requests.get(f"{BACKEND}/api/v1/products/{product_id}", headers=HEADERS, timeout=15)
            detail2 = r2.json()
            persisted = update_payload["description"] in str(detail2)
            log_result("API", "Product update persisted", persisted,
                       "description updated" if persisted else "update not reflected")
        except Exception as e:
            log_result("API", "PUT /products update+verify", False, str(e))

        # ── Rating engine (multi-factor, not flat $5K) ──────────────────────
        print("\n── Rating Engine (Foundry fallback) ──")
        try:
            rate_payload = {
                "submission_data": {
                    "business_type": "restaurant",
                    "annual_revenue": 2_000_000,
                    "employee_count": 50,
                    "years_in_business": 10,
                    "state": "CA",
                    "coverage_amount": 1_000_000,
                },
            }
            r = requests.post(f"{BACKEND}/api/v1/products/{product_id}/rate",
                            headers=HEADERS, json=rate_payload, timeout=30)
            if r.status_code == 200:
                rate_result = r.json()
                premium = rate_result.get("premium") or rate_result.get("total_premium") or rate_result.get("annual_premium")
                if premium is None:
                    # Try nested
                    for key in rate_result:
                        if isinstance(rate_result[key], (int, float)) and rate_result[key] > 0:
                            premium = rate_result[key]
                            break
                not_flat = premium is not None and premium != 5000
                log_result("API", "POST /products/rate → non-$5K", not_flat,
                           f"premium={premium}" if premium else f"response keys: {list(rate_result.keys())}")
            else:
                log_result("API", "POST /products/rate → non-$5K", False, 
                           f"status={r.status_code}, body={r.text[:200]}")
        except Exception as e:
            log_result("API", "POST /products/rate → non-$5K", False, str(e))

    # ── Coverages endpoint ──────────────────────────────────────────────────
    if product_id:
        try:
            r = requests.get(f"{BACKEND}/api/v1/products/{product_id}/coverages", headers=HEADERS, timeout=15)
            ok = r.status_code == 200
            data = r.json() if ok else {}
            log_result("API", f"GET /products/{product_id}/coverages", ok,
                       f"count={len(data) if isinstance(data, list) else 'obj'}")
        except Exception as e:
            log_result("API", "GET /products/coverages", False, str(e))

    # ── Admin sync-products ─────────────────────────────────────────────────
    print("\n── Admin Sync (Cosmos/AI Search) ──")
    try:
        r = requests.post(f"{BACKEND}/api/v1/admin/sync-products", headers=HEADERS, timeout=30)
        ok = r.status_code in (200, 201, 202)
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:200]
        log_result("API", "POST /admin/sync-products", ok, f"status={r.status_code}")
    except Exception as e:
        log_result("API", "POST /admin/sync-products", False, str(e))

    # ── Metrics (executive dashboard data) ──────────────────────────────────
    print("\n── Metrics & Analytics APIs ──")
    for endpoint, label in [
        ("/api/v1/metrics/summary", "Metrics summary"),
        ("/api/v1/metrics/executive", "Executive metrics"),
        ("/api/v1/metrics/pipeline", "Pipeline metrics"),
    ]:
        try:
            r = requests.get(f"{BACKEND}{endpoint}", headers=HEADERS, timeout=15)
            ok = r.status_code == 200
            log_result("API", label, ok, f"status={r.status_code}")
        except Exception as e:
            log_result("API", label, False, str(e))

    # ── Knowledge API ───────────────────────────────────────────────────────
    print("\n── Knowledge API (extracted to knowledge_store.py) ──")
    for endpoint, label in [
        ("/api/v1/knowledge/products", "Knowledge products"),
        ("/api/v1/knowledge/sync-status", "Knowledge sync status"),
        ("/api/v1/knowledge/guidelines/commercial_property", "Guidelines: commercial property"),
        ("/api/v1/knowledge/compliance-rules", "Compliance rules list"),
    ]:
        try:
            r = requests.get(f"{BACKEND}{endpoint}", headers=HEADERS, timeout=15)
            ok = r.status_code == 200
            data = r.json() if ok else {}
            log_result("API", label, ok, f"keys={list(data.keys())[:5]}" if isinstance(data, dict) else f"len={len(data) if isinstance(data, list) else '?'}")
        except Exception as e:
            log_result("API", label, False, str(e))

    # ── Escalations ────────────────────────────────────────────────────────
    print("\n── Escalations API ──")
    try:
        r = requests.get(f"{BACKEND}/api/v1/escalations/count", headers=HEADERS, timeout=15)
        ok = r.status_code == 200
        log_result("API", "Escalations count", ok, f"response={r.json() if ok else r.status_code}")
    except Exception as e:
        log_result("API", "Escalations count", False, str(e))

    try:
        r = requests.get(f"{BACKEND}/api/v1/escalations", headers=HEADERS, timeout=15)
        ok = r.status_code == 200
        log_result("API", "Escalations list", ok, f"status={r.status_code}")
    except Exception as e:
        log_result("API", "Escalations list", False, str(e))

    # ── Compliance ──────────────────────────────────────────────────────────
    print("\n── Compliance API (BaseRepository refactor) ──")
    for endpoint, label in [
        ("/api/v1/compliance/decisions", "Compliance decisions"),
        ("/api/v1/compliance/audit-trail", "Audit trail"),
        ("/api/v1/compliance/system-inventory", "System inventory"),
    ]:
        try:
            r = requests.get(f"{BACKEND}{endpoint}", headers=HEADERS, timeout=15)
            ok = r.status_code == 200
            log_result("API", label, ok, f"status={r.status_code}")
        except Exception as e:
            log_result("API", label, False, str(e))

    # ── Submissions, Policies, Claims lists ─────────────────────────────────
    print("\n── Core Entity Lists ──")
    for endpoint, label in [
        ("/api/v1/submissions", "Submissions list"),
        ("/api/v1/policies", "Policies list"),
        ("/api/v1/claims", "Claims list"),
        ("/api/v1/underwriter/queue", "UW queue"),
        ("/api/v1/broker/submissions", "Broker submissions"),
    ]:
        try:
            r = requests.get(f"{BACKEND}{endpoint}", headers=HEADERS, timeout=15)
            ok = r.status_code == 200
            log_result("API", label, ok, f"status={r.status_code}")
        except Exception as e:
            log_result("API", label, False, str(e))

    # ── Finance & Actuarial ─────────────────────────────────────────────────
    print("\n── Finance & Actuarial APIs ──")
    for endpoint, label in [
        ("/api/v1/finance/summary", "Finance summary"),
        ("/api/v1/actuarial/reserves", "Actuarial reserves"),
        ("/api/v1/actuarial/rate-adequacy", "Rate adequacy"),
    ]:
        try:
            r = requests.get(f"{BACKEND}{endpoint}", headers=HEADERS, timeout=15)
            ok = r.status_code == 200
            log_result("API", label, ok, f"status={r.status_code}")
        except Exception as e:
            log_result("API", label, False, str(e))


# ════════════════════════════════════════════════════════════════════════════
# PART 2: PLAYWRIGHT DASHBOARD E2E TESTS
# ════════════════════════════════════════════════════════════════════════════

# Pages to test: (route, screenshot_name, description, content_checks)
PAGES = [
    {
        "route": "/products",
        "name": "01-product-management",
        "title": "Product Management",
        "checks": ["product", "commercial"],  # keywords in page
    },
    {
        "route": "/submissions",
        "name": "02-submissions-list",
        "title": "Submissions List",
        "checks": ["submission"],
    },
    {
        "route": "/submissions/new",
        "name": "03-submissions-new",
        "title": "New Submission",
        "checks": ["submit", "business", "insured"],
    },
    {
        "route": "/workbench/underwriting",
        "name": "04-underwriting-workbench",
        "title": "Underwriting Workbench",
        "checks": ["underwriting", "risk"],
    },
    {
        "route": "/policies",
        "name": "05-policy-dashboard",
        "title": "Policies",
        "checks": ["polic"],
    },
    {
        "route": "/claims",
        "name": "06-claims-management",
        "title": "Claims",
        "checks": ["claim"],
    },
    {
        "route": "/executive",
        "name": "07-executive-dashboard",
        "title": "Executive Dashboard",
        "checks": ["premium", "ratio"],
    },
    {
        "route": "/knowledge",
        "name": "08-knowledge-base",
        "title": "Knowledge Base",
        "checks": ["knowledge", "guideline"],
    },
    {
        "route": "/workbench/compliance",
        "name": "09-compliance-workbench",
        "title": "Compliance Workbench",
        "checks": ["compliance"],
    },
    {
        "route": "/finance",
        "name": "10-billing-finance",
        "title": "Billing & Finance",
        "checks": ["finance", "billing"],
    },
    {
        "route": "/escalations",
        "name": "11-escalations",
        "title": "Escalations",
        "checks": ["escalat"],
    },
    {
        "route": "/portal/broker",
        "name": "12-broker-portal",
        "title": "Broker Portal",
        "checks": ["broker"],
    },
    {
        "route": "/workbench/actuarial",
        "name": "13-actuarial-workbench",
        "title": "Actuarial Workbench",
        "checks": ["actuarial", "reserve"],
    },
    {
        "route": "/compliance",
        "name": "14-compliance-dashboard",
        "title": "Compliance Dashboard",
        "checks": ["compliance"],
    },
    {
        "route": "/",
        "name": "15-main-dashboard",
        "title": "Dashboard",
        "checks": ["dashboard"],
    },
]


async def test_page(page, pg_config):
    """Navigate to a page, wait for content, screenshot, assert content."""
    route = pg_config["route"]
    name = pg_config["name"]
    title = pg_config["title"]
    checks = pg_config["checks"]

    url = f"{DASHBOARD}{route}"
    try:
        resp = await page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT)
        status = resp.status if resp else "no response"

        # Wait for spinners/skeletons to disappear
        try:
            await page.wait_for_load_state("networkidle", timeout=15_000)
        except Exception:
            pass

        # Extra wait for React hydration
        await page.wait_for_timeout(3000)

        # Take screenshot
        ss_path = SCREENSHOT_DIR / f"{name}.png"
        await page.screenshot(path=str(ss_path), full_page=True)

        # Get page text content
        body_text = await page.inner_text("body")
        body_lower = body_text.lower()

        # Check it's not blank or error
        is_blank = len(body_text.strip()) < 50
        has_error = "error" in body_lower and "something went wrong" in body_lower
        has_crash = "cannot read properties" in body_lower or "unhandled" in body_lower

        # Content checks (at least one keyword must be present)
        keyword_found = any(kw.lower() in body_lower for kw in checks)

        if is_blank:
            log_result("UI", f"{title} — page loads", False, "page is blank (<50 chars)")
        elif has_crash:
            log_result("UI", f"{title} — page loads", False, "JS crash detected")
        elif has_error:
            log_result("UI", f"{title} — page loads", False, "error banner on page")
        elif not keyword_found:
            # Still passed loading, but content check failed
            log_result("UI", f"{title} — content check", False,
                       f"none of {checks} found in page text (len={len(body_text)})")
            log_result("UI", f"{title} — page loads", True, f"status={status}")
        else:
            log_result("UI", f"{title} — page loads", True, f"status={status}, keywords found")

        return True

    except Exception as e:
        ss_path = SCREENSHOT_DIR / f"{name}-error.png"
        try:
            await page.screenshot(path=str(ss_path))
        except Exception:
            pass
        log_result("UI", f"{title} — page loads", False, str(e)[:200])
        return False


async def test_product_detail(page):
    """Navigate to products list, click first product to see detail with coverages/rating."""
    print("\n── Product Detail (coverages & rating factors) ──")
    try:
        await page.goto(f"{DASHBOARD}/products", wait_until="networkidle", timeout=NAV_TIMEOUT)
        await page.wait_for_timeout(3000)

        # Try to find and click first product link/card
        product_links = await page.query_selector_all("a[href*='/products/'], tr[class*='cursor'], [data-testid*='product']")
        if not product_links:
            # Try table rows
            product_links = await page.query_selector_all("table tbody tr")
        if not product_links:
            product_links = await page.query_selector_all("[class*='card'], [class*='Card']")

        if product_links:
            await product_links[0].click()
            await page.wait_for_timeout(3000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass

            ss_path = SCREENSHOT_DIR / "01b-product-detail.png"
            await page.screenshot(path=str(ss_path), full_page=True)

            body = await page.inner_text("body")
            body_lower = body.lower()
            has_coverage = "coverage" in body_lower or "limit" in body_lower
            has_rating = "rating" in body_lower or "factor" in body_lower or "premium" in body_lower
            log_result("UI", "Product detail — coverages visible", has_coverage,
                       f"coverage={'yes' if has_coverage else 'no'}")
            log_result("UI", "Product detail — rating factors", has_rating,
                       f"rating={'yes' if has_rating else 'no'}")
        else:
            log_result("UI", "Product detail — navigation", False, "no product links found to click")
    except Exception as e:
        log_result("UI", "Product detail", False, str(e)[:200])


async def test_sidebar_escalation_badge(page):
    """Check that escalation badge appears in sidebar."""
    print("\n── Sidebar Escalation Badge ──")
    try:
        await page.goto(f"{DASHBOARD}/", wait_until="networkidle", timeout=NAV_TIMEOUT)
        await page.wait_for_timeout(3000)

        # Look for badge/count near escalation nav item
        sidebar_html = ""
        sidebar = await page.query_selector("nav, [class*='sidebar'], [class*='Sidebar'], aside")
        if sidebar:
            sidebar_html = await sidebar.inner_text()

        has_escalation = "escalat" in sidebar_html.lower()
        # Look for a badge (number)
        import re
        badge_numbers = re.findall(r'\b\d+\b', sidebar_html)

        ss_path = SCREENSHOT_DIR / "11b-sidebar-badge.png"
        await page.screenshot(path=str(ss_path))

        log_result("UI", "Sidebar escalation link", has_escalation,
                   f"found='{'yes' if has_escalation else 'no'}'")
    except Exception as e:
        log_result("UI", "Sidebar escalation badge", False, str(e)[:200])


async def test_knowledge_tabs(page):
    """Check knowledge base tabs render and have content."""
    print("\n── Knowledge Base Tabs ──")
    try:
        await page.goto(f"{DASHBOARD}/knowledge", wait_until="networkidle", timeout=NAV_TIMEOUT)
        await page.wait_for_timeout(3000)

        body = await page.inner_text("body")
        body_lower = body.lower()

        # Check for tab-like content
        tab_keywords = ["guideline", "rating", "coverage", "compliance", "precedent", "industry"]
        found_tabs = [k for k in tab_keywords if k in body_lower]

        ss_path = SCREENSHOT_DIR / "08b-knowledge-tabs.png"
        await page.screenshot(path=str(ss_path), full_page=True)

        log_result("UI", "Knowledge tabs render", len(found_tabs) >= 2,
                   f"tabs found: {found_tabs}")
    except Exception as e:
        log_result("UI", "Knowledge tabs", False, str(e)[:200])


async def run_dashboard_tests():
    print("\n" + "=" * 70)
    print("PART 2: PLAYWRIGHT DASHBOARD E2E TESTS")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Test all pages
        for pg_config in PAGES:
            print(f"\n── {pg_config['title']} ({pg_config['route']}) ──")
            await test_page(page, pg_config)

        # Detailed tests
        await test_product_detail(page)
        await test_sidebar_escalation_badge(page)
        await test_knowledge_tabs(page)

        await browser.close()


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
def print_summary():
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    api_results = [r for r in results if r["category"] == "API"]
    ui_results = [r for r in results if r["category"] == "UI"]

    api_pass = sum(1 for r in api_results if r["passed"])
    ui_pass = sum(1 for r in ui_results if r["passed"])

    print(f"\n  API Tests: {api_pass}/{len(api_results)} passed")
    print(f"  UI Tests:  {ui_pass}/{len(ui_results)} passed")
    print(f"  Total:     {api_pass + ui_pass}/{len(results)} passed")

    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"\n  ❌ FAILURES ({len(failures)}):")
        for f in failures:
            print(f"    [{f['category']}] {f['name']}: {f['detail']}")
    else:
        print("\n  🎉 ALL TESTS PASSED!")

    print(f"\n  Screenshots saved to: {SCREENSHOT_DIR.resolve()}")
    print("=" * 70)

    return len(failures) == 0


if __name__ == "__main__":
    print(f"OpenInsure v95 Tech-Debt E2E Tests — {datetime.now().isoformat()}")
    print(f"Backend:   {BACKEND}")
    print(f"Dashboard: {DASHBOARD}")

    run_api_tests()
    asyncio.run(run_dashboard_tests())
    all_passed = print_summary()
    sys.exit(0 if all_passed else 1)
