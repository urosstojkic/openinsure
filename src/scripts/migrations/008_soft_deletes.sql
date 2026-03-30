-- Migration 008: Soft deletes — add deleted_at to all core tables
-- Idempotent: safe to run multiple times
-- Checks OBJECT_ID before ALTER to handle missing tables gracefully

IF OBJECT_ID('parties', 'U') IS NOT NULL AND COL_LENGTH('parties', 'deleted_at') IS NULL
    ALTER TABLE parties ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('submissions', 'U') IS NOT NULL AND COL_LENGTH('submissions', 'deleted_at') IS NULL
    ALTER TABLE submissions ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('policies', 'U') IS NOT NULL AND COL_LENGTH('policies', 'deleted_at') IS NULL
    ALTER TABLE policies ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('claims', 'U') IS NOT NULL AND COL_LENGTH('claims', 'deleted_at') IS NULL
    ALTER TABLE claims ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('products', 'U') IS NOT NULL AND COL_LENGTH('products', 'deleted_at') IS NULL
    ALTER TABLE products ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('billing_accounts', 'U') IS NOT NULL AND COL_LENGTH('billing_accounts', 'deleted_at') IS NULL
    ALTER TABLE billing_accounts ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('reinsurance_treaties', 'U') IS NOT NULL AND COL_LENGTH('reinsurance_treaties', 'deleted_at') IS NULL
    ALTER TABLE reinsurance_treaties ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('reinsurance_cessions', 'U') IS NOT NULL AND COL_LENGTH('reinsurance_cessions', 'deleted_at') IS NULL
    ALTER TABLE reinsurance_cessions ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('renewal_records', 'U') IS NOT NULL AND COL_LENGTH('renewal_records', 'deleted_at') IS NULL
    ALTER TABLE renewal_records ADD deleted_at DATETIME2 NULL;

IF OBJECT_ID('mga_authorities', 'U') IS NOT NULL AND COL_LENGTH('mga_authorities', 'deleted_at') IS NULL
    ALTER TABLE mga_authorities ADD deleted_at DATETIME2 NULL;
