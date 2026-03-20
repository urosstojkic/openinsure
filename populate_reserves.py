"""Populate realistic reserves directly into Azure SQL claim_reserves table using Node.js."""
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

def main():
    random.seed(42)

    # Generate SQL statements
    # First, get claims list via Node.js
    node_fetch = """
const sql = require('mssql');
const { DefaultAzureCredential } = require('@azure/identity');

async function main() {
    const cred = new DefaultAzureCredential();
    const tokenResponse = await cred.getToken('https://database.windows.net/.default');
    
    const config = {
        server: 'openinsure-dev-sql-knshtzbusr734.database.windows.net',
        database: 'openinsure-db',
        authentication: { type: 'azure-active-directory-access-token', options: { token: tokenResponse.token } },
        options: { encrypt: true, trustServerCertificate: false }
    };
    
    const pool = await sql.connect(config);
    
    // Fetch claims
    const claims = await pool.request().query('SELECT id, claim_number, cause_of_loss, status FROM claims');
    
    // Check existing reserves
    const existing = await pool.request().query('SELECT COUNT(*) as cnt FROM claim_reserves');
    console.error('Existing reserves: ' + existing.recordset[0].cnt);
    
    // Output claims as JSON
    console.log(JSON.stringify(claims.recordset));
    
    await pool.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
"""
    
    print("Fetching claims from SQL...")
    script_path = os.path.join(os.path.dirname(__file__), '_fetch_claims.js')
    with open(script_path, 'w') as f:
        f.write(node_fetch)
    
    result = subprocess.run(['node', script_path], capture_output=True, text=True, cwd=os.path.dirname(__file__))
    os.unlink(script_path)
    
    if result.returncode != 0:
        print(f"Error fetching claims: {result.stderr}")
        sys.exit(1)
    
    print(result.stderr.strip())
    claims = json.loads(result.stdout)
    print(f"Found {len(claims)} claims\n")
    
    # Generate reserve inserts
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
    
    # Write insert script
    node_insert = """
const sql = require('mssql');
const { DefaultAzureCredential } = require('@azure/identity');

const inserts = INSERTS_PLACEHOLDER;

async function main() {
    const cred = new DefaultAzureCredential();
    const tokenResponse = await cred.getToken('https://database.windows.net/.default');
    
    const config = {
        server: 'openinsure-dev-sql-knshtzbusr734.database.windows.net',
        database: 'openinsure-db',
        authentication: { type: 'azure-active-directory-access-token', options: { token: tokenResponse.token } },
        options: { encrypt: true, trustServerCertificate: false }
    };
    
    const pool = await sql.connect(config);
    
    // Clear existing reserves
    await pool.request().query('DELETE FROM claim_reserves');
    console.error('Cleared existing reserves');
    
    let success = 0, failed = 0;
    for (const r of inserts) {
        try {
            await pool.request()
                .input('id', sql.UniqueIdentifier, r.id)
                .input('claim_id', sql.UniqueIdentifier, r.claim_id)
                .input('amount', sql.Decimal(18, 2), r.amount)
                .query(`INSERT INTO claim_reserves (id, claim_id, reserve_type, amount, set_date, set_by, confidence)
                        VALUES (@id, @claim_id, 'indemnity', @amount, GETUTCDATE(), 'system', 0.85)`);
            success++;
            console.error('  OK ' + r.claim_number + ' | ' + r.cause_of_loss + ' | $' + r.amount.toFixed(2));
        } catch (e) {
            failed++;
            console.error('  FAIL ' + r.claim_number + ' | ' + e.message);
        }
    }
    
    console.error('\\nInserted: ' + success + ' success, ' + failed + ' failed');
    
    // Verify
    const stats = await pool.request().query(`
        SELECT COUNT(*) as cnt, SUM(amount) as total_reserved, AVG(amount) as avg_reserve
        FROM claim_reserves
    `);
    const s = stats.recordset[0];
    console.error('\\nVerification:');
    console.error('  Reserve records: ' + s.cnt);
    console.error('  Total reserved:  $' + Number(s.total_reserved).toFixed(2));
    console.error('  Average reserve: $' + Number(s.avg_reserve).toFixed(2));
    
    // Output summary as JSON for the Python wrapper
    console.log(JSON.stringify({ success, failed, total: s.cnt, total_reserved: Number(s.total_reserved) }));
    
    await pool.close();
}

main().catch(e => { console.error(e.message); process.exit(1); });
""".replace('INSERTS_PLACEHOLDER', json.dumps(inserts))
    
    script_path = os.path.join(os.path.dirname(__file__), '_insert_reserves.js')
    with open(script_path, 'w') as f:
        f.write(node_insert)
    
    print("Inserting reserves into SQL...")
    result = subprocess.run(['node', script_path], capture_output=True, text=True, cwd=os.path.dirname(__file__))
    os.unlink(script_path)
    
    print(result.stderr)
    
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    
    summary = json.loads(result.stdout)
    print(f"\n✓ Summary: {summary['success']}/{summary['total']} reserves, ${summary['total_reserved']:,.2f} total")

if __name__ == "__main__":
    main()
