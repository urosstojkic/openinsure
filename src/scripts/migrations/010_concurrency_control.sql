-- Migration 010: Add optimistic concurrency control (ROWVERSION) columns
-- Issue #159 — idempotent via IF COL_LENGTH checks

IF COL_LENGTH('policies', 'row_version') IS NULL ALTER TABLE policies ADD row_version ROWVERSION;
IF COL_LENGTH('claims', 'row_version') IS NULL ALTER TABLE claims ADD row_version ROWVERSION;
IF COL_LENGTH('submissions', 'row_version') IS NULL ALTER TABLE submissions ADD row_version ROWVERSION;
IF COL_LENGTH('products', 'row_version') IS NULL ALTER TABLE products ADD row_version ROWVERSION;
IF COL_LENGTH('billing_accounts', 'row_version') IS NULL ALTER TABLE billing_accounts ADD row_version ROWVERSION
