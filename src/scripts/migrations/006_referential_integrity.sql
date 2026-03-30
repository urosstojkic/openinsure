-- Migration 006: Referential Integrity — ON DELETE actions
-- Issue #156: Add proper ON DELETE RESTRICT/CASCADE to all foreign keys
-- Idempotent: safe to run multiple times (TRY/CATCH per FK, drops+recreates)
--
-- SQL Server uses ON DELETE NO ACTION as the equivalent of RESTRICT.
-- Both prevent parent deletion when children exist; NO ACTION is the T-SQL syntax.
--
-- DOWN MIGRATION (manual rollback):
--   -- This migration drops and recreates FK constraints with ON DELETE actions.
--   -- Rollback requires re-creating the original FKs without ON DELETE clauses.
--   -- Review the original constraint definitions in 001_initial_schema.sql.
--   DELETE FROM _migration_history WHERE migration_name = '006_referential_integrity.sql';

DECLARE @fk NVARCHAR(200);

-- ============================================================================
-- RESTRICT (NO ACTION) — Critical parent-child relationships
-- ============================================================================

-- 1. policies.insured_id → parties(id) RESTRICT
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('policies')
      AND fk.referenced_object_id = OBJECT_ID('parties')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'insured_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE policies DROP CONSTRAINT ' + @fk);
    ALTER TABLE policies ADD CONSTRAINT FK_policies_insured
        FOREIGN KEY (insured_id) REFERENCES parties(id) ON DELETE NO ACTION;
    PRINT 'OK: FK_policies_insured (NO ACTION)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_policies_insured — ' + ERROR_MESSAGE();
END CATCH;

-- 2. policies.product_id → products(id) RESTRICT
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('policies')
      AND fk.referenced_object_id = OBJECT_ID('products')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'product_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE policies DROP CONSTRAINT ' + @fk);
    ALTER TABLE policies ADD CONSTRAINT FK_policies_product
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE NO ACTION;
    PRINT 'OK: FK_policies_product (NO ACTION)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_policies_product — ' + ERROR_MESSAGE();
END CATCH;

-- 3. claims.policy_id → policies(id) RESTRICT
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('claims')
      AND fk.referenced_object_id = OBJECT_ID('policies')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'policy_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE claims DROP CONSTRAINT ' + @fk);
    ALTER TABLE claims ADD CONSTRAINT FK_claims_policy
        FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE NO ACTION;
    PRINT 'OK: FK_claims_policy (NO ACTION)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_claims_policy — ' + ERROR_MESSAGE();
END CATCH;

-- 4. billing_accounts.policy_id → policies(id) RESTRICT
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('billing_accounts')
      AND fk.referenced_object_id = OBJECT_ID('policies')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'policy_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE billing_accounts DROP CONSTRAINT ' + @fk);
    ALTER TABLE billing_accounts ADD CONSTRAINT FK_billing_accounts_policy
        FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE NO ACTION;
    PRINT 'OK: FK_billing_accounts_policy (NO ACTION)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_billing_accounts_policy — ' + ERROR_MESSAGE();
END CATCH;

-- 5. reinsurance_cessions.policy_id → policies(id) RESTRICT
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('reinsurance_cessions')
      AND fk.referenced_object_id = OBJECT_ID('policies')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'policy_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE reinsurance_cessions DROP CONSTRAINT ' + @fk);
    ALTER TABLE reinsurance_cessions ADD CONSTRAINT FK_reinsurance_cessions_policy
        FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE NO ACTION;
    PRINT 'OK: FK_reinsurance_cessions_policy (NO ACTION)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_reinsurance_cessions_policy — ' + ERROR_MESSAGE();
END CATCH;

-- 6. reinsurance_cessions.treaty_id → reinsurance_treaties(id) RESTRICT
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('reinsurance_cessions')
      AND fk.referenced_object_id = OBJECT_ID('reinsurance_treaties')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'treaty_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE reinsurance_cessions DROP CONSTRAINT ' + @fk);
    ALTER TABLE reinsurance_cessions ADD CONSTRAINT FK_reinsurance_cessions_treaty
        FOREIGN KEY (treaty_id) REFERENCES reinsurance_treaties(id) ON DELETE NO ACTION;
    PRINT 'OK: FK_reinsurance_cessions_treaty (NO ACTION)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_reinsurance_cessions_treaty — ' + ERROR_MESSAGE();
END CATCH;

-- 7. reinsurance_recoveries.claim_id → claims(id) RESTRICT
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('reinsurance_recoveries')
      AND fk.referenced_object_id = OBJECT_ID('claims')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'claim_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE reinsurance_recoveries DROP CONSTRAINT ' + @fk);
    ALTER TABLE reinsurance_recoveries ADD CONSTRAINT FK_reinsurance_recoveries_claim
        FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE NO ACTION;
    PRINT 'OK: FK_reinsurance_recoveries_claim (NO ACTION)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_reinsurance_recoveries_claim — ' + ERROR_MESSAGE();
END CATCH;

-- 8. renewal_records.original_policy_id → policies(id) RESTRICT
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('renewal_records')
      AND fk.referenced_object_id = OBJECT_ID('policies')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'original_policy_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE renewal_records DROP CONSTRAINT ' + @fk);
    ALTER TABLE renewal_records ADD CONSTRAINT FK_renewal_records_original_policy
        FOREIGN KEY (original_policy_id) REFERENCES policies(id) ON DELETE NO ACTION;
    PRINT 'OK: FK_renewal_records_original_policy (NO ACTION)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_renewal_records_original_policy — ' + ERROR_MESSAGE();
END CATCH;

-- ============================================================================
-- CASCADE — Dependent children (meaningless without parent)
-- ============================================================================

-- 9. party_roles.party_id → parties(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('party_roles')
      AND fk.referenced_object_id = OBJECT_ID('parties')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'party_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE party_roles DROP CONSTRAINT ' + @fk);
    ALTER TABLE party_roles ADD CONSTRAINT FK_party_roles_party
        FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE CASCADE;
    PRINT 'OK: FK_party_roles_party (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_party_roles_party — ' + ERROR_MESSAGE();
END CATCH;

-- 10. party_addresses.party_id → parties(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('party_addresses')
      AND fk.referenced_object_id = OBJECT_ID('parties')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'party_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE party_addresses DROP CONSTRAINT ' + @fk);
    ALTER TABLE party_addresses ADD CONSTRAINT FK_party_addresses_party
        FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE CASCADE;
    PRINT 'OK: FK_party_addresses_party (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_party_addresses_party — ' + ERROR_MESSAGE();
END CATCH;

-- 11. party_contacts.party_id → parties(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('party_contacts')
      AND fk.referenced_object_id = OBJECT_ID('parties')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'party_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE party_contacts DROP CONSTRAINT ' + @fk);
    ALTER TABLE party_contacts ADD CONSTRAINT FK_party_contacts_party
        FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE CASCADE;
    PRINT 'OK: FK_party_contacts_party (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_party_contacts_party — ' + ERROR_MESSAGE();
END CATCH;

-- 12. submission_documents.submission_id → submissions(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('submission_documents')
      AND fk.referenced_object_id = OBJECT_ID('submissions')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'submission_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE submission_documents DROP CONSTRAINT ' + @fk);
    ALTER TABLE submission_documents ADD CONSTRAINT FK_submission_documents_submission
        FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE;
    PRINT 'OK: FK_submission_documents_submission (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_submission_documents_submission — ' + ERROR_MESSAGE();
END CATCH;

-- 13. policy_coverages.policy_id → policies(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('policy_coverages')
      AND fk.referenced_object_id = OBJECT_ID('policies')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'policy_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE policy_coverages DROP CONSTRAINT ' + @fk);
    ALTER TABLE policy_coverages ADD CONSTRAINT FK_policy_coverages_policy
        FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE;
    PRINT 'OK: FK_policy_coverages_policy (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_policy_coverages_policy — ' + ERROR_MESSAGE();
END CATCH;

-- 14. policy_endorsements.policy_id → policies(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('policy_endorsements')
      AND fk.referenced_object_id = OBJECT_ID('policies')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'policy_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE policy_endorsements DROP CONSTRAINT ' + @fk);
    ALTER TABLE policy_endorsements ADD CONSTRAINT FK_policy_endorsements_policy
        FOREIGN KEY (policy_id) REFERENCES policies(id) ON DELETE CASCADE;
    PRINT 'OK: FK_policy_endorsements_policy (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_policy_endorsements_policy — ' + ERROR_MESSAGE();
END CATCH;

-- 15. claim_reserves.claim_id → claims(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('claim_reserves')
      AND fk.referenced_object_id = OBJECT_ID('claims')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'claim_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE claim_reserves DROP CONSTRAINT ' + @fk);
    ALTER TABLE claim_reserves ADD CONSTRAINT FK_claim_reserves_claim
        FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE;
    PRINT 'OK: FK_claim_reserves_claim (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_claim_reserves_claim — ' + ERROR_MESSAGE();
END CATCH;

-- 16. claim_payments.claim_id → claims(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('claim_payments')
      AND fk.referenced_object_id = OBJECT_ID('claims')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'claim_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE claim_payments DROP CONSTRAINT ' + @fk);
    ALTER TABLE claim_payments ADD CONSTRAINT FK_claim_payments_claim
        FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE;
    PRINT 'OK: FK_claim_payments_claim (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_claim_payments_claim — ' + ERROR_MESSAGE();
END CATCH;

-- 17. invoices.billing_account_id → billing_accounts(id) CASCADE
BEGIN TRY
    SET @fk = NULL;
    SELECT @fk = fk.name FROM sys.foreign_keys fk
    INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE fk.parent_object_id = OBJECT_ID('invoices')
      AND fk.referenced_object_id = OBJECT_ID('billing_accounts')
      AND COL_NAME(fkc.parent_object_id, fkc.parent_column_id) = 'billing_account_id';
    IF @fk IS NOT NULL EXEC('ALTER TABLE invoices DROP CONSTRAINT ' + @fk);
    ALTER TABLE invoices ADD CONSTRAINT FK_invoices_billing_account
        FOREIGN KEY (billing_account_id) REFERENCES billing_accounts(id) ON DELETE CASCADE;
    PRINT 'OK: FK_invoices_billing_account (CASCADE)';
END TRY
BEGIN CATCH
    PRINT 'WARN: FK_invoices_billing_account — ' + ERROR_MESSAGE();
END CATCH;

PRINT '--- Migration 006 complete: 17 FK constraints updated ---';
