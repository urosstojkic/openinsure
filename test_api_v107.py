"""API functional tests for v107 post-migration validation."""
import requests
import json
import time

BASE = "https://openinsure-backend.proudplant-9550e5a5.swedencentral.azurecontainerapps.io"
H = {"X-API-Key": "openinsure-dev-key-2024", "Content-Type": "application/json"}

results = {}

# 1. SUBMISSION LIFECYCLE
print("=== SUBMISSION LIFECYCLE ===")
try:
    sub = requests.post(f"{BASE}/api/v1/submissions", headers=H, json={
        "applicant_name": "E2E Test Corp",
        "line_of_business": "cyber",
        "risk_data": {"annual_revenue": 8000000, "employee_count": 120, "industry": "technology", "security_maturity_score": 7},
        "cyber_risk_data": {"has_mfa": True, "has_endpoint_protection": True, "prior_incidents": 0}
    }, timeout=30)
    sub_data = sub.json()
    sub_id = sub_data.get("id", "")
    print(f"Create: {sub_id} status={sub_data.get('status')} code={sub.status_code}")

    triage = requests.post(f"{BASE}/api/v1/submissions/{sub_id}/triage", headers=H, timeout=60)
    triage_data = triage.json()
    print(f"Triage: score={triage_data.get('risk_score')} flags={str(triage_data.get('flags', ''))[:80]} code={triage.status_code}")

    quote = requests.post(f"{BASE}/api/v1/submissions/{sub_id}/quote", headers=H, timeout=60)
    quote_data = quote.json()
    print(f"Quote: premium={quote_data.get('premium')} code={quote.status_code}")

    bind = requests.post(f"{BASE}/api/v1/submissions/{sub_id}/bind", headers=H, timeout=30)
    bind_data = bind.json()
    print(f"Bind: policy={str(bind_data.get('policy_id', ''))[:30]} code={bind.status_code}")
    results["submission"] = "PASS" if all([
        sub.status_code in (200, 201),
        triage.status_code == 200,
        quote.status_code == 200,
        bind.status_code == 200
    ]) else "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["submission"] = "FAIL"

# 2. PRODUCTS
print("\n=== PRODUCTS ===")
try:
    products = requests.get(f"{BASE}/api/v1/products", headers=H, timeout=15)
    pdata = products.json()
    print(f"Products: {pdata.get('total', 0)} total, code={products.status_code}")
    if pdata.get("items"):
        pid = pdata["items"][0]["id"]
        detail = requests.get(f"{BASE}/api/v1/products/{pid}", headers=H, timeout=15)
        dd = detail.json()
        print(f"Product detail: {dd.get('name')} coverages={len(dd.get('coverages', []))} factors={len(dd.get('rating_factors', []))}")
    results["products"] = "PASS" if products.status_code == 200 and pdata.get("total", 0) > 0 else "WARN"
except Exception as e:
    print(f"ERROR: {e}")
    results["products"] = "FAIL"

# 3. CLAIMS
print("\n=== CLAIMS ===")
try:
    claims = requests.get(f"{BASE}/api/v1/claims", headers=H, timeout=15)
    cdata = claims.json()
    print(f"Claims: {cdata.get('total', 0)} total, code={claims.status_code}")
    results["claims"] = "PASS" if claims.status_code == 200 else "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["claims"] = "FAIL"

# 4. AUDIT TRAIL
print("\n=== AUDIT TRAIL ===")
try:
    audit = requests.get(f"{BASE}/api/v1/audit/recent?hours=24", headers=H, timeout=15)
    if audit.status_code == 200:
        print(f"Audit trail: {audit.status_code} - {len(audit.json())} records")
        results["audit"] = "PASS"
    else:
        print(f"Audit trail: {audit.status_code} - {audit.text[:200]}")
        results["audit"] = "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["audit"] = "FAIL"

# 5. GDPR
print("\n=== GDPR ===")
try:
    retention = requests.get(f"{BASE}/api/v1/gdpr/retention-policies", headers=H, timeout=15)
    print(f"GDPR retention: {retention.status_code} - {retention.text[:200]}")
    results["gdpr"] = "PASS" if retention.status_code == 200 else "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["gdpr"] = "FAIL"

# 6. PARTIES
print("\n=== PARTIES ===")
try:
    parties = requests.get(f"{BASE}/api/v1/parties/search?name=E2E", headers=H, timeout=15)
    print(f"Party search: {parties.status_code} - {parties.text[:200]}")
    results["parties"] = "PASS" if parties.status_code == 200 else "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["parties"] = "FAIL"

# 7. COMPLIANCE STATS
print("\n=== COMPLIANCE ===")
try:
    stats = requests.get(f"{BASE}/api/v1/compliance/stats", headers=H, timeout=15)
    print(f"Compliance stats: {stats.status_code} - {stats.text[:200]}")
    results["compliance"] = "PASS" if stats.status_code == 200 else "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["compliance"] = "FAIL"

# 8. PRODUCT SYNC
print("\n=== PRODUCT SYNC ===")
try:
    sync = requests.post(f"{BASE}/api/v1/admin/sync-products", headers=H, timeout=30)
    sdata = sync.json()
    print(f"Product sync: {sync.status_code} - {sdata.get('total_products', 0)} products")
    results["product_sync"] = "PASS" if sync.status_code == 200 else "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["product_sync"] = "FAIL"

# 9. METRICS
print("\n=== METRICS ===")
try:
    metrics = requests.get(f"{BASE}/api/v1/metrics/summary", headers=H, timeout=15)
    mdata = metrics.json()
    print(f"Metrics: {mdata.get('total_submissions', 0)} submissions, {mdata.get('total_policies', 0)} policies, code={metrics.status_code}")
    results["metrics"] = "PASS" if metrics.status_code == 200 else "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["metrics"] = "FAIL"

# 10. FRIA
print("\n=== FRIA ===")
try:
    fria = requests.post(f"{BASE}/api/v1/compliance/fria/generate", headers=H, json={}, timeout=30)
    if fria.status_code == 200:
        print(f"FRIA: {fria.status_code} - sections={fria.json().get('sections', 0)}")
        results["fria"] = "PASS"
    else:
        print(f"FRIA: {fria.status_code} - {fria.text[:200]}")
        results["fria"] = "FAIL"
except Exception as e:
    print(f"ERROR: {e}")
    results["fria"] = "FAIL"

print("\n=== API TEST SUMMARY ===")
for k, v in results.items():
    print(f"  {k:20s}: {v}")
