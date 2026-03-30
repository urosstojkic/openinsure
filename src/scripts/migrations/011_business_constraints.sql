-- Migration 011: Database-level validation constraints
-- Issue #162 — idempotent via BEGIN TRY / BEGIN CATCH

-- Date logic
BEGIN TRY ALTER TABLE policies ADD CONSTRAINT CK_policies_dates CHECK (effective_date <= expiration_date) END TRY BEGIN CATCH PRINT 'CK_policies_dates exists' END CATCH;
BEGIN TRY ALTER TABLE reinsurance_treaties ADD CONSTRAINT CK_treaties_dates CHECK (effective_date <= expiration_date) END TRY BEGIN CATCH PRINT 'CK_treaties_dates exists' END CATCH;

-- Financial non-negativity
BEGIN TRY ALTER TABLE policies ADD CONSTRAINT CK_policies_premium CHECK (total_premium >= 0) END TRY BEGIN CATCH PRINT 'CK_policies_premium exists' END CATCH;
BEGIN TRY ALTER TABLE claim_reserves ADD CONSTRAINT CK_reserves_amount CHECK (amount >= 0) END TRY BEGIN CATCH PRINT 'CK_reserves_amount exists' END CATCH;
BEGIN TRY ALTER TABLE claim_payments ADD CONSTRAINT CK_payments_amount CHECK (amount >= 0) END TRY BEGIN CATCH PRINT 'CK_payments_amount exists' END CATCH;
BEGIN TRY ALTER TABLE invoices ADD CONSTRAINT CK_invoices_amount CHECK (amount >= 0) END TRY BEGIN CATCH PRINT 'CK_invoices_amount exists' END CATCH;
BEGIN TRY ALTER TABLE submissions ADD CONSTRAINT CK_submissions_premium CHECK (quoted_premium IS NULL OR quoted_premium >= 0) END TRY BEGIN CATCH PRINT 'CK_submissions_premium exists' END CATCH;
BEGIN TRY ALTER TABLE products ADD CONSTRAINT CK_products_version CHECK (version >= 1) END TRY BEGIN CATCH PRINT 'CK_products_version exists' END CATCH
