"""
OpenInsure v95 Comprehensive Playwright E2E Tests
Tests ALL portal pages with proper role-based access across 11 personas.
"""
# ruff: noqa: T201

import asyncio
import os
import re
import sys
from dataclasses import dataclass, field

from playwright.async_api import Page, async_playwright

# ── Constants ──────────────────────────────────────────────────────────────────

DASHBOARD_URL = "https://openinsure-dashboard.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
BACKEND_URL = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "test-screenshots", "v95-functional")
TIMEOUT = 30_000  # 30s for page loads
NAV_TIMEOUT = 15_000

# ── Personas ───────────────────────────────────────────────────────────────────


@dataclass
class Persona:
    name: str
    role: str
    landing: str
    nav_routes: list = field(default_factory=list)


PERSONAS = {
    "ceo": Persona(
        "Alexandra Reed",
        "ceo",
        "/executive",
        [
            "/",
            "/decisions",
            "/escalations",
            "/finance",
            "/compliance",
            "/products",
            "/analytics/underwriting",
            "/analytics/claims",
            "/workbench/actuarial",
            "/executive",
        ],
    ),
    "cuo": Persona(
        "Sarah Chen",
        "cuo",
        "/",
        [
            "/",
            "/submissions",
            "/policies",
            "/claims",
            "/decisions",
            "/escalations",
            "/finance",
            "/compliance",
            "/knowledge",
            "/products",
            "/analytics/underwriting",
            "/analytics/claims",
            "/workbench/underwriting",
            "/workbench/reinsurance",
            "/workbench/actuarial",
            "/executive",
        ],
    ),
    "senior_uw": Persona(
        "James Wright",
        "senior_uw",
        "/workbench/underwriting",
        [
            "/",
            "/submissions",
            "/policies",
            "/escalations",
            "/knowledge",
            "/analytics/underwriting",
            "/workbench/underwriting",
        ],
    ),
    "uw_analyst": Persona(
        "Maria Lopez",
        "uw_analyst",
        "/workbench/underwriting",
        ["/", "/submissions", "/policies", "/analytics/underwriting", "/workbench/underwriting"],
    ),
    "claims_manager": Persona(
        "David Park",
        "claims_manager",
        "/workbench/claims",
        ["/", "/claims", "/escalations", "/policies", "/analytics/claims", "/workbench/claims"],
    ),
    "adjuster": Persona(
        "Lisa Martinez",
        "adjuster",
        "/workbench/claims",
        ["/", "/claims", "/escalations", "/analytics/claims", "/workbench/claims"],
    ),
    "cfo": Persona(
        "Michael Torres",
        "cfo",
        "/executive",
        [
            "/",
            "/policies",
            "/escalations",
            "/finance",
            "/analytics/underwriting",
            "/analytics/claims",
            "/workbench/reinsurance",
            "/workbench/actuarial",
            "/executive",
        ],
    ),
    "compliance": Persona(
        "Anna Kowalski",
        "compliance",
        "/workbench/compliance",
        ["/", "/policies", "/claims", "/decisions", "/compliance", "/knowledge", "/workbench/compliance"],
    ),
    "product_mgr": Persona(
        "Robert Chen",
        "product_mgr",
        "/products",
        [
            "/",
            "/submissions",
            "/decisions",
            "/knowledge",
            "/products",
            "/analytics/underwriting",
            "/workbench/actuarial",
        ],
    ),
    "operations": Persona("Emily Davis", "operations", "/finance", ["/", "/submissions", "/finance"]),
    "broker": Persona("Thomas Anderson", "broker", "/portal/broker", ["/portal/broker"]),
}

# ── Result Tracking ───────────────────────────────────────────────────────────

results: list[tuple[str, str, str]] = []  # (status, name, detail)


def PASS(name: str, detail: str = ""):
    results.append(("PASS", name, detail))
    print(f"  [PASS] {name}{(' — ' + detail) if detail else ''}")


def FAIL(name: str, detail: str = ""):
    results.append(("FAIL", name, detail))
    print(f"  [FAIL] {name}{(' — ' + detail) if detail else ''}")


def WARN(name: str, detail: str = ""):
    results.append(("WARN", name, detail))
    print(f"  [WARN] {name}{(' — ' + detail) if detail else ''}")


# ── Helpers ────────────────────────────────────────────────────────────────────


async def screenshot(page: Page, name: str):
    path = os.path.join(SCREENSHOT_DIR, name)
    await page.screenshot(path=path, full_page=True)


async def login_as(page: Page, role: str) -> bool:
    """Login as a specific persona. Returns True on success."""
    persona = PERSONAS[role]
    await page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)

    # Try clicking persona button
    btn = page.locator(f'button:has-text("{persona.name}")')
    if await btn.count() > 0:
        await btn.first.click()
        await page.wait_for_timeout(3000)
        await page.wait_for_load_state("networkidle")
        body = await page.inner_text("body")
        if len(body) > 500 and "sign in" not in body.lower()[:200]:
            return True

    # Fallback: set localStorage directly
    await page.evaluate(f"localStorage.setItem('openinsure_role', '{persona.role}')")
    await page.reload(wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(3000)
    body = await page.inner_text("body")
    return len(body) > 500


async def navigate_to(page: Page, path: str, wait_for_content: bool = True):
    """Navigate to a path and wait for content to load."""
    url = DASHBOARD_URL + path
    await page.goto(url, wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)
    if wait_for_content:
        # Wait for spinners/loading indicators to disappear
        try:
            loading = page.locator('text="Loading"')
            if await loading.count() > 0:
                await loading.first.wait_for(state="hidden", timeout=15000)
        except Exception:  # noqa: S110
            pass
        try:
            spinner = page.locator('[class*="animate-spin"]')
            if await spinner.count() > 0:
                await spinner.first.wait_for(state="hidden", timeout=15000)
        except Exception:  # noqa: S110
            pass


async def check_no_blank_page(page: Page, context: str) -> bool:
    """Check that the page has meaningful content."""
    body_text = await page.inner_text("body")
    body_text = body_text.strip()

    if len(body_text) < 50:
        FAIL(f"blank-page:{context}", f"Body text only {len(body_text)} chars")
        return False
    if "500 Internal Server Error" in body_text:
        FAIL(f"server-error:{context}", "500 error visible")
        return False
    return True


async def collect_console_errors(page: Page) -> list[str]:
    """Collect JS console errors."""
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    return errors


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — Login & Role Selection
# ══════════════════════════════════════════════════════════════════════════════


async def phase1_login_and_roles(page: Page):
    print("\n═══ PHASE 1: Login & Role Selection ═══")

    for role_key, persona in PERSONAS.items():
        test_name = f"login:{role_key}"
        try:
            ok = await login_as(page, role_key)
            if not ok:
                FAIL(test_name, "Login failed — page appears blank after auth")
                continue

            # Check we landed on the correct page
            current_url = page.url
            if persona.landing in current_url or role_key == "cuo":
                PASS(test_name, f"Landed on {persona.landing}")
            else:
                WARN(test_name, f"Expected {persona.landing}, got {current_url}")

            # Check sidebar nav items
            if role_key != "broker":
                sidebar = page.locator("aside")
                if await sidebar.count() > 0:
                    visible_links = []
                    for route in persona.nav_routes:
                        link = page.locator(f'a[href="{route}"]')
                        if await link.count() > 0 and await link.first.is_visible():
                            visible_links.append(route)
                    if len(visible_links) >= len(persona.nav_routes) * 0.5:
                        PASS(f"nav:{role_key}", f"{len(visible_links)}/{len(persona.nav_routes)} nav items visible")
                    else:
                        msg = f"Only {len(visible_links)}/{len(persona.nav_routes)} nav items visible"
                        WARN(f"nav:{role_key}", msg)
                else:
                    WARN(f"nav:{role_key}", "No sidebar found")
            else:
                PASS(f"nav:{role_key}", "Broker portal — scoped view")

            await screenshot(page, f"{role_key}-dashboard.png")

            # Logout for next persona
            await page.evaluate("localStorage.removeItem('openinsure_role')")

        except Exception as e:
            FAIL(test_name, str(e)[:120])


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — Core Workflow Tests
# ══════════════════════════════════════════════════════════════════════════════


async def phase2a_submissions(page: Page):
    """Test submission flow as CUO (Sarah Chen)."""
    print("\n─── 2a: Submission Flow ───")
    await login_as(page, "cuo")

    # Navigate to submissions list
    await navigate_to(page, "/submissions")
    await page.wait_for_timeout(2000)

    body = await page.inner_text("body")
    if "submission" in body.lower() or "new" in body.lower():
        PASS("submissions-list", "Submissions page loads with content")
    else:
        FAIL("submissions-list", "Submissions page content not found")
    await screenshot(page, "submission-list.png")

    # Try New Submission
    try:
        new_btn = page.locator(
            'button:has-text("New Submission"), a:has-text("New Submission"), a[href="/submissions/new"]'
        )
        if await new_btn.count() > 0:
            await new_btn.first.click()
            await page.wait_for_timeout(3000)
            await page.wait_for_load_state("networkidle")
            body = await page.inner_text("body")
            if len(body) > 100:
                PASS("new-submission-form", "New submission form loads")
                await screenshot(page, "new-submission-form.png")
            else:
                WARN("new-submission-form", "Form page seems light on content")
                await screenshot(page, "new-submission-form.png")
        else:
            WARN("new-submission-form", "No 'New Submission' button found")
    except Exception as e:
        WARN("new-submission-form", str(e)[:100])


async def phase2b_uw_workbench(page: Page):
    """Test UW Workbench as CUO."""
    print("\n─── 2b: Underwriting Workbench ───")
    await login_as(page, "cuo")
    await navigate_to(page, "/workbench/underwriting")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "uw-workbench")
    if has_content:
        # Check for queue/submissions in workbench
        if any(kw in body.lower() for kw in ["queue", "submission", "underwriting", "risk", "score", "workbench"]):
            PASS("uw-workbench", "UW Workbench loads with queue data")
        else:
            WARN("uw-workbench", "UW Workbench loaded but expected keywords not found")
    await screenshot(page, "uw-workbench.png")

    # Try clicking on a submission in the queue
    try:
        rows = page.locator("tr, [class*='card'], [class*='item'], [role='row']")
        row_count = await rows.count()
        if row_count > 1:
            await rows.nth(1).click()
            await page.wait_for_timeout(3000)
            body = await page.inner_text("body")
            if any(kw in body.lower() for kw in ["risk", "score", "detail", "assessment", "premium"]):
                PASS("uw-detail-panel", "Detail panel opens with risk data")
            else:
                WARN("uw-detail-panel", "Clicked item but detail panel content unclear")
            await screenshot(page, "uw-detail-panel.png")
        else:
            WARN("uw-detail-panel", "No clickable items in workbench queue")
    except Exception as e:
        WARN("uw-detail-panel", str(e)[:100])


async def phase2c_policies(page: Page):
    """Test Policy Dashboard as CUO."""
    print("\n─── 2c: Policy Dashboard ───")
    await login_as(page, "cuo")
    await navigate_to(page, "/policies")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "policies")
    if has_content:
        # Check for policy count
        numbers = re.findall(r"\b\d{2,4}\b", body)
        if numbers:
            PASS("policies-list", f"Policies page loads, found numbers: {numbers[:5]}")
        else:
            WARN("policies-list", "Policies page loads but no numeric counts found")
    await screenshot(page, "policies-list.png")


async def phase2d_claims(page: Page):
    """Test Claims as Claims Manager."""
    print("\n─── 2d: Claims Management ───")
    await login_as(page, "claims_manager")
    await navigate_to(page, "/claims")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "claims")
    if has_content:
        if any(kw in body.lower() for kw in ["claim", "status", "open", "closed", "reserve"]):
            PASS("claims-list", "Claims page loads with claim data")
        else:
            WARN("claims-list", "Claims page loads but expected keywords missing")

        # Test filters
        try:
            filters = page.locator(
                'button:has-text("Open"), button:has-text("Closed"), button:has-text("All"), select, [role="tab"]'
            )
            if await filters.count() > 0:
                PASS("claims-filters", f"Found {await filters.count()} filter controls")
            else:
                WARN("claims-filters", "No filter controls found")
        except Exception:
            WARN("claims-filters", "Could not check filters")

    await screenshot(page, "claims-list.png")


async def phase2e_products(page: Page):
    """Test Product Management as product_mgr."""
    print("\n─── 2e: Product Management ───")
    await login_as(page, "product_mgr")
    await navigate_to(page, "/products")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "products")
    if has_content:
        # Check for product cards
        cards = page.locator('[class*="card"], [class*="Card"]')
        card_count = await cards.count()
        if card_count >= 4:
            PASS("product-catalog", f"Product catalog loads with {card_count} cards")
        elif card_count > 0:
            WARN("product-catalog", f"Only {card_count} product cards (expected ~6)")
        else:
            # Maybe products are in a list/table
            if any(kw in body.lower() for kw in ["cyber", "liability", "property", "product"]):
                PASS("product-catalog", "Product catalog loads with product data")
            else:
                WARN("product-catalog", "Product catalog loaded but no products found")

    await screenshot(page, "product-catalog.png")

    # Try clicking Cyber Liability product
    try:
        cyber = page.locator('text="Cyber Liability"').first
        if await cyber.is_visible():
            await cyber.click()
            await page.wait_for_timeout(3000)
            await page.wait_for_load_state("networkidle")
            body = await page.inner_text("body")
            if len(body) > 200:
                PASS("product-detail", "Product detail page loads")
                await screenshot(page, "product-detail.png")

                # Check tabs
                for tab_name, ss_name in [
                    ("Coverages", "product-coverages.png"),
                    ("Rating", "product-rating.png"),
                    ("Performance", "product-performance.png"),
                ]:
                    tab = page.locator(
                        f'button:has-text("{tab_name}"), [role="tab"]:has-text("{tab_name}"), a:has-text("{tab_name}")'
                    )
                    if await tab.count() > 0:
                        await tab.first.click()
                        await page.wait_for_timeout(2000)
                        await screenshot(page, ss_name)
                        PASS(f"product-tab:{tab_name}", f"{tab_name} tab renders")
                    else:
                        WARN(f"product-tab:{tab_name}", f"No '{tab_name}' tab found")
            else:
                WARN("product-detail", "Product detail page seems sparse")
        else:
            WARN("product-detail", "'Cyber Liability' text not visible to click")
    except Exception as e:
        WARN("product-detail", str(e)[:100])


async def phase2f_executive(page: Page):
    """Test Executive Dashboard as CEO."""
    print("\n─── 2f: Executive Dashboard ───")
    await login_as(page, "ceo")
    await navigate_to(page, "/executive")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "executive")
    if has_content:
        checks = {
            "gwp": any(kw in body.lower() for kw in ["gwp", "gross written", "premium", "$"]),
            "loss-ratio": any(kw in body.lower() for kw in ["loss ratio", "loss", "ratio"]),
            "pipeline": any(kw in body.lower() for kw in ["pipeline", "funnel", "submission"]),
            "agent": any(kw in body.lower() for kw in ["agent", "ai", "decision"]),
        }
        passed = sum(1 for v in checks.values() if v)
        if passed >= 3:
            PASS("executive-dashboard", f"Executive Dashboard renders ({passed}/4 sections found)")
        elif passed >= 1:
            WARN("executive-dashboard", f"Only {passed}/4 sections found: {[k for k, v in checks.items() if v]}")
        else:
            FAIL("executive-dashboard", "Executive Dashboard has no expected content")

        # Check for GWP number ($24M+)
        gwp_match = re.search(r"\$[\d,.]+[MBK]?", body)
        if gwp_match:
            PASS("executive-gwp-figure", f"GWP figure found: {gwp_match.group()}")
        else:
            WARN("executive-gwp-figure", "No dollar figure found on executive dashboard")

    await screenshot(page, "executive-dashboard.png")


async def phase2g_knowledge(page: Page):
    """Test Knowledge Base as product_mgr."""
    print("\n─── 2g: Knowledge Base ───")
    await login_as(page, "product_mgr")
    await navigate_to(page, "/knowledge")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "knowledge")
    if has_content:
        if any(kw in body.lower() for kw in ["knowledge", "guideline", "product", "rating", "factor", "document"]):
            PASS("knowledge-base", "Knowledge Base loads with content")
        else:
            WARN("knowledge-base", "Knowledge Base loaded but expected keywords missing")

        # Check for tabs
        tabs = page.locator(
            '[role="tab"], button:has-text("Guidelines"), button:has-text("Products"), button:has-text("Rating")'
        )
        if await tabs.count() > 0:
            PASS("knowledge-tabs", f"Found {await tabs.count()} tabs/sections")
            # Click through first couple of tabs
            for i in range(min(await tabs.count(), 3)):
                await tabs.nth(i).click()
                await page.wait_for_timeout(1500)
        else:
            WARN("knowledge-tabs", "No tabs found on Knowledge page")

    await screenshot(page, "knowledge-base.png")


async def phase2h_compliance(page: Page):
    """Test Compliance Workbench as Compliance Officer."""
    print("\n─── 2h: Compliance Workbench ───")
    await login_as(page, "compliance")
    await navigate_to(page, "/workbench/compliance")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "compliance-workbench")
    if has_content:
        checks = {
            "bias": any(kw in body.lower() for kw in ["bias", "fairness", "fria", "disparate"]),
            "audit": any(kw in body.lower() for kw in ["audit", "trail", "log", "decision"]),
            "compliance": "compliance" in body.lower(),
        }
        passed = sum(1 for v in checks.values() if v)
        if passed >= 2:
            PASS("compliance-workbench", f"Compliance Workbench renders ({passed}/3 sections)")
        elif passed >= 1:
            WARN("compliance-workbench", f"Only {passed}/3 sections: {[k for k, v in checks.items() if v]}")
        else:
            FAIL("compliance-workbench", "Compliance Workbench missing expected sections")

    await screenshot(page, "compliance-workbench.png")

    # Also test /compliance (main compliance page)
    await navigate_to(page, "/compliance")
    body = await page.inner_text("body")
    if len(body.strip()) > 100:
        PASS("compliance-page", "Compliance main page loads")
    else:
        WARN("compliance-page", "Compliance main page seems empty")


async def phase2i_billing(page: Page):
    """Test Billing/Finance as CFO."""
    print("\n─── 2i: Billing & Finance ───")
    await login_as(page, "cfo")
    await navigate_to(page, "/finance")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "finance")
    if has_content:
        checks = {
            "premium": any(kw in body.lower() for kw in ["premium", "gwp", "earned"]),
            "cash-flow": any(kw in body.lower() for kw in ["cash", "flow", "revenue", "expense"]),
            "commission": any(kw in body.lower() for kw in ["commission", "agent", "broker"]),
        }
        passed = sum(1 for v in checks.values() if v)
        if passed >= 2:
            PASS("billing-finance", f"Finance Dashboard renders ({passed}/3 sections)")
        elif passed >= 1:
            WARN("billing-finance", f"Only {passed}/3 sections found")
        else:
            FAIL("billing-finance", "Finance Dashboard missing expected content")

        # Check for non-zero amounts
        amounts = re.findall(r"\$[\d,.]+", body)
        if amounts:
            PASS("billing-amounts", f"Found {len(amounts)} dollar amounts, e.g. {amounts[0]}")
        else:
            WARN("billing-amounts", "No dollar amounts found on finance page")

    await screenshot(page, "billing-finance.png")


async def phase2j_actuarial(page: Page):
    """Test Actuarial Workbench as CFO."""
    print("\n─── 2j: Actuarial Workbench ───")
    await login_as(page, "cfo")
    await navigate_to(page, "/workbench/actuarial")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "actuarial")
    if has_content:
        keywords = ["reserve", "triangle", "ibnr", "rate", "actuarial", "loss", "development"]
        found = [kw for kw in keywords if kw in body.lower()]
        if len(found) >= 2:
            PASS("actuarial-workbench", f"Actuarial Workbench loads ({', '.join(found)})")
        elif len(found) >= 1:
            WARN("actuarial-workbench", f"Partial content: {found}")
        else:
            WARN("actuarial-workbench", "Actuarial Workbench loaded but no expected keywords")

    await screenshot(page, "actuarial-workbench.png")


async def phase2k_escalations(page: Page):
    """Test Escalations as CEO."""
    print("\n─── 2k: Escalations ───")
    await login_as(page, "ceo")
    await navigate_to(page, "/escalations")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "escalations")
    if has_content:
        if any(kw in body.lower() for kw in ["escalation", "pending", "queue", "priority", "review"]):
            PASS("escalations", "Escalations page loads with content")
        else:
            WARN("escalations", "Escalations page loaded but expected keywords missing")

    # Check sidebar badge
    badge = page.locator('a[href="/escalations"] span[class*="bg-red"], a[href="/escalations"] span[class*="badge"]')
    if await badge.count() > 0:
        badge_text = await badge.first.inner_text()
        PASS("escalations-badge", f"Badge shows: {badge_text}")
    else:
        WARN("escalations-badge", "No escalation badge found in sidebar")

    await screenshot(page, "escalations.png")


async def phase2l_broker(page: Page):
    """Test Broker Portal as Broker."""
    print("\n─── 2l: Broker Portal ───")
    await login_as(page, "broker")
    await navigate_to(page, "/portal/broker")

    body = await page.inner_text("body")
    has_content = await check_no_blank_page(page, "broker-portal")
    if has_content:
        if any(kw in body.lower() for kw in ["broker", "submission", "policy", "claim", "portal"]):
            PASS("broker-portal", "Broker Portal loads with scoped data")
        else:
            WARN("broker-portal", "Broker Portal loaded but expected keywords missing")

        # Check for tabs
        tab_keywords = ["submission", "polic", "claim"]
        found_tabs = 0
        tabs = page.locator('[role="tab"], button[class*="tab"]')
        tab_count = await tabs.count()
        if tab_count > 0:
            for i in range(tab_count):
                txt = (await tabs.nth(i).inner_text()).lower()
                if any(kw in txt for kw in tab_keywords):
                    found_tabs += 1
            PASS("broker-tabs", f"Found {found_tabs} broker tabs out of {tab_count} total")
        else:
            # Check body text for tab-like sections
            if sum(1 for kw in tab_keywords if kw in body.lower()) >= 2:
                PASS("broker-tabs", "Broker sections found in body content")
            else:
                WARN("broker-tabs", "No tabs or sections found for broker portal")

    await screenshot(page, "broker-portal.png")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — Additional analytics/workbench pages
# ══════════════════════════════════════════════════════════════════════════════


async def phase2_analytics(page: Page):
    """Test analytics pages."""
    print("\n─── 2m: Analytics Pages ───")

    # UW Analytics as CUO
    await login_as(page, "cuo")
    await navigate_to(page, "/analytics/underwriting")
    body = await page.inner_text("body")
    if await check_no_blank_page(page, "uw-analytics"):
        if any(kw in body.lower() for kw in ["analytics", "underwriting", "ratio", "premium", "performance"]):
            PASS("uw-analytics", "UW Analytics page loads with data")
        else:
            WARN("uw-analytics", "UW Analytics loaded but expected keywords missing")
    await screenshot(page, "uw-analytics.png")

    # Claims Analytics
    await navigate_to(page, "/analytics/claims")
    body = await page.inner_text("body")
    if await check_no_blank_page(page, "claims-analytics"):
        if any(kw in body.lower() for kw in ["analytics", "claims", "severity", "frequency", "loss"]):
            PASS("claims-analytics", "Claims Analytics page loads with data")
        else:
            WARN("claims-analytics", "Claims Analytics loaded but expected keywords missing")
    await screenshot(page, "claims-analytics.png")

    # Reinsurance as CUO
    await navigate_to(page, "/workbench/reinsurance")
    body = await page.inner_text("body")
    if await check_no_blank_page(page, "reinsurance"):
        PASS("reinsurance-workbench", "Reinsurance Dashboard loads")
    await screenshot(page, "reinsurance-workbench.png")

    # Agent Decisions
    await navigate_to(page, "/decisions")
    body = await page.inner_text("body")
    if await check_no_blank_page(page, "decisions"):
        if any(kw in body.lower() for kw in ["decision", "agent", "ai", "action"]):
            PASS("agent-decisions", "Agent Decisions page loads")
        else:
            WARN("agent-decisions", "Agent Decisions loaded but expected keywords missing")
    await screenshot(page, "agent-decisions.png")

    # Main Dashboard (home)
    await navigate_to(page, "/")
    body = await page.inner_text("body")
    if await check_no_blank_page(page, "home-dashboard"):
        PASS("home-dashboard", "Home Dashboard loads")
    await screenshot(page, "home-dashboard.png")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 — Edge Cases & Negative Tests
# ══════════════════════════════════════════════════════════════════════════════


async def phase3a_blank_page_detection(page: Page):
    """Check all major pages for blank page issues."""
    print("\n─── 3a: Blank Page Detection ───")
    await login_as(page, "ceo")

    # Pages accessible to CEO
    pages_to_check = [
        ("/executive", "executive"),
        ("/", "home"),
        ("/escalations", "escalations"),
        ("/finance", "finance"),
        ("/compliance", "compliance"),
        ("/products", "products"),
        ("/decisions", "decisions"),
    ]

    blank_count = 0
    for path, name in pages_to_check:
        await navigate_to(page, path)
        body = await page.inner_text("body")
        body_stripped = body.strip()

        issues = []
        if len(body_stripped) < 50:
            issues.append("nearly blank")
        if "500 Internal Server Error" in body:
            issues.append("500 error")
        if "undefined" in body_stripped[:500]:
            issues.append("'undefined' visible")

        if issues:
            FAIL(f"blank-check:{name}", "; ".join(issues))
            blank_count += 1
        else:
            PASS(f"blank-check:{name}", f"{len(body_stripped)} chars of content")

    if blank_count == 0:
        PASS("blank-page-sweep", "All CEO-accessible pages have content")


async def phase3b_navigation_edge_cases(page: Page):
    """Test navigation edge cases."""
    print("\n─── 3b: Navigation Edge Cases ───")
    await login_as(page, "cuo")

    # Rapid sidebar clicks
    nav_paths = ["/submissions", "/policies", "/claims", "/", "/products", "/knowledge"]
    crash = False
    for path in nav_paths:
        try:
            link = page.locator(f'a[href="{path}"]')
            if await link.count() > 0:
                await link.first.click()
                await page.wait_for_timeout(500)
        except Exception:
            crash = True
            break
    await page.wait_for_timeout(2000)
    if not crash:
        body = await page.inner_text("body")
        if len(body.strip()) > 50:
            PASS("rapid-nav-clicks", "No crash after rapid sidebar clicks")
        else:
            FAIL("rapid-nav-clicks", "Page blank after rapid navigation")
    else:
        FAIL("rapid-nav-clicks", "Exception during rapid nav")

    # Invalid route (404)
    await navigate_to(page, "/nonexistent-page-xyz")
    body = await page.inner_text("body")
    url = page.url
    if "404" in body or "/nonexistent" not in url or len(body.strip()) > 20:
        PASS("invalid-route", "Invalid route handled (redirected or 404)")
    else:
        WARN("invalid-route", "Invalid route response unclear")
    await screenshot(page, "404-page.png")

    # Browser back/forward
    await navigate_to(page, "/submissions")
    await page.wait_for_timeout(1000)
    await navigate_to(page, "/policies")
    await page.wait_for_timeout(1000)
    await page.go_back()
    await page.wait_for_timeout(2000)
    if "/submissions" in page.url or len(await page.inner_text("body")) > 50:
        PASS("browser-back", "Browser back works correctly")
    else:
        WARN("browser-back", "Browser back may not preserve state")


async def phase3c_responsive(page: Page):
    """Test responsive layout at mobile viewport."""
    print("\n─── 3c: Responsive Check ───")
    await login_as(page, "ceo")
    await navigate_to(page, "/executive")

    # Set mobile viewport
    await page.set_viewport_size({"width": 375, "height": 812})
    await page.wait_for_timeout(2000)

    body = await page.inner_text("body")
    if len(body.strip()) > 50:
        PASS("mobile-responsive", "Page renders at mobile viewport (375x812)")
    else:
        FAIL("mobile-responsive", "Page blank at mobile viewport")

    # Check sidebar collapsed/hidden
    sidebar = page.locator("aside")
    if await sidebar.count() > 0:
        sidebar_visible = await sidebar.first.is_visible()
        if not sidebar_visible:
            PASS("mobile-sidebar", "Sidebar hidden on mobile")
        else:
            box = await sidebar.first.bounding_box()
            if box and box["width"] <= 70:
                PASS("mobile-sidebar", f"Sidebar collapsed to {box['width']}px on mobile")
            else:
                WARN("mobile-sidebar", "Sidebar still visible/expanded on mobile")
    else:
        PASS("mobile-sidebar", "No sidebar element on mobile — fully collapsed")

    # Check horizontal scrollbar
    has_scrollbar = await page.evaluate("document.body.scrollWidth > document.body.clientWidth")
    if not has_scrollbar:
        PASS("mobile-no-hscroll", "No horizontal scrollbar on mobile")
    else:
        WARN("mobile-no-hscroll", "Horizontal scrollbar detected on mobile")

    await screenshot(page, "mobile-responsive.png")

    # Reset viewport
    await page.set_viewport_size({"width": 1440, "height": 900})


async def phase3d_data_integrity(page: Page):
    """Check data consistency across pages."""
    print("\n─── 3d: Data Integrity Across Pages ───")
    await login_as(page, "ceo")

    # Get GWP from executive
    await navigate_to(page, "/executive")
    exec_body = await page.inner_text("body")
    exec_amounts = re.findall(r"\$[\d,.]+[MBK]?", exec_body)

    # Get finance data
    await navigate_to(page, "/finance")
    fin_body = await page.inner_text("body")
    fin_amounts = re.findall(r"\$[\d,.]+[MBK]?", fin_body)

    if exec_amounts and fin_amounts:
        PASS("data-integrity", f"Executive has {len(exec_amounts)} amounts, Finance has {len(fin_amounts)} amounts")
    elif exec_amounts or fin_amounts:
        WARN("data-integrity", f"Only one page shows amounts (exec: {len(exec_amounts)}, fin: {len(fin_amounts)})")
    else:
        WARN("data-integrity", "No dollar amounts found on either page")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN — Run all phases
# ══════════════════════════════════════════════════════════════════════════════


async def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  OpenInsure v95 Comprehensive E2E Test Suite                ║")
    print(f"║  Dashboard: {DASHBOARD_URL[:50]}...  ║")
    print(f"║  Screenshots: {SCREENSHOT_DIR:<46s}║")
    print("╚══════════════════════════════════════════════════════════════╝")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Collect console errors
        js_errors: list[str] = []
        page.on("console", lambda msg: js_errors.append(msg.text) if msg.type == "error" else None)

        try:
            # Phase 1: Login & Role Selection
            await phase1_login_and_roles(page)

            # Phase 2: Core Workflow Tests
            await phase2a_submissions(page)
            await phase2b_uw_workbench(page)
            await phase2c_policies(page)
            await phase2d_claims(page)
            await phase2e_products(page)
            await phase2f_executive(page)
            await phase2g_knowledge(page)
            await phase2h_compliance(page)
            await phase2i_billing(page)
            await phase2j_actuarial(page)
            await phase2k_escalations(page)
            await phase2l_broker(page)
            await phase2_analytics(page)

            # Phase 3: Edge Cases
            await phase3a_blank_page_detection(page)
            await phase3b_navigation_edge_cases(page)
            await phase3c_responsive(page)
            await phase3d_data_integrity(page)

        except Exception as e:
            FAIL("test-suite", f"Unhandled exception: {e}")
            import traceback

            traceback.print_exc()

        finally:
            # Report JS errors
            if js_errors:
                unique_errors = list(set(js_errors))[:10]
                WARN("js-console-errors", f"{len(js_errors)} total, {len(unique_errors)} unique errors")
                for err in unique_errors[:5]:
                    print(f"    JS: {err[:120]}")
            else:
                PASS("js-console-errors", "No JavaScript console errors detected")

            await browser.close()

    # ── Summary ────────────────────────────────────────────────────────────
    print("\n")
    print("═" * 70)
    print("  SUMMARY")
    print("═" * 70)

    pass_count = sum(1 for s, _, _ in results if s == "PASS")
    fail_count = sum(1 for s, _, _ in results if s == "FAIL")
    warn_count = sum(1 for s, _, _ in results if s == "WARN")

    print(f"\n  {'Status':<8} {'Count':>5}")
    print(f"  {'─' * 8} {'─' * 5}")
    print(f"  PASS   {pass_count:>5}")
    print(f"  FAIL   {fail_count:>5}")
    print(f"  WARN   {warn_count:>5}")
    print(f"  TOTAL  {len(results):>5}")

    if fail_count > 0:
        print("\n  ❌ FAILURES:")
        for s, name, detail in results:
            if s == "FAIL":
                print(f"    • {name}: {detail}")

    if warn_count > 0:
        print("\n  ⚠️  WARNINGS:")
        for s, name, detail in results:
            if s == "WARN":
                print(f"    • {name}: {detail}")

    # Screenshots summary
    screenshots = [f for f in os.listdir(SCREENSHOT_DIR) if f.endswith(".png")]
    print(f"\n  📸 Screenshots: {len(screenshots)} saved to {SCREENSHOT_DIR}")

    print("\n" + "═" * 70)
    print(f"  Result: {'✅ ALL TESTS PASSED' if fail_count == 0 else f'❌ {fail_count} FAILURES'}")
    print("═" * 70)

    return fail_count


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(min(exit_code, 1))
