-- Migration 012: Composite unique constraints
-- Issue #163 — idempotent via IF NOT EXISTS checks

-- One active policy per insured+product
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_policies_active_insured_product') CREATE UNIQUE INDEX UQ_policies_active_insured_product ON policies (insured_id, product_id) WHERE status IN ('active', 'pending');

-- One billing account per policy
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_billing_policy') CREATE UNIQUE INDEX UQ_billing_policy ON billing_accounts (policy_id);

-- One active renewal per policy
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_renewal_active') CREATE UNIQUE INDEX UQ_renewal_active ON renewal_records (original_policy_id) WHERE status IN ('pending', 'terms_generated', 'offered')
