-- Migration 012: Composite unique constraints
-- Issue #163 — idempotent via IF NOT EXISTS checks
-- Clean duplicate data before creating unique constraints

-- Deduplicate billing_accounts: keep latest record per policy_id
IF EXISTS (SELECT policy_id FROM billing_accounts GROUP BY policy_id HAVING COUNT(*) > 1)
BEGIN
    ;WITH cte AS (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY policy_id ORDER BY created_at DESC) AS rn
        FROM billing_accounts
    )
    DELETE FROM cte WHERE rn > 1;
END

-- One active policy per insured+product
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_policies_active_insured_product') CREATE UNIQUE INDEX UQ_policies_active_insured_product ON policies (insured_id, product_id) WHERE status IN ('active', 'pending');

-- One billing account per policy
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_billing_policy') CREATE UNIQUE INDEX UQ_billing_policy ON billing_accounts (policy_id);

-- One active renewal per policy
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_renewal_active') CREATE UNIQUE INDEX UQ_renewal_active ON renewal_records (original_policy_id) WHERE status IN ('pending', 'terms_generated', 'offered')
