import sys
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv()

import asyncio
from openinsure.infrastructure.factory import get_claim_repository, get_database_adapter

async def check():
    repo = get_claim_repository()
    db = get_database_adapter()
    
    claims = await repo.list_all(limit=500)
    print(f"Total claims: {len(claims)}")
    
    with_reserves = sum(1 for c in claims if float(c.get("total_reserved") or 0) > 0)
    without_reserves = len(claims) - with_reserves
    print(f"Claims with total_reserved > 0: {with_reserves}")
    print(f"Claims with total_reserved = 0: {without_reserves}")
    
    print("\nFirst 3 claims:")
    for claim in claims[:3]:
        cid = str(claim.get("id", ""))[:8]
        ctype = claim.get("claim_type", "")
        reserved = claim.get("total_reserved", 0)
        paid = claim.get("total_paid", 0)
        incurred = claim.get("total_incurred", 0)
        print(f"  {cid}... type={ctype} reserved={reserved} paid={paid} incurred={incurred}")
    
    if db:
        result = await db.fetch_one("SELECT COUNT(*) as cnt FROM claim_reserves", [])
        if result:
            print(f"\nRaw claim_reserves count: {result.get('cnt', 0)}")
        
        result = await db.fetch_one("SELECT COUNT(*) as cnt FROM claim_payments", [])
        if result:
            print(f"Raw claim_payments count: {result.get('cnt', 0)}")

asyncio.run(check())
