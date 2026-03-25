"""Populate claim reserves for all claims missing them."""

import random

import httpx

BE = os.environ.get("OPENINSURE_BACKEND_URL", "http://localhost:8000")/api/v1"
H = {"X-API-Key": "dev-key-change-me"}

RANGES = {
    "data_breach": (25000, 500000),
    "ransomware": (50000, 750000),
    "business_interruption": (30000, 400000),
    "social_engineering": (15000, 200000),
}

# Paginate all claims
all_claims = []
skip = 0
while True:
    r = httpx.get(f"{BE}/claims", params={"limit": 50, "skip": skip}, headers=H, timeout=30)
    page = r.json()
    items = page["items"]
    all_claims.extend(items)
    if len(items) < 50:
        break
    skip += 50
print(f"Total claims: {len(all_claims)}")

ok, skip_existing = 0, 0
for c in all_claims:
    cid = c["id"]
    if float(c.get("total_reserved", 0) or 0) > 0:
        skip_existing += 1
        continue
    ct = c.get("claim_type", "other")
    lo, hi = RANGES.get(ct, (10000, 150000))
    amt = random.randint(lo, hi)
    try:
        resp = httpx.post(
            f"{BE}/claims/{cid}/reserve",
            json={"category": "indemnity", "amount": amt, "currency": "USD", "notes": f"Case reserve for {ct}"},
            headers=H,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            ok += 1
        elif ok == 0:
            print(f"  {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        if ok == 0:
            print(f"  ERR: {e}")
print(f"Reserves set: {ok} | Already had reserves: {skip_existing} | Total: {len(all_claims)}")

# Verify
r = httpx.get(f"{BE}/metrics/summary", headers=H, timeout=15)
s = r.json()
claims_data = s["claims"]
print(f"Loss ratio: {claims_data['loss_ratio']}% | Total incurred: ${claims_data['total_incurred']}")
