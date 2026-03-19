"""Explore the dashboard to understand login flow and page structure."""
import json
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "https://openinsure-dashboard.braveriver-f92a9f28.swedencentral.azurecontainerapps.io"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Navigate to login page
    page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=30000)
    page.screenshot(path=r"C:\Users\urstojki\openinsure\test-screenshots\00-login-page.png", full_page=True)
    
    # Get page content to understand structure
    title = page.title()
    print(f"Page title: {title}")
    print(f"URL: {page.url}")
    
    # Find all buttons and clickable elements
    buttons = page.query_selector_all("button")
    print(f"\nFound {len(buttons)} buttons:")
    for b in buttons:
        text = b.inner_text().strip()
        if text:
            print(f"  - '{text}'")
    
    # Find role selectors, cards, or dropdowns
    selects = page.query_selector_all("select")
    print(f"\nFound {len(selects)} select elements")
    for s in selects:
        options = s.query_selector_all("option")
        for o in options:
            print(f"  Option: '{o.inner_text().strip()}'")
    
    # Check for links
    links = page.query_selector_all("a")
    print(f"\nFound {len(links)} links:")
    for l in links[:20]:
        text = l.inner_text().strip()
        href = l.get_attribute("href") or ""
        if text:
            print(f"  - '{text}' -> {href}")
    
    # Check for role-related elements
    role_elements = page.query_selector_all("[data-role], [role], .role, .persona")
    print(f"\nFound {len(role_elements)} role-related elements")
    
    # Get the page HTML structure (first 5000 chars)
    html = page.content()
    print(f"\nPage HTML length: {len(html)}")
    # Print relevant parts
    if "role" in html.lower() or "persona" in html.lower():
        print("Page contains 'role' or 'persona' text")
    
    # Look for cards or list items that might be role selectors
    cards = page.query_selector_all("[class*='card'], [class*='Card'], [class*='role'], [class*='persona'], [class*='avatar']")
    print(f"\nFound {len(cards)} card/role elements")
    for c in cards[:10]:
        text = c.inner_text().strip()[:100]
        cls = c.get_attribute("class") or ""
        print(f"  - class='{cls}' text='{text}'")
    
    # Get all visible text
    body_text = page.inner_text("body")
    print(f"\n--- Page text (first 3000 chars) ---")
    print(body_text[:3000])
    
    browser.close()
