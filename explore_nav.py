"""Explore navigation structure after logging in as each persona."""
import json
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "https://openinsure-dashboard.braveriver-f92a9f28.swedencentral.azurecontainerapps.io"
SCREENSHOT_DIR = r"C:\Users\urstojki\openinsure\test-screenshots"

PERSONAS = [
    "Alexandra Reed",
    "Sarah Chen",
    "James Wright",
    "Maria Lopez",
    "David Park",
    "Lisa Martinez",
    "Michael Torres",
    "Anna Kowalski",
    "Robert Chen",
    "Emily Davis",
    "Thomas Anderson",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    for persona_name in PERSONAS:
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        
        print(f"\n{'='*60}")
        print(f"PERSONA: {persona_name}")
        print(f"{'='*60}")
        
        # Go to login
        page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=30000)
        
        # Click persona button
        persona_btn = page.locator(f"button:has-text('{persona_name}')")
        if persona_btn.count() == 0:
            print(f"  ERROR: Could not find button for {persona_name}")
            context.close()
            continue
        
        persona_btn.click()
        page.wait_for_load_state("networkidle", timeout=15000)
        
        print(f"  URL after login: {page.url}")
        
        # Find all nav links
        nav_links = page.query_selector_all("nav a, aside a, [class*='nav'] a, [class*='sidebar'] a, [class*='menu'] a")
        print(f"  Found {len(nav_links)} nav links:")
        seen = set()
        for link in nav_links:
            text = link.inner_text().strip()
            href = link.get_attribute("href") or ""
            if text and text not in seen:
                seen.add(text)
                print(f"    - '{text}' -> {href}")
        
        # Also check for any links in the page
        all_links = page.query_selector_all("a[href]")
        print(f"  All links ({len(all_links)}):")
        seen2 = set()
        for link in all_links:
            href = link.get_attribute("href") or ""
            text = link.inner_text().strip()[:60]
            if href and href not in seen2 and href != "#":
                seen2.add(href)
                print(f"    - '{text}' -> {href}")
        
        context.close()
    
    browser.close()
