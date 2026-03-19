"""
Comprehensive Playwright test for OpenInsure Dashboard.
Tests every persona and every page they can access.
Captures screenshots, console errors, API calls, and data presence.
"""
import json
import time
import os
from playwright.sync_api import sync_playwright

DASHBOARD_URL = "https://openinsure-dashboard.braveriver-f92a9f28.swedencentral.azurecontainerapps.io"
BACKEND_URL = "https://openinsure-backend.braveriver-f92a9f28.swedencentral.azurecontainerapps.io"
SCREENSHOT_DIR = r"C:\Users\urstojki\openinsure\test-screenshots"

os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Persona -> list of (page_label, path) to test
PERSONAS = {
    "Alexandra Reed": {
        "role": "Executive / CEO",
        "pages": [
            ("Dashboard", "/"),
            ("Agent Decisions", "/decisions"),
            ("Escalations", "/escalations"),
            ("Compliance", "/compliance"),
            ("Actuarial Workbench", "/workbench/actuarial"),
            ("Executive Dashboard", "/executive"),
        ],
    },
    "Sarah Chen": {
        "role": "Chief Underwriting Officer",
        "pages": [
            ("Dashboard", "/"),
            ("Submissions", "/submissions"),
            ("Policies", "/policies"),
            ("Claims", "/claims"),
            ("Agent Decisions", "/decisions"),
            ("Escalations", "/escalations"),
            ("Compliance", "/compliance"),
            ("Underwriter Workbench", "/workbench/underwriting"),
            ("Actuarial Workbench", "/workbench/actuarial"),
            ("Reinsurance Workbench", "/workbench/reinsurance"),
            ("Executive Dashboard", "/executive"),
        ],
    },
    "James Wright": {
        "role": "Senior Underwriter",
        "pages": [
            ("Dashboard", "/"),
            ("Submissions", "/submissions"),
            ("Policies", "/policies"),
            ("Escalations", "/escalations"),
            ("Underwriter Workbench", "/workbench/underwriting"),
        ],
    },
    "Maria Lopez": {
        "role": "Underwriting Analyst",
        "pages": [
            ("Dashboard", "/"),
            ("Submissions", "/submissions"),
            ("Policies", "/policies"),
            ("Underwriter Workbench", "/workbench/underwriting"),
        ],
    },
    "David Park": {
        "role": "Chief Claims Officer",
        "pages": [
            ("Dashboard", "/"),
            ("Policies", "/policies"),
            ("Claims List", "/claims"),
            ("Escalations", "/escalations"),
            ("Claims Workbench", "/workbench/claims"),
        ],
    },
    "Lisa Martinez": {
        "role": "Claims Adjuster",
        "pages": [
            ("Dashboard", "/"),
            ("Claims List", "/claims"),
            ("Claims Workbench", "/workbench/claims"),
        ],
    },
    "Michael Torres": {
        "role": "CFO / Finance",
        "pages": [
            ("Dashboard", "/"),
            ("Policies", "/policies"),
            ("Escalations", "/escalations"),
            ("Actuarial Workbench", "/workbench/actuarial"),
            ("Reinsurance Workbench", "/workbench/reinsurance"),
            ("Executive Dashboard", "/executive"),
        ],
    },
    "Anna Kowalski": {
        "role": "Compliance Officer",
        "pages": [
            ("Dashboard", "/"),
            ("Policies", "/policies"),
            ("Claims", "/claims"),
            ("Agent Decisions", "/decisions"),
            ("Compliance", "/compliance"),
            ("Compliance Workbench", "/workbench/compliance"),
        ],
    },
    "Robert Chen": {
        "role": "Head of Product & Data",
        "pages": [
            ("Dashboard", "/"),
            ("Submissions", "/submissions"),
            ("Agent Decisions", "/decisions"),
        ],
    },
    "Emily Davis": {
        "role": "Operations Lead",
        "pages": [
            ("Dashboard", "/"),
            ("Submissions", "/submissions"),
        ],
    },
    "Thomas Anderson": {
        "role": "Broker",
        "pages": [
            ("Broker Portal", "/portal/broker"),
        ],
    },
}

# Track results
results = []
all_unique_pages_tested = set()

LOADING_INDICATORS = [
    "loading...", "loading", "spinner", "skeleton",
    "fetching", "please wait", "no data", "no results",
    "empty", "nothing to show", "error"
]

def sanitize_filename(text):
    return text.replace(" ", "_").replace("/", "_").replace("\\", "_").replace(":", "").replace("&", "and")


def check_page_content(page, page_label):
    """Check if page shows real data vs loading/empty states."""
    info = {"has_data": False, "loading": False, "empty": False, "error_text": None}
    
    try:
        body_text = page.inner_text("body").lower()
    except Exception:
        body_text = ""
    
    # Check for loading indicators
    if "loading..." in body_text or page.locator("[class*='spinner'], [class*='loading'], [class*='skeleton']").count() > 0:
        info["loading"] = True
    
    # Check for empty states
    if "no data" in body_text or "no results" in body_text or "nothing to show" in body_text:
        info["empty"] = True
    
    # Check for error messages
    error_els = page.locator("[class*='error'], [class*='Error'], [role='alert']")
    if error_els.count() > 0:
        try:
            info["error_text"] = error_els.first.inner_text()[:200]
        except Exception:
            pass
    
    # Check for data indicators - tables, charts, cards with numbers, lists
    tables = page.locator("table, [class*='table'], [class*='Table']").count()
    charts = page.locator("canvas, svg[class*='chart'], [class*='chart'], [class*='Chart'], .recharts-wrapper").count()
    cards = page.locator("[class*='card'], [class*='Card'], [class*='stat'], [class*='metric'], [class*='kpi']").count()
    list_items = page.locator("[class*='list-item'], [class*='ListItem'], tr, [class*='row']").count()
    
    # Numbers in the page suggest real data
    import re
    numbers = re.findall(r'\$[\d,]+|\d{1,3}(?:,\d{3})+|\d+\.\d+%|\d+%', body_text)
    
    if tables > 0 or charts > 0 or cards > 2 or list_items > 3 or len(numbers) > 2:
        info["has_data"] = True
    
    info["tables"] = tables
    info["charts"] = charts
    info["cards"] = cards
    info["numbers_found"] = len(numbers)
    
    return info


def test_persona(p, persona_name, persona_config):
    """Test all pages for a given persona."""
    persona_results = []
    role = persona_config["role"]
    pages = persona_config["pages"]
    
    context = p.chromium.launch(headless=True).new_context(
        viewport={"width": 1440, "height": 900}
    )
    page = context.new_page()
    
    # Collect console errors
    console_errors = []
    def handle_console(msg):
        if msg.type == "error":
            console_errors.append(msg.text)
    page.on("console", handle_console)
    
    # Track API requests
    api_requests = []
    def handle_request(request):
        url = request.url
        if "/api/" in url or BACKEND_URL in url:
            api_requests.append({"url": url, "method": request.method})
    page.on("request", handle_request)
    
    api_responses = []
    def handle_response(response):
        url = response.url
        if "/api/" in url or BACKEND_URL in url:
            api_responses.append({
                "url": url,
                "status": response.status,
                "ok": response.ok,
            })
    page.on("response", handle_response)
    
    # Login
    print(f"\n{'='*70}")
    print(f"PERSONA: {persona_name} ({role})")
    print(f"{'='*70}")
    
    page.goto(DASHBOARD_URL, wait_until="networkidle", timeout=30000)
    persona_btn = page.locator(f"button:has-text('{persona_name}')")
    persona_btn.click()
    page.wait_for_load_state("networkidle", timeout=15000)
    time.sleep(1)
    
    print(f"  Logged in. URL: {page.url}")
    
    for page_label, path in pages:
        page_key = f"{persona_name}_{page_label}"
        console_errors.clear()
        api_requests.clear()
        api_responses.clear()
        
        full_url = DASHBOARD_URL + path
        print(f"\n  --- {page_label} ({path}) ---")
        
        try:
            page.goto(full_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)  # Let dynamic content load
            
            # Check if we got redirected (e.g., unauthorized)
            current_url = page.url
            redirected = not current_url.endswith(path)
            if redirected:
                print(f"    REDIRECTED to: {current_url}")
            
            # Take screenshot
            fname = sanitize_filename(f"{persona_name}_{page_label}")
            screenshot_path = os.path.join(SCREENSHOT_DIR, f"{fname}.png")
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"    Screenshot: {fname}.png")
            
            # Check content
            content_info = check_page_content(page, page_label)
            
            # Get page title/heading
            heading = ""
            h1 = page.locator("h1, h2, [class*='title'], [class*='Title']").first
            try:
                heading = h1.inner_text()[:100]
            except Exception:
                pass
            
            result = {
                "persona": persona_name,
                "role": role,
                "page_label": page_label,
                "path": path,
                "loaded": True,
                "redirected": redirected,
                "redirect_url": current_url if redirected else None,
                "heading": heading,
                "content": content_info,
                "console_errors": list(console_errors),
                "api_calls": len(api_requests),
                "api_responses": list(api_responses),
                "api_failures": [r for r in api_responses if not r["ok"]],
                "screenshot": screenshot_path,
            }
            
            status = "✅" if content_info["has_data"] and not content_info["loading"] else "⚠️"
            if redirected or not content_info["has_data"]:
                status = "❌" if redirected else "⚠️"
            if content_info["loading"]:
                status = "⏳"
            
            print(f"    {status} Data: {content_info['has_data']}, Loading: {content_info['loading']}, Empty: {content_info['empty']}")
            print(f"    Tables: {content_info['tables']}, Charts: {content_info['charts']}, Cards: {content_info['cards']}, Numbers: {content_info['numbers_found']}")
            if content_info.get("error_text"):
                print(f"    Error text: {content_info['error_text']}")
            print(f"    API calls: {len(api_requests)}, Failures: {len(result['api_failures'])}")
            if result['api_failures']:
                for f in result['api_failures']:
                    print(f"      FAIL: {f['status']} {f['url']}")
            if console_errors:
                print(f"    Console errors ({len(console_errors)}):")
                for e in console_errors[:5]:
                    print(f"      - {e[:150]}")
            
            persona_results.append(result)
            
        except Exception as ex:
            print(f"    ❌ EXCEPTION: {ex}")
            persona_results.append({
                "persona": persona_name,
                "role": role,
                "page_label": page_label,
                "path": path,
                "loaded": False,
                "error": str(ex),
            })
    
    context.browser.close()
    return persona_results


with sync_playwright() as p:
    for persona_name, persona_config in PERSONAS.items():
        persona_results = test_persona(p, persona_name, persona_config)
        results.extend(persona_results)

# Print summary
print("\n\n" + "=" * 90)
print("SUMMARY REPORT")
print("=" * 90)

print(f"\n{'Persona':<22} {'Role':<28} {'Page':<25} {'Status':<8} {'Data':<6} {'API':<6} {'Errors'}")
print("-" * 130)

for r in results:
    if not r.get("loaded"):
        status = "FAIL"
        data = "N/A"
        api = "N/A"
        errors = r.get("error", "")[:40]
    else:
        if r.get("redirected"):
            status = "REDIR"
        elif r["content"]["loading"]:
            status = "LOAD"
        elif r["content"]["has_data"]:
            status = "OK"
        else:
            status = "EMPTY"
        
        data = "Yes" if r["content"]["has_data"] else "No"
        api_fail_count = len(r.get("api_failures", []))
        api = f"{r['api_calls']}" + (f"/{api_fail_count}F" if api_fail_count else "")
        errors = str(len(r.get("console_errors", [])))
    
    print(f"{r['persona']:<22} {r['role']:<28} {r['page_label']:<25} {status:<8} {data:<6} {api:<6} {errors}")

# Count stats
total = len(results)
ok = sum(1 for r in results if r.get("loaded") and r.get("content", {}).get("has_data") and not r.get("redirected"))
loading = sum(1 for r in results if r.get("loaded") and r.get("content", {}).get("loading"))
empty = sum(1 for r in results if r.get("loaded") and not r.get("content", {}).get("has_data") and not r.get("redirected"))
redir = sum(1 for r in results if r.get("redirected"))
fail = sum(1 for r in results if not r.get("loaded"))
api_issues = sum(1 for r in results if r.get("loaded") and len(r.get("api_failures", [])) > 0)
js_errors = sum(1 for r in results if r.get("loaded") and len(r.get("console_errors", [])) > 0)

print(f"\n{'='*60}")
print(f"TOTALS: {total} page tests")
print(f"  ✅ OK (loaded with data):    {ok}")
print(f"  ⏳ Still loading:             {loading}")
print(f"  ⚠️  Empty (no data):           {empty}")
print(f"  🔀 Redirected:                {redir}")
print(f"  ❌ Failed to load:            {fail}")
print(f"  🔌 API failures:              {api_issues}")
print(f"  ⚡ JS console errors:         {js_errors}")
print(f"{'='*60}")

# Highlight problem pages
problems = [r for r in results if not r.get("loaded") or r.get("redirected") or len(r.get("api_failures", [])) > 0 or len(r.get("console_errors", [])) > 0]
if problems:
    print("\n⚠️  PAGES WITH ISSUES:")
    for r in problems:
        issue = []
        if not r.get("loaded"):
            issue.append(f"Failed: {r.get('error', 'unknown')[:80]}")
        if r.get("redirected"):
            issue.append(f"Redirected to {r.get('redirect_url')}")
        if r.get("api_failures"):
            for f in r["api_failures"]:
                issue.append(f"API {f['status']}: {f['url']}")
        if r.get("console_errors"):
            for e in r["console_errors"][:3]:
                issue.append(f"JS: {e[:100]}")
        print(f"  - {r['persona']} / {r['page_label']} ({r['path']})")
        for i in issue:
            print(f"      {i}")
