-- Migration 007: Performance Indexes
-- Issue #158: Add 17 NONCLUSTERED indexes for query-path and analytics performance
-- Idempotent: IF NOT EXISTS checks + TRY/CATCH per index

-- ============================================================================
-- Critical — Query-path indexes
-- ============================================================================

-- 1. claims(loss_date) — loss triangles, date-range queries
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_claims_loss_date' AND object_id = OBJECT_ID('claims'))
        CREATE NONCLUSTERED INDEX IX_claims_loss_date ON claims(loss_date);
    PRINT 'OK: IX_claims_loss_date';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_claims_loss_date — ' + ERROR_MESSAGE();
END CATCH;

-- 2. claims(policy_id, status) — claims for a policy filtered by status
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_claims_policy_status' AND object_id = OBJECT_ID('claims'))
        CREATE NONCLUSTERED INDEX IX_claims_policy_status ON claims(policy_id, status);
    PRINT 'OK: IX_claims_policy_status';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_claims_policy_status — ' + ERROR_MESSAGE();
END CATCH;

-- 3. policies(effective_date) — policies effective in window
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_policies_effective_date' AND object_id = OBJECT_ID('policies'))
        CREATE NONCLUSTERED INDEX IX_policies_effective_date ON policies(effective_date);
    PRINT 'OK: IX_policies_effective_date';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_policies_effective_date — ' + ERROR_MESSAGE();
END CATCH;

-- 4. policies(expiration_date) — upcoming expirations, renewals
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_policies_expiration_date' AND object_id = OBJECT_ID('policies'))
        CREATE NONCLUSTERED INDEX IX_policies_expiration_date ON policies(expiration_date);
    PRINT 'OK: IX_policies_expiration_date';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_policies_expiration_date — ' + ERROR_MESSAGE();
END CATCH;

-- 5. policies(insured_id, status) — customer's active policies
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_policies_insured_status' AND object_id = OBJECT_ID('policies'))
        CREATE NONCLUSTERED INDEX IX_policies_insured_status ON policies(insured_id, status);
    PRINT 'OK: IX_policies_insured_status';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_policies_insured_status — ' + ERROR_MESSAGE();
END CATCH;

-- 6. billing_accounts(policy_id) — billing for a policy
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_billing_accounts_policy' AND object_id = OBJECT_ID('billing_accounts'))
        CREATE NONCLUSTERED INDEX IX_billing_accounts_policy ON billing_accounts(policy_id);
    PRINT 'OK: IX_billing_accounts_policy';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_billing_accounts_policy — ' + ERROR_MESSAGE();
END CATCH;

-- 7. invoices(due_date, status) — overdue invoice reports
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_invoices_due_status' AND object_id = OBJECT_ID('invoices'))
        CREATE NONCLUSTERED INDEX IX_invoices_due_status ON invoices(due_date, status);
    PRINT 'OK: IX_invoices_due_status';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_invoices_due_status — ' + ERROR_MESSAGE();
END CATCH;

-- 8. invoices(billing_account_id) — invoices for an account
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_invoices_billing_account' AND object_id = OBJECT_ID('invoices'))
        CREATE NONCLUSTERED INDEX IX_invoices_billing_account ON invoices(billing_account_id);
    PRINT 'OK: IX_invoices_billing_account';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_invoices_billing_account — ' + ERROR_MESSAGE();
END CATCH;

-- 9. party_roles(role) — find all brokers, all insureds
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_party_roles_role' AND object_id = OBJECT_ID('party_roles'))
        CREATE NONCLUSTERED INDEX IX_party_roles_role ON party_roles(role);
    PRINT 'OK: IX_party_roles_role';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_party_roles_role — ' + ERROR_MESSAGE();
END CATCH;

-- 10. submissions(applicant_id) — submissions for a customer
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_submissions_applicant' AND object_id = OBJECT_ID('submissions'))
        CREATE NONCLUSTERED INDEX IX_submissions_applicant ON submissions(applicant_id);
    PRINT 'OK: IX_submissions_applicant';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_submissions_applicant — ' + ERROR_MESSAGE();
END CATCH;

-- 11. submissions(received_at) — time-based queries, dashboards
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_submissions_received_at' AND object_id = OBJECT_ID('submissions'))
        CREATE NONCLUSTERED INDEX IX_submissions_received_at ON submissions(received_at);
    PRINT 'OK: IX_submissions_received_at';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_submissions_received_at — ' + ERROR_MESSAGE();
END CATCH;

-- 12. decision_records(entity_id) — decisions for a submission/claim
-- Note: entity_id may be packed into JSON columns; index skips gracefully if column absent
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_decision_records_entity' AND object_id = OBJECT_ID('decision_records'))
        CREATE NONCLUSTERED INDEX IX_decision_records_entity ON decision_records(entity_id);
    PRINT 'OK: IX_decision_records_entity';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_decision_records_entity — ' + ERROR_MESSAGE();
END CATCH;

-- 13. decision_records(created_at) — recent decisions, time series
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_decision_records_created_at' AND object_id = OBJECT_ID('decision_records'))
        CREATE NONCLUSTERED INDEX IX_decision_records_created_at ON decision_records(created_at);
    PRINT 'OK: IX_decision_records_created_at';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_decision_records_created_at — ' + ERROR_MESSAGE();
END CATCH;

-- ============================================================================
-- Secondary — Report/analytics indexes
-- ============================================================================

-- 14. policies(broker_id) — broker book of business
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_policies_broker' AND object_id = OBJECT_ID('policies'))
        CREATE NONCLUSTERED INDEX IX_policies_broker ON policies(broker_id);
    PRINT 'OK: IX_policies_broker';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_policies_broker — ' + ERROR_MESSAGE();
END CATCH;

-- 15. submissions(broker_id) — broker submissions
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_submissions_broker' AND object_id = OBJECT_ID('submissions'))
        CREATE NONCLUSTERED INDEX IX_submissions_broker ON submissions(broker_id);
    PRINT 'OK: IX_submissions_broker';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_submissions_broker — ' + ERROR_MESSAGE();
END CATCH;

-- 16. claim_payments(payment_date) — payment reports
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_claim_payments_date' AND object_id = OBJECT_ID('claim_payments'))
        CREATE NONCLUSTERED INDEX IX_claim_payments_date ON claim_payments(payment_date);
    PRINT 'OK: IX_claim_payments_date';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_claim_payments_date — ' + ERROR_MESSAGE();
END CATCH;

-- 17. policy_endorsements(policy_id, effective_date) — endorsement history
BEGIN TRY
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_policy_endorsements_policy_date' AND object_id = OBJECT_ID('policy_endorsements'))
        CREATE NONCLUSTERED INDEX IX_policy_endorsements_policy_date ON policy_endorsements(policy_id, effective_date);
    PRINT 'OK: IX_policy_endorsements_policy_date';
END TRY
BEGIN CATCH
    PRINT 'WARN: IX_policy_endorsements_policy_date — ' + ERROR_MESSAGE();
END CATCH;

PRINT '--- Migration 007 complete: 17 indexes processed ---';
