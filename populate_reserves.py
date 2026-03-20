"""Populate realistic reserves directly into Azure SQL claim_reserves table."""
import random
import uuid
import json
import subprocess
import sys
import os

RESERVE_RANGES = {
    "data_breach": (25_000, 500_000),
    "ransomware": (50_000, 750_000),
    "business_interruption": (30_000, 400_000),
    "social_engineering": (15_000, 200_000),
    "third_party_liability": (20_000, 300_000),
    "regulatory_proceeding": (25_000, 350_000),
    "system_failure": (20_000, 250_000),
    "unauthorized_access": (25_000, 400_000),
    "denial_of_service": (30_000, 350_000),
    "other": (10_000, 150_000),
}

def get_token():
    """Get Azure SQL access token via az CLI."""
    result = subprocess.run(
        ['az', 'account', 'get-access-token', '--resource', 'https://database.windows.net', '--query', 'accessToken', '-o', 'tsv'],
        capture_output=True, text=True, shell=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to get token: {result.stderr}")
    return result.stdout.strip()

def run_node_script(script_content, cwd):
    """Run a Node.js script and return (stdout, stderr)."""
    script_path = os.path.join(cwd, '_sql_script.js')
    with open(script_path, 'w') as f:
        f.write(script_content)
    try:
        result = subprocess.run(['node', script_path], capture_output=True, text=True, cwd=cwd, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Node script failed: {result.stderr}")
        return result.stdout, result.stderr
    finally:
        if os.path.exists(script_path):
            os.unlink(script_path)

def main():
    random.seed(42)
    cwd = os.path.dirname(os.path.abspath(__file__))
    
    print("Getting Azure SQL access token...")
    token = get_token()
    print(f"Got token (length: {len(token)})")
    
    # Step 1: Fetch claims and existing reserves
    fetch_script = f"""
const sql = require('mssql');
const TOKEN = {json.dumps(token)};

async function main() {{
    const config = {{
        server: 'openinsure-dev-sql-knshtzbusr734.database.windows.net',
        database: 'openinsure-db',
        authentication: {{ type: 'azure-active-directory-access-token', options: {{ token: TOKEN }} }},
        options: {{ encrypt: true, trustServerCertificate: false, requestTimeout: 30000 }}
    }};
    
    const pool = await sql.connect(config);
    const claims = await pool.request().query('SELECT id, claim_number, cause_of_loss, status FROM claims');
    const reserves = await pool.request().query('SELECT COUNT(*) as cnt FROM claim_reserves');
    
    console.log(JSON.stringify({{
        claims: claims.recordset,
        existing_reserves: reserves.recordset[0].cnt
    }}));
    
    await pool.close();
}}

main().catch(e => {{ console.error(e.message); process.exit(1); }});
"""
    
    print("Fetching claims from SQL...")
    stdout, stderr = run_node_script(fetch_script, cwd)
    if stderr.strip():
        print(f"  stderr: {stderr.strip()}")
    data = json.loads(stdout)
    claims = data['claims']
    print(f"Found {len(claims)} claims, {data['existing_reserves']} existing reserves")
    
    # Step 2: Generate reserve data
    inserts = []
    for c in claims:
        ctype = c.get('cause_of_loss') or 'other'
        lo, hi = RESERVE_RANGES.get(ctype, RESERVE_RANGES['other'])
        amount = round(random.uniform(lo, hi), 2)
        reserve_id = str(uuid.uuid4()).upper()
        inserts.append({
            'id': reserve_id,
            'claim_id': c['id'],
            'claim_number': c.get('claim_number', '?'),
            'cause_of_loss': ctype,
            'amount': amount,
        })
    
    total_amount = sum(r['amount'] for r in inserts)
    print(f"\nGenerated {len(inserts)} reserves totaling ${total_amount:,.2f}")
    
    # Step 3: Insert reserves in batches
    # Build batch SQL to avoid 115 individual round-trips
    batch_size = 50
    all_success = 0
    all_failed = 0
    
    for batch_start in range(0, len(inserts), batch_size):
        batch = inserts[batch_start:batch_start + batch_size]
        
        # Build VALUES clause
        values_clauses = []
        for r in batch:
            values_clauses.append(
                f"('{r['id']}', '{r['claim_id']}', 'indemnity', {r['amount']}, GETUTCDATE(), 'system', 0.85)"
            )
        
        values_sql = ',\\n'.join(values_clauses)
        
        insert_script = f"""
const sql = require('mssql');
const TOKEN = {json.dumps(token)};

async function main() {{
    const config = {{
        server: 'openinsure-dev-sql-knshtzbusr734.database.windows.net',
        database: 'openinsure-db',
        authentication: {{ type: 'azure-active-directory-access-token', options: {{ token: TOKEN }} }},
        options: {{ encrypt: true, trustServerCertificate: false, requestTimeout: 30000 }}
    }};
    
    const pool = await sql.connect(config);
    
    // Delete existing reserves on first batch
    {"await pool.request().query('DELETE FROM claim_reserves');" if batch_start == 0 else ""}
    
    // Batch insert
    await pool.request().query(`
        INSERT INTO claim_reserves (id, claim_id, reserve_type, amount, set_date, set_by, confidence)
        VALUES {values_sql}
    `);
    
    // Get stats
    const stats = await pool.request().query(`
        SELECT COUNT(*) as cnt, CAST(SUM(amount) AS FLOAT) as total, CAST(AVG(amount) AS FLOAT) as avg_amt
        FROM claim_reserves
    `);
    
    console.log(JSON.stringify({{ success: {len(batch)}, stats: stats.recordset[0] }}));
    await pool.close();
}}

main().catch(e => {{ console.error(e.message); process.exit(1); }});
"""
        
        stdout, stderr = run_node_script(insert_script, cwd)
        if stderr.strip():
            print(f"  stderr: {stderr.strip()}")
        result = json.loads(stdout)
        all_success += result['success']
        print(f"  Batch {batch_start//batch_size + 1}: inserted {result['success']} reserves (total so far: {result['stats']['cnt']})")
        
        # Print individual reserves from this batch
        for r in batch:
            print(f"    ✓ {r['claim_number']:12s} | {r['cause_of_loss']:25s} | ${r['amount']:>12,.2f}")
    
    print(f"\n✓ Inserted {all_success} reserves into claim_reserves table")
    
    # Step 4: Final verification
    verify_script = f"""
const sql = require('mssql');
const TOKEN = {json.dumps(token)};

async function main() {{
    const config = {{
        server: 'openinsure-dev-sql-knshtzbusr734.database.windows.net',
        database: 'openinsure-db',
        authentication: {{ type: 'azure-active-directory-access-token', options: {{ token: TOKEN }} }},
        options: {{ encrypt: true, trustServerCertificate: false, requestTimeout: 30000 }}
    }};
    
    const pool = await sql.connect(config);
    
    const stats = await pool.request().query(`
        SELECT 
            (SELECT COUNT(*) FROM claim_reserves) as reserve_count,
            (SELECT CAST(SUM(amount) AS FLOAT) FROM claim_reserves) as total_reserved,
            (SELECT CAST(AVG(amount) AS FLOAT) FROM claim_reserves) as avg_reserve,
            (SELECT COUNT(DISTINCT claim_id) FROM claim_reserves) as claims_with_reserves,
            (SELECT COUNT(*) FROM claims) as total_claims
    `);
    
    // Sample by cause_of_loss
    const byCause = await pool.request().query(`
        SELECT c.cause_of_loss, COUNT(cr.id) as cnt, CAST(SUM(cr.amount) AS FLOAT) as total, CAST(AVG(cr.amount) AS FLOAT) as avg_amt
        FROM claim_reserves cr JOIN claims c ON cr.claim_id = c.id
        GROUP BY c.cause_of_loss
    `);
    
    console.log(JSON.stringify({{ stats: stats.recordset[0], by_cause: byCause.recordset }}));
    await pool.close();
}}

main().catch(e => {{ console.error(e.message); process.exit(1); }});
"""
    
    print("\nVerifying...")
    stdout, stderr = run_node_script(verify_script, cwd)
    result = json.loads(stdout)
    s = result['stats']
    print(f"  Total claims: {s['total_claims']}")
    print(f"  Claims with reserves: {s['claims_with_reserves']}")
    print(f"  Reserve records: {s['reserve_count']}")
    print(f"  Total reserved: ${s['total_reserved']:,.2f}")
    print(f"  Average reserve: ${s['avg_reserve']:,.2f}")
    print(f"\n  By cause of loss:")
    for row in result['by_cause']:
        print(f"    {row['cause_of_loss']:25s} | {row['cnt']:3d} claims | ${row['total']:>12,.2f} total | ${row['avg_amt']:>10,.2f} avg")

if __name__ == "__main__":
    main()
