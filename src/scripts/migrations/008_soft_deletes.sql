-- Migration 008: Soft deletes — add deleted_at to all core tables
-- Idempotent: safe to run multiple times

IF COL_LENGTH('parties', 'deleted_at') IS NULL
    ALTER TABLE parties ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('submissions', 'deleted_at') IS NULL
    ALTER TABLE submissions ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('policies', 'deleted_at') IS NULL
    ALTER TABLE policies ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('claims', 'deleted_at') IS NULL
    ALTER TABLE claims ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('products', 'deleted_at') IS NULL
    ALTER TABLE products ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('billing_accounts', 'deleted_at') IS NULL
    ALTER TABLE billing_accounts ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('reinsurance_treaties', 'deleted_at') IS NULL
    ALTER TABLE reinsurance_treaties ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('reinsurance_cessions', 'deleted_at') IS NULL
    ALTER TABLE reinsurance_cessions ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('renewal_records', 'deleted_at') IS NULL
    ALTER TABLE renewal_records ADD deleted_at DATETIME2 NULL;

IF COL_LENGTH('mga_authorities', 'deleted_at') IS NULL
    ALTER TABLE mga_authorities ADD deleted_at DATETIME2 NULL;
