#!/usr/bin/env python3
"""
OpenInsure Functional Test Suite v95
Comprehensive end-to-end tests against the LIVE deployed backend.
"""

import requests
import json
import uuid
import time
import sys
from datetime import datetime, timedelta

# ── Configuration ──────────────────────────────────────────────────────────
BASE_URL = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
API_V1 = f"{BASE_URL}/api/v1"
HEADERS = {
    "X-API-Key": "openinsure-dev-key-2024",
    "Content-Type": "application/json",
}
TIMEOUT = 30

# ── Result Tracking ────────────────────────────────────────────────────────
results = []  # list of (category, name, status, detail)
PASS, FAIL, WARN = "PASS", "FAIL", "WARN"


def log(category, name, status, detail=""):
    results.append((category, name, status, detail))
    icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "WARN": "[WARN]"}[status]
    print(f"  {icon} {name} — {detail}")


def req(method, path, expected=None, category="", test_name="", **kwargs):
    """Helper: make request, log result, return response."""
    url = f"{API_V1}{path}" if not path.startswith("http") else path
    kwargs.setdefault("headers", HEADERS)
    kwargs.setdefault("timeout", TIMEOUT)
    try:
        r = getattr(requests, method)(url, **kwargs)
    except Exception as e:
        log(category, test_name, FAIL, f"Request exception: {e}")
        return None
    status_code = r.status_code
    if expected is not None:
        if isinstance(expected, (list, tuple)):
            if status_code in expected:
                log(category, test_name, PASS, f"HTTP {status_code}")
            else:
                log(category, test_name, FAIL,
                    f"HTTP {status_code} — Expected one of {expected}")
        else:
            if status_code == expected:
                log(category, test_name, PASS, f"HTTP {status_code}")
            else:
                log(category, test_name, FAIL,
                    f"HTTP {status_code} — Expected {expected}")
    return r


# ══════════════════════════════════════════════════════════════════════════
# 1. SUBMISSION LIFECYCLE
# ══════════════════════════════════════════════════════════════════════════
def test_submissions():
    CAT = "Submission"
    print(f"\n{'='*70}\n  1. SUBMISSION LIFECYCLE\n{'='*70}")

    # ── Happy path ──
    payload = {
        "applicant_name": "FuncTest Cyber Corp",
        "applicant_email": "qa@functest.com",
        "channel": "api",
        "line_of_business": "cyber",
        "risk_data": {
            "annual_revenue": 5000000,
            "employee_count": 50,
            "industry": "Technology",
        },
        "cyber_risk_data": {
            "requested_limit": 1000000,
            "requested_deductible": 10000,
            "has_mfa": True,
            "has_endpoint_protection": True,
            "has_backup_strategy": True,
            "has_incident_response_plan": True,
            "prior_incidents": 0,
            "security_maturity_score": 75,
        },
        "effective_date": "2026-01-01",
        "expiration_date": "2027-01-01",
    }
    r = req("post", "/submissions", [200, 201], CAT, "Create cyber submission",
            json=payload)
    if not r or r.status_code not in (200, 201):
        print("  !! Cannot continue submission lifecycle without create")
        return None, None
    sub = r.json()
    sub_id = sub.get("id")
    print(f"    → Submission ID: {sub_id}")

    # GET verify
    r = req("get", f"/submissions/{sub_id}", [200], CAT,
            "GET created submission")
    if r and r.status_code == 200:
        body = r.json()
        if body.get("applicant_name") != "FuncTest Cyber Corp":
            log(CAT, "Verify applicant_name", FAIL,
                f"Got: {body.get('applicant_name')}")
        else:
            log(CAT, "Verify applicant_name", PASS, "Matches")

    # Triage
    r = req("post", f"/submissions/{sub_id}/triage", [200, 202], CAT,
            "Triage submission")
    if r and r.status_code in (200, 202):
        triage_body = r.json()
        print(f"    → Post-triage status: {triage_body.get('status', 'N/A')}")

    # Underwrite (may be /underwrite or handled by triage)
    r_uw = req("post", f"/submissions/{sub_id}/underwrite", [200, 202, 404, 405],
               CAT, "Underwrite submission")
    if r_uw and r_uw.status_code in (404, 405):
        log(CAT, "Underwrite endpoint existence", WARN,
            f"HTTP {r_uw.status_code} — endpoint may not exist separately")

    # Quote
    r = req("post", f"/submissions/{sub_id}/quote", [200, 202], CAT,
            "Generate quote")
    if r and r.status_code in (200, 202):
        quote_body = r.json()
        premium = quote_body.get("quoted_premium") or quote_body.get("premium")
        print(f"    → Quoted premium: {premium}")

    # Bind
    r = req("post", f"/submissions/{sub_id}/bind", [200, 201, 202], CAT,
            "Bind to policy")
    policy_id = None
    if r and r.status_code in (200, 201, 202):
        bind_body = r.json()
        policy_id = bind_body.get("policy_id") or bind_body.get("id")
        print(f"    → Policy ID: {policy_id}")

    # Verify policy created
    r = req("get", "/policies", [200], CAT, "GET /policies list")
    if r and r.status_code == 200:
        policies = r.json()
        if isinstance(policies, list):
            log(CAT, "Policies list is array", PASS, f"{len(policies)} policies")
        elif isinstance(policies, dict):
            items = policies.get("items") or policies.get("policies") or []
            log(CAT, "Policies list", PASS, f"{len(items)} policies")

    # ── Edge Cases ──
    print("\n  --- Submission Edge Cases ---")

    # Missing required fields
    r = req("post", "/submissions", [400, 422], CAT,
            "Submit missing required fields", json={})

    # Extreme revenue $0
    payload_zero = {
        "applicant_name": "Zero Revenue Inc",
        "risk_data": {"annual_revenue": 0, "employee_count": 1, "industry": "Tech"},
    }
    r = req("post", "/submissions", [200, 201, 400, 422], CAT,
            "Submit $0 revenue", json=payload_zero)
    if r and r.status_code in (200, 201):
        log(CAT, "$0 revenue accepted", WARN,
            "Accepted — may need appetite check at triage")

    # Extreme revenue $999B
    payload_huge = {
        "applicant_name": "MegaCorp",
        "risk_data": {"annual_revenue": 999000000000, "employee_count": 500000,
                      "industry": "Conglomerate"},
    }
    r = req("post", "/submissions", [200, 201, 400, 422], CAT,
            "Submit $999B revenue", json=payload_huge)

    # Double triage
    if sub_id:
        r = req("post", f"/submissions/{sub_id}/triage", [200, 202, 409, 400],
                CAT, "Double-triage (idempotency)")

    # Quote before underwriting (new submission)
    payload_new = {
        "applicant_name": "Quote Before UW Test",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 1000000, "employee_count": 10,
                      "industry": "Retail"},
    }
    r2 = req("post", "/submissions", [200, 201], CAT,
             "Create submission for quote-before-UW test", json=payload_new)
    if r2 and r2.status_code in (200, 201):
        new_id = r2.json().get("id")
        r = req("post", f"/submissions/{new_id}/quote", [400, 409, 422, 200],
                CAT, "Quote un-triaged submission")
        if r and r.status_code == 200:
            log(CAT, "Quote without triage allowed", WARN,
                "No state guard — quote succeeded on received submission")

    # Bind already-bound
    if sub_id:
        r = req("post", f"/submissions/{sub_id}/bind", [409, 400, 200], CAT,
                "Bind already-bound submission")
        if r and r.status_code == 200:
            log(CAT, "Double-bind allowed", WARN, "Expected 409, got 200")

    return sub_id, policy_id


# ══════════════════════════════════════════════════════════════════════════
# 2. CLAIMS LIFECYCLE
# ══════════════════════════════════════════════════════════════════════════
def test_claims(policy_id):
    CAT = "Claims"
    print(f"\n{'='*70}\n  2. CLAIMS LIFECYCLE\n{'='*70}")

    if not policy_id:
        log(CAT, "Prerequisites", WARN, "No policy_id from submissions — using dummy")
        policy_id = "test-policy-missing"

    # ── Happy path ──
    claim_payload = {
        "policy_id": policy_id,
        "claim_type": "data_breach",
        "description": "Functional test: ransomware attack encrypted production DBs",
        "date_of_loss": "2026-06-15",
        "reported_by": "QA CISO",
        "contact_email": "qa-ciso@functest.com",
    }
    r = req("post", "/claims", [200, 201], CAT, "File claim (FNOL)",
            json=claim_payload)
    claim_id = None
    if r and r.status_code in (200, 201):
        claim = r.json()
        claim_id = claim.get("id")
        print(f"    → Claim ID: {claim_id}")
        print(f"    → Claim status: {claim.get('status')}")

    if not claim_id:
        print("  !! Cannot continue claims lifecycle")
        return

    # GET verify
    r = req("get", f"/claims/{claim_id}", [200], CAT, "GET created claim")

    # Assess (may be /process or /assess)
    r = req("post", f"/claims/{claim_id}/assess", [200, 202, 404, 405], CAT,
            "Assess claim")
    if r and r.status_code in (404, 405):
        log(CAT, "Assess endpoint", WARN, "Not found — trying /process")
        r = req("post", f"/claims/{claim_id}/process", [200, 202], CAT,
                "Process claim (AI)")

    # Set reserve
    reserve_payload = {
        "category": "indemnity",
        "amount": 50000.00,
        "currency": "USD",
        "notes": "Initial reserve estimate from functional test",
    }
    r = req("post", f"/claims/{claim_id}/reserve", [200, 201], CAT,
            "Set reserve", json=reserve_payload)
    if r and r.status_code in (200, 201):
        res_body = r.json()
        print(f"    → Total reserved: {res_body.get('total_reserved', 'N/A')}")

    # Also try PUT update (as user spec'd)
    update_payload = {"description": "Updated: confirmed ransomware — full scope"}
    r = req("put", f"/claims/{claim_id}", [200], CAT,
            "Update claim via PUT", json=update_payload)

    # Settle / close
    r = req("post", f"/claims/{claim_id}/settle", [200, 404, 405], CAT,
            "Settle claim")
    if r and r.status_code in (404, 405):
        log(CAT, "Settle endpoint", WARN, "Not found — trying payment + close")
        # Make payment first
        pay_payload = {
            "payee": "FuncTest Payee Corp",
            "amount": 45000.00,
            "category": "indemnity",
            "reference": "FT-PAY-001",
        }
        req("post", f"/claims/{claim_id}/payment", [200, 201], CAT,
            "Record payment", json=pay_payload)
        # Close
        req("post", f"/claims/{claim_id}/close", [200], CAT,
            "Close claim")

    # ── Edge Cases ──
    print("\n  --- Claims Edge Cases ---")

    # Claim against non-existent policy
    bad_claim = {
        "policy_id": f"nonexistent-{uuid.uuid4()}",
        "claim_type": "ransomware",
        "description": "Test against fake policy",
        "date_of_loss": "2026-06-15",
        "reported_by": "QA",
    }
    r = req("post", "/claims", [400, 404, 422, 200, 201, 500], CAT,
            "Claim against non-existent policy", json=bad_claim)
    if r and r.status_code == 500:
        log(CAT, "Non-existent policy → 500", FAIL,
            "Server error instead of validation — no FK check on policy_id")
    elif r and r.status_code in (200, 201):
        log(CAT, "Non-existent policy accepted", WARN,
            "No FK validation — claim created for fake policy")

    # Future loss date
    future_claim = {
        "policy_id": policy_id,
        "claim_type": "data_breach",
        "description": "Future loss date test",
        "date_of_loss": "2030-12-31",
        "reported_by": "QA",
    }
    r = req("post", "/claims", [400, 422, 200, 201], CAT,
            "Claim with future loss_date", json=future_claim)
    if r and r.status_code in (200, 201):
        log(CAT, "Future loss_date accepted", WARN,
            "No date validation — future date accepted")

    # Double-close
    if claim_id:
        r = req("post", f"/claims/{claim_id}/close", [409, 400, 422, 200], CAT,
                "Double-close claim")
        if r and r.status_code == 200:
            log(CAT, "Double-close allowed", WARN, "Expected 409, got 200")


# ══════════════════════════════════════════════════════════════════════════
# 3. PRODUCT MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════
def test_products():
    CAT = "Products"
    print(f"\n{'='*70}\n  3. PRODUCT MANAGEMENT\n{'='*70}")

    # ── Test 1: Create product (known bug: product_code NOT NULL) ──
    product_payload = {
        "name": f"PI Test Product {uuid.uuid4().hex[:6]}",
        "product_line": "professional_indemnity",
        "description": "Functional test PI product",
        "version": "1.0",
        "coverages": [
            {
                "name": "Professional Liability",
                "description": "Covers professional negligence",
                "default_limit": 1000000,
                "max_limit": 5000000,
                "default_deductible": 10000,
                "is_optional": False,
            },
            {
                "name": "Defense Costs",
                "description": "Legal defense coverage",
                "default_limit": 500000,
                "max_limit": 2000000,
                "default_deductible": 5000,
                "is_optional": True,
            },
        ],
        "rating_rules": {
            "base_rate": 0.02,
            "factors": ["industry", "revenue_band", "claims_history"],
        },
        "rating_factor_tables": [
            {
                "name": "industry",
                "description": "Industry risk multipliers",
                "entries": [
                    {"key": "technology", "multiplier": 0.90, "description": "Tech"},
                    {"key": "healthcare", "multiplier": 1.20, "description": "Healthcare"},
                    {"key": "finance", "multiplier": 1.10, "description": "Finance"},
                ],
            }
        ],
        "appetite_rules": [
            {
                "name": "revenue_range",
                "field": "annual_revenue",
                "operator": "between",
                "value": [500000, 500000000],
                "description": "Mid-market only",
            }
        ],
        "authority_limits": {
            "max_auto_bind_premium": 50000,
            "max_auto_bind_limit": 2000000,
        },
        "territories": ["US", "CA", "GB"],
    }
    r = req("post", "/products", [200, 201, 500], CAT, "Create PI product",
            json=product_payload)
    prod_id = None
    if r and r.status_code == 500:
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if "product_code" in str(body):
            log(CAT, "Create product — product_code bug", FAIL,
                "500: DB requires product_code but API doesn't auto-generate it")
        else:
            log(CAT, "Create product — unexpected 500", FAIL, r.text[:200])
    elif r and r.status_code in (200, 201):
        prod = r.json()
        prod_id = prod.get("id")
        print(f"    → Product ID: {prod_id}")

    # ── Use existing product for lifecycle tests ──
    r = req("get", "/products", [200], CAT, "List existing products")
    existing_prod_id = None
    existing_prod_status = None
    prod_list_raw = []
    if r and r.status_code == 200:
        prods = r.json()
        if isinstance(prods, list):
            prod_list_raw = prods
        elif isinstance(prods, dict):
            prod_list_raw = prods.get("items") or prods.get("products") or []
        if prod_list_raw:
            log(CAT, "Products list", PASS, f"{len(prod_list_raw)} products found")
            for p in prod_list_raw:
                if p.get("status") == "draft":
                    existing_prod_id = p["id"]
                    existing_prod_status = "draft"
                    break
            if not existing_prod_id:
                existing_prod_id = prod_list_raw[0]["id"]
                existing_prod_status = prod_list_raw[0].get("status")
            print(f"    → Using existing product: {existing_prod_id} (status: {existing_prod_status})")
        else:
            log(CAT, "Products list", WARN, "No products found")

    test_prod = prod_id or existing_prod_id
    if not test_prod:
        print("  !! No products available for lifecycle testing")
        return

    # GET verify
    r = req("get", f"/products/{test_prod}", [200], CAT, "GET product details")
    if r and r.status_code == 200:
        body = r.json()
        log(CAT, "Verify product status", PASS, f"Status: {body.get('status')}")

    # Update (only if draft or active)
    update_payload = {
        "description": f"Updated by func test at {datetime.now().isoformat()}",
    }
    r = req("put", f"/products/{test_prod}", [200, 409], CAT, "Update product",
            json=update_payload)

    # Verify update persisted (known past bug)
    if r and r.status_code == 200:
        r2 = req("get", f"/products/{test_prod}", [200], CAT,
                 "Verify update PERSISTED")
        if r2 and r2.status_code == 200:
            body = r2.json()
            desc = body.get("description", "")
            if "Updated by func test" in desc:
                log(CAT, "Update persistence check", PASS,
                    "Description updated correctly")
            else:
                log(CAT, "Update persistence check", FAIL,
                    f"Not persisted: {desc[:80]}")

    # Publish (only if draft)
    if existing_prod_status == "draft":
        r = req("post", f"/products/{test_prod}/publish", [200, 202, 409], CAT,
                "Publish product")
        if r and r.status_code in (200, 202):
            pub_body = r.json()
            print(f"    → Post-publish status: {pub_body.get('status', 'N/A')}")

    # Rate with risk data (find an active product)
    rate_payload = {
        "risk_data": {
            "annual_revenue": 5000000,
            "employee_count": 50,
            "industry": "technology",
            "has_mfa": True,
            "security_maturity_score": 80,
            "years_in_business": 10,
        }
    }
    # Find active product for rating
    active_prod = None
    for p in prod_list_raw:
        if p.get("status") == "active":
            active_prod = p["id"]
            break
    if not active_prod and prod_list_raw:
        active_prod = prod_list_raw[0]["id"]

    rate_target = active_prod or test_prod
    r = req("post", f"/products/{rate_target}/rate", [200, 409], CAT,
            "Rate with risk data", json=rate_payload)
    if r and r.status_code == 200:
        rate_body = r.json()
        premium = rate_body.get("premium") or rate_body.get("total_premium")
        print(f"    → Calculated premium: {premium}")
        if premium and premium > 0:
            log(CAT, "Premium is non-flat", PASS, f"Premium: {premium}")
        else:
            log(CAT, "Premium is non-flat", WARN, f"Premium: {premium}")

    # Create version
    r = req("post", f"/products/{test_prod}/versions", [200, 201, 409], CAT,
            "Create new version")
    if r and r.status_code in (200, 201):
        ver_body = r.json()
        ver_status = ver_body.get("status")
        print(f"    → New version status: {ver_status}")

    # List coverages
    r = req("get", f"/products/{test_prod}/coverages", [200], CAT,
            "List coverages")
    if r and r.status_code == 200:
        covs = r.json()
        if isinstance(covs, list):
            log(CAT, "Coverages returned", PASS, f"{len(covs)} coverages")
        elif isinstance(covs, dict):
            items = covs.get("coverages") or covs.get("items") or []
            log(CAT, "Coverages returned", PASS, f"{len(items)} coverages")

    # Performance
    r = req("get", f"/products/{test_prod}/performance", [200], CAT,
            "Get performance metrics")

    # ── Edge Cases ──
    print("\n  --- Product Edge Cases ---")

    # Rate a draft product
    draft_prods = [p for p in prod_list_raw if p.get("status") == "draft"]
    if draft_prods:
        r = req("post", f"/products/{draft_prods[0]['id']}/rate", [409, 400, 200],
                CAT, "Rate draft product", json=rate_payload)
        if r and r.status_code == 200:
            log(CAT, "Draft product ratable", WARN,
                "Expected 409 — draft products should not be ratable")
    else:
        log(CAT, "Rate draft product", WARN, "No draft products to test")

    # Publish already-active
    if active_prod:
        r = req("post", f"/products/{active_prod}/publish", [409, 400, 200], CAT,
                "Publish already-active product")
        if r and r.status_code == 200:
            log(CAT, "Double-publish allowed", WARN, "Expected 409, got 200")

    # Empty name
    r = req("post", "/products", [400, 422, 500], CAT,
            "Create product with empty name",
            json={"name": "", "product_line": "cyber"})
    if r and r.status_code == 500:
        log(CAT, "Empty name → 500", WARN, "Should return 422 validation error")

    # Rate with missing risk data
    if rate_target:
        r = req("post", f"/products/{rate_target}/rate", [200, 400, 422], CAT,
                "Rate with empty risk_data", json={"risk_data": {}})
        if r and r.status_code == 200:
            fb_body = r.json()
            fb_premium = fb_body.get("premium") or fb_body.get("total_premium")
            log(CAT, "Rate fallback behavior", WARN,
                f"Accepted with empty risk_data — premium: {fb_premium}")


# ══════════════════════════════════════════════════════════════════════════
# 4. KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════
def test_knowledge():
    CAT = "Knowledge"
    print(f"\n{'='*70}\n  4. KNOWLEDGE BASE\n{'='*70}")

    req("get", "/knowledge/products", [200], CAT, "GET knowledge/products")
    # guidelines endpoint doesn't exist; use search
    r = req("get", "/knowledge/guidelines", [200, 404], CAT,
            "GET knowledge/guidelines")
    if r and r.status_code == 404:
        log(CAT, "Guidelines endpoint missing", WARN,
            "404 — not implemented, use /knowledge/search?q=guidelines")
    req("get", "/knowledge/search?q=underwriting+guidelines", [200], CAT,
        "Search knowledge for guidelines")
    req("get", "/knowledge/sync-status", [200], CAT, "GET knowledge/sync-status")
    req("post", "/admin/sync-products", [200, 202], CAT, "POST admin/sync-products")


# ══════════════════════════════════════════════════════════════════════════
# 5. COMPLIANCE & REGULATORY
# ══════════════════════════════════════════════════════════════════════════
def test_compliance():
    CAT = "Compliance"
    print(f"\n{'='*70}\n  5. COMPLIANCE & REGULATORY\n{'='*70}")

    req("get", "/compliance/decisions", [200], CAT, "GET decisions")
    req("get", "/compliance/audit", [200, 404], CAT, "GET audit (alt path)")
    req("get", "/compliance/audit-trail", [200, 404], CAT, "GET audit-trail")
    req("get", "/compliance/inventory", [200, 404], CAT, "GET inventory (alt)")
    req("get", "/compliance/system-inventory", [200, 404], CAT, "GET system-inventory")

    # FRIA
    fria_payload = {
        "system_name": "OpenInsure AI Underwriting",
        "risk_level": "high",
    }
    r = req("post", "/compliance/fria/generate", [200, 201, 404], CAT,
            "Generate FRIA", json=fria_payload)
    if r and r.status_code == 404:
        log(CAT, "FRIA endpoint", WARN, "Not found at /fria/generate")

    # Transparency report
    r = req("post", "/compliance/transparency-report", [200, 201, 404], CAT,
            "Art 13 transparency report", json={})
    if r and r.status_code == 404:
        # Try bias-report as alternative
        bias_payload = {
            "decision_type": "underwriting",
            "date_from": "2025-01-01",
            "date_to": "2025-12-31",
        }
        req("post", "/compliance/bias-report", [200], CAT,
            "Bias report (alt)", json=bias_payload)

    # Tech doc
    req("post", "/compliance/tech-doc", [200, 201, 404], CAT,
        "Art 11 tech doc", json={})

    # Conformity checklist
    req("get", "/compliance/conformity-checklist", [200, 404], CAT,
        "Art 43 conformity checklist")

    # Schedule P
    req("get", "/compliance/schedule-p", [200, 404], CAT, "NAIC Schedule P export")


# ══════════════════════════════════════════════════════════════════════════
# 6. BILLING & FINANCE
# ══════════════════════════════════════════════════════════════════════════
def test_billing():
    CAT = "Billing"
    print(f"\n{'='*70}\n  6. BILLING & FINANCE\n{'='*70}")

    req("get", "/billing/summary", [200, 404], CAT, "GET billing summary")
    req("get", "/billing/premium-summary", [200, 404], CAT, "GET premium summary")
    req("get", "/billing/cashflow", [200, 404], CAT, "GET cashflow")
    req("get", "/billing/commissions", [200, 404], CAT, "GET commissions")

    # Also test the account-based billing API
    req("get", "/billing/accounts", [200, 404, 405], CAT, "GET billing accounts")


# ══════════════════════════════════════════════════════════════════════════
# 7. REINSURANCE
# ══════════════════════════════════════════════════════════════════════════
def test_reinsurance():
    CAT = "Reinsurance"
    print(f"\n{'='*70}\n  7. REINSURANCE\n{'='*70}")

    req("get", "/reinsurance/treaties", [200], CAT, "GET treaties")
    req("get", "/reinsurance/cessions", [200], CAT, "GET cessions")
    r = req("get", "/reinsurance/capacity", [200, 404], CAT, "GET capacity")
    if r and r.status_code == 404:
        log(CAT, "Capacity endpoint missing", WARN, "404 — not implemented")


# ══════════════════════════════════════════════════════════════════════════
# 8. ACTUARIAL
# ══════════════════════════════════════════════════════════════════════════
def test_actuarial():
    CAT = "Actuarial"
    print(f"\n{'='*70}\n  8. ACTUARIAL\n{'='*70}")

    req("get", "/actuarial/reserves", [200], CAT, "GET reserves")
    r = req("get", "/actuarial/triangles", [200, 404], CAT, "GET loss triangles")
    if r and r.status_code == 404:
        log(CAT, "Triangles endpoint missing", WARN, "404 — not implemented")
    req("get", "/actuarial/rate-adequacy", [200], CAT, "GET rate adequacy")


# ══════════════════════════════════════════════════════════════════════════
# 9. ESCALATIONS
# ══════════════════════════════════════════════════════════════════════════
def test_escalations():
    CAT = "Escalations"
    print(f"\n{'='*70}\n  9. ESCALATIONS\n{'='*70}")

    req("get", "/escalations/count", [200], CAT, "GET escalation count")
    req("get", "/escalations", [200], CAT, "GET escalations list")


# ══════════════════════════════════════════════════════════════════════════
# 10. METRICS & ANALYTICS
# ══════════════════════════════════════════════════════════════════════════
def test_metrics():
    CAT = "Metrics"
    print(f"\n{'='*70}\n  10. METRICS & ANALYTICS\n{'='*70}")

    req("get", "/metrics/summary", [200], CAT, "GET summary")
    req("get", "/metrics/executive", [200], CAT, "GET executive dashboard")
    req("get", "/metrics/pipeline", [200], CAT, "GET pipeline")


# ══════════════════════════════════════════════════════════════════════════
# 11. BROKER PORTAL
# ══════════════════════════════════════════════════════════════════════════
def test_broker():
    CAT = "Broker"
    print(f"\n{'='*70}\n  11. BROKER PORTAL\n{'='*70}")

    req("get", "/broker/submissions", [200], CAT, "GET broker submissions")
    req("get", "/broker/policies", [200], CAT, "GET broker policies")
    req("get", "/broker/claims", [200], CAT, "GET broker claims")


# ══════════════════════════════════════════════════════════════════════════
# 12. CROSS-CUTTING EDGE CASES
# ══════════════════════════════════════════════════════════════════════════
def test_cross_cutting():
    CAT = "CrossCutting"
    print(f"\n{'='*70}\n  12. CROSS-CUTTING EDGE CASES\n{'='*70}")

    # Invalid API key
    bad_headers = {"X-API-Key": "invalid-key-12345", "Content-Type": "application/json"}
    r = req("get", "/submissions", [401, 403, 200], CAT, "Invalid API key",
            headers=bad_headers)
    if r and r.status_code == 200:
        log(CAT, "Auth bypass — invalid key", FAIL,
            "SECURITY: Invalid API key returns 200 — no auth enforcement")

    # Missing API key
    no_auth_headers = {"Content-Type": "application/json"}
    r = req("get", "/submissions", [401, 403, 422, 200], CAT, "Missing API key",
            headers=no_auth_headers)
    if r and r.status_code == 200:
        log(CAT, "Auth bypass — no key", FAIL,
            "SECURITY: Missing API key returns 200 — no auth enforcement")

    # Non-existent entity
    fake_id = str(uuid.uuid4())
    req("get", f"/submissions/{fake_id}", [404], CAT,
        "GET non-existent submission")
    req("get", f"/claims/{fake_id}", [404], CAT,
        "GET non-existent claim")
    req("get", f"/products/{fake_id}", [404], CAT,
        "GET non-existent product")

    # Malformed JSON
    r = requests.post(
        f"{API_V1}/submissions",
        headers={"X-API-Key": "openinsure-dev-key-2024",
                 "Content-Type": "application/json"},
        data="{{not valid json",
        timeout=TIMEOUT,
    )
    if r.status_code == 422:
        log(CAT, "Malformed JSON body", PASS, f"HTTP {r.status_code}")
    elif r.status_code in (400, 500):
        log(CAT, "Malformed JSON body", WARN, f"HTTP {r.status_code} (expected 422)")
    else:
        log(CAT, "Malformed JSON body", FAIL, f"HTTP {r.status_code}")

    # Very large payload (100KB)
    large_body = {
        "applicant_name": "Large Payload Test",
        "risk_data": {"padding": "X" * 100000},
    }
    r = req("post", "/submissions", [200, 201, 413, 422, 400], CAT,
            "100KB payload", json=large_body)
    if r and r.status_code in (200, 201):
        log(CAT, "Large payload accepted", PASS, "Server handled 100KB OK")

    # Rate-limit test: rapid-fire 50 requests
    print("  --- Rate limit test (50 rapid requests) ---")
    start = time.time()
    statuses = []
    for i in range(50):
        try:
            r = requests.get(f"{API_V1}/submissions", headers=HEADERS, timeout=10)
            statuses.append(r.status_code)
        except Exception:
            statuses.append(0)
    elapsed = time.time() - start
    rate_limited = [s for s in statuses if s == 429]
    errors = [s for s in statuses if s >= 500]
    ok = [s for s in statuses if s == 200]
    if rate_limited:
        log(CAT, "Rate limiting", PASS,
            f"429s: {len(rate_limited)}, 200s: {len(ok)} in {elapsed:.1f}s")
    elif errors:
        log(CAT, "Rate limiting", FAIL,
            f"Server errors: {len(errors)}, 200s: {len(ok)} in {elapsed:.1f}s")
    else:
        log(CAT, "Rate limiting (50 req)", WARN,
            f"No rate limit — all {len(ok)} returned 200 in {elapsed:.1f}s")


# ══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════
def print_summary():
    categories = {}
    for cat, name, status, detail in results:
        if cat not in categories:
            categories[cat] = {"PASS": 0, "FAIL": 0, "WARN": 0}
        categories[cat][status] += 1

    total_p = total_f = total_w = 0
    print(f"\n{'='*70}")
    print(f"  FUNCTIONAL TEST SUMMARY — {datetime.now().isoformat()}")
    print(f"{'='*70}")
    print(f"  {'Category':<18} | {'Pass':>4} | {'Fail':>4} | {'Warn':>4} | {'Total':>5}")
    print(f"  {'-'*18}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*5}")
    for cat in categories:
        p, f, w = categories[cat]["PASS"], categories[cat]["FAIL"], categories[cat]["WARN"]
        t = p + f + w
        total_p += p; total_f += f; total_w += w
        print(f"  {cat:<18} | {p:>4} | {f:>4} | {w:>4} | {t:>5}")
    total = total_p + total_f + total_w
    print(f"  {'-'*18}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*5}")
    print(f"  {'TOTAL':<18} | {total_p:>4} | {total_f:>4} | {total_w:>4} | {total:>5}")
    print(f"{'='*70}\n")

    # Print failures
    failures = [(cat, name, detail) for cat, name, status, detail in results if status == "FAIL"]
    if failures:
        print("  FAILURES:")
        for cat, name, detail in failures:
            print(f"    [{cat}] {name} — {detail}")
        print()

    # Print warnings
    warnings = [(cat, name, detail) for cat, name, status, detail in results if status == "WARN"]
    if warnings:
        print("  WARNINGS:")
        for cat, name, detail in warnings:
            print(f"    [{cat}] {name} — {detail}")
        print()

    return failures


# ══════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"{'='*70}")
    print(f"  OpenInsure Functional Test Suite v95")
    print(f"  Target: {BASE_URL}")
    print(f"  Started: {datetime.now().isoformat()}")
    print(f"{'='*70}")

    # Health check first
    try:
        r = requests.get(f"{BASE_URL}/health", headers=HEADERS, timeout=10)
        print(f"  Health check: HTTP {r.status_code}")
        if r.status_code != 200:
            print("  !! Backend may be unhealthy — proceeding anyway")
    except Exception as e:
        print(f"  !! Health check failed: {e}")
        # Try root
        try:
            r = requests.get(BASE_URL, timeout=10)
            print(f"  Root check: HTTP {r.status_code}")
        except Exception as e2:
            print(f"  !! Backend unreachable: {e2}")
            sys.exit(1)

    sub_id, policy_id = test_submissions()
    test_claims(policy_id)
    test_products()
    test_knowledge()
    test_compliance()
    test_billing()
    test_reinsurance()
    test_actuarial()
    test_escalations()
    test_metrics()
    test_broker()
    test_cross_cutting()

    failures = print_summary()

    # Exit code
    if failures:
        print(f"  ✗ {len(failures)} test(s) FAILED")
        sys.exit(1)
    else:
        print(f"  ✓ All tests passed (with warnings)")
        sys.exit(0)
