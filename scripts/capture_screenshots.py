"""Capture screenshots of all v74 features for the feature guide."""
import asyncio
import os
from playwright.async_api import async_playwright, Page, Browser

DASHBOARD = "https://openinsure-dashboard.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "test-screenshots", "features")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Known IDs from API
POLICY_ID = "FBE31B4F-A91A-43F3-B7FA-7315294DBBDE"
CLAIM_ID = "E987B456-550F-43F3-B410-FA2D6F0DB96C"
SUBMISSION_ID = "9FFA233B-895A-4738-BB26-3C0F12523272"

ROLE_MAP = {
    "Emily Davis": "operations",
    "Sarah Chen": "cuo",
    "David Park": "claims_manager",
    "James Wright": "senior_uw",
    "Alexandra Reed": "ceo",
}


async def login_as_and_goto(page: Page, role_label: str, path: str):
    """Login by setting localStorage role and navigate to target page."""
    role_key = ROLE_MAP.get(role_label, "cuo")
    # Set localStorage on any page first
    await page.goto(f"{DASHBOARD}/login", wait_until="domcontentloaded", timeout=30000)
    await page.evaluate(f"localStorage.setItem('openinsure_role', '{role_key}')")
    # Now navigate to target page (app will read role from localStorage)
    await page.goto(f"{DASHBOARD}{path}", wait_until="networkidle", timeout=30000)
    await page.wait_for_timeout(3000)
    print(f"  Logged in as {role_label} ({role_key}), navigated to {page.url}")


async def screenshot(page: Page, name: str, full_page: bool = True):
    path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
    await page.screenshot(path=path, full_page=full_page)
    print(f"  ✓ Saved: {path}")


async def capture_billing(page: Page):
    """Feature 1: Billing Pipeline - Login as Emily Davis (Operations)."""
    print("\n=== 1. Billing Pipeline ===")
    await login_as_and_goto(page, "Emily Davis", "/finance")
    await screenshot(page, "billing")


async def capture_documents(page: Page):
    """Feature 2: Document Generation - Login as Sarah Chen (CUO)."""
    print("\n=== 2. Document Generation ===")
    await login_as_and_goto(page, "Sarah Chen", f"/policies/{POLICY_ID}")
    await screenshot(page, "document-generation")
    # Look for declaration/certificate buttons
    for btn_text in ["Declaration", "Certificate", "Download", "View"]:
        btn = page.locator(f"text=/{btn_text}/i").first
        try:
            if await btn.is_visible(timeout=2000):
                print(f"  Found button: {btn_text}")
                await btn.click()
                await page.wait_for_timeout(2000)
                await screenshot(page, "document-generation-clicked")
                break
        except Exception:
            continue


async def capture_subrogation(page: Page):
    """Feature 3: Claims Subrogation - Login as David Park (Claims Manager)."""
    print("\n=== 3. Claims Subrogation ===")
    await login_as_and_goto(page, "David Park", f"/claims/{CLAIM_ID}")
    # Look for Subrogation tab
    tabs = page.locator("text=/[Ss]ubrogation/")
    if await tabs.count() > 0:
        await tabs.first.click()
        await page.wait_for_timeout(2000)
        print("  Clicked Subrogation tab")
    await screenshot(page, "claims-subrogation")


async def capture_enrichment(page: Page):
    """Feature 4: Data Enrichment - Login as Sarah Chen."""
    print("\n=== 4. Data Enrichment ===")
    await login_as_and_goto(page, "Sarah Chen", f"/submissions/{SUBMISSION_ID}")
    # Look for enrichment section
    enrichment = page.locator("text=/[Ee]nrich/")
    if await enrichment.count() > 0:
        print(f"  Found enrichment elements: {await enrichment.count()}")
    await screenshot(page, "data-enrichment")


async def capture_uw_analytics(page: Page):
    """Feature 5: UW Analytics."""
    print("\n=== 5. UW Analytics ===")
    await login_as_and_goto(page, "Sarah Chen", "/analytics/underwriting")
    await page.wait_for_timeout(2000)
    await screenshot(page, "uw-analytics")


async def capture_claims_analytics(page: Page):
    """Feature 6: Claims Analytics."""
    print("\n=== 6. Claims Analytics ===")
    await login_as_and_goto(page, "David Park", "/analytics/claims")
    await page.wait_for_timeout(2000)
    await screenshot(page, "claims-analytics")


async def capture_ai_insights(page: Page):
    """Feature 7: AI Insights - Login as Alexandra Reed (CEO)."""
    print("\n=== 7. AI Insights ===")
    await login_as_and_goto(page, "Alexandra Reed", "/executive")
    # Scroll down to find AI Insights section
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await page.wait_for_timeout(2000)
    await screenshot(page, "ai-insights", full_page=True)


async def capture_renewals(page: Page):
    """Feature 8: Renewal Scheduling."""
    print("\n=== 8. Renewal Scheduling ===")
    # Try the UW workbench first (Sarah Chen has access), look for renewals
    await login_as_and_goto(page, "Sarah Chen", "/policies")
    await page.wait_for_timeout(2000)
    # Look for renewal tab or section on policies page
    renewal_tab = page.locator("text=/[Rr]enewal/")
    count = await renewal_tab.count()
    print(f"  Found {count} renewal elements")
    if count > 0:
        await renewal_tab.first.click()
        await page.wait_for_timeout(2000)
        print("  Clicked Renewals tab/link")
    await screenshot(page, "renewals")


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        page = await context.new_page()

        await capture_billing(page)
        await capture_documents(page)
        await capture_subrogation(page)
        await capture_enrichment(page)
        await capture_uw_analytics(page)
        await capture_claims_analytics(page)
        await capture_ai_insights(page)
        await capture_renewals(page)

        await browser.close()
        print("\n✅ All screenshots captured!")


if __name__ == "__main__":
    asyncio.run(main())
