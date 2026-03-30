-- Migration 005: Extend the products table with JSON columns for coverages,
-- rating factors, appetite rules, authority limits, territories, forms, and
-- metadata.  Also seed four default products.
--
-- The original products table (001_initial_schema) lacks these columns, so we
-- ALTER it rather than re-create it.
--
-- DOWN MIGRATION (manual rollback):
--   -- Remove seeded products and added columns (order matters):
--   DELETE FROM products WHERE code IN ('cyber-smb', 'cyber-enterprise', 'pi-professional', 'do-directors');
--   ALTER TABLE products DROP COLUMN IF EXISTS code, coverages, rating_factors,
--     appetite_rules, authority_limits, territories, forms, product_metadata;
--   DELETE FROM _migration_history WHERE migration_name = '005_products_table.sql';

-- Add new JSON / metadata columns if they don't already exist
IF COL_LENGTH('products', 'code') IS NULL
    ALTER TABLE products ADD code NVARCHAR(50) NULL;

IF COL_LENGTH('products', 'coverages') IS NULL
    ALTER TABLE products ADD coverages NVARCHAR(MAX) NULL;

IF COL_LENGTH('products', 'rating_factors') IS NULL
    ALTER TABLE products ADD rating_factors NVARCHAR(MAX) NULL;

IF COL_LENGTH('products', 'appetite_rules') IS NULL
    ALTER TABLE products ADD appetite_rules NVARCHAR(MAX) NULL;

IF COL_LENGTH('products', 'authority_limits') IS NULL
    ALTER TABLE products ADD authority_limits NVARCHAR(MAX) NULL;

IF COL_LENGTH('products', 'territories') IS NULL
    ALTER TABLE products ADD territories NVARCHAR(MAX) NULL;

IF COL_LENGTH('products', 'forms') IS NULL
    ALTER TABLE products ADD forms NVARCHAR(MAX) NULL;

IF COL_LENGTH('products', 'metadata') IS NULL
    ALTER TABLE products ADD metadata NVARCHAR(MAX) NULL;

IF COL_LENGTH('products', 'published_at') IS NULL
    ALTER TABLE products ADD published_at DATETIME2 NULL;

IF COL_LENGTH('products', 'created_by') IS NULL
    ALTER TABLE products ADD created_by NVARCHAR(200) NULL;
GO

-- Update status CHECK constraint to include 'sunset' (original had 'filed',
-- 'suspended', 'retired'; the new domain model uses 'draft', 'active', 'sunset').
-- SQL Server doesn't support IF NOT EXISTS on constraints easily, so we drop-and-
-- recreate inside a TRY/CATCH.
BEGIN TRY
    DECLARE @ck_name NVARCHAR(200);
    SELECT @ck_name = name FROM sys.check_constraints
        WHERE parent_object_id = OBJECT_ID('products') AND name LIKE '%status%';
    IF @ck_name IS NOT NULL
        EXEC('ALTER TABLE products DROP CONSTRAINT ' + @ck_name);
    ALTER TABLE products ADD CONSTRAINT CK_products_status
        CHECK (status IN ('draft', 'active', 'sunset', 'filed', 'suspended', 'retired'));
END TRY
BEGIN CATCH
    -- Constraint may already be correct; ignore errors
    PRINT 'Status constraint update skipped: ' + ERROR_MESSAGE();
END CATCH
GO

-- Make code UNIQUE if a unique index doesn't already exist
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID('products') AND name = 'UQ_products_code')
BEGIN
    -- Back-fill code from product_code for any existing rows
    UPDATE products SET code = product_code WHERE code IS NULL AND product_code IS NOT NULL;
    -- Only create index if there are no NULL codes (or table is empty)
    IF NOT EXISTS (SELECT 1 FROM products WHERE code IS NULL)
        CREATE UNIQUE INDEX UQ_products_code ON products (code) WHERE code IS NOT NULL;
END
GO

-- Seed default products (skip if already present)
IF NOT EXISTS (SELECT 1 FROM products WHERE product_code = 'CYBER-SMB-001' OR code = 'CYBER-SMB-001')
INSERT INTO products (id, product_code, code, product_name, line_of_business, description, status, version, coverages, rating_factors, appetite_rules, authority_limits, territories, metadata)
VALUES
(NEWID(), 'CYBER-SMB-001', 'CYBER-SMB-001', 'Cyber Liability — Small & Medium Business', 'cyber',
 'Comprehensive cyber insurance for businesses with revenue under $50M', 'active', 1,
 '[{"code":"BREACH-RESP","name":"First-Party Breach Response","default_limit":1000000,"default_deductible":25000},{"code":"BIZ-INTERRUPT","name":"Business Interruption","default_limit":500000,"default_deductible":50000},{"code":"RANSOM","name":"Cyber Extortion / Ransomware","default_limit":500000,"default_deductible":25000},{"code":"TPL","name":"Third-Party Liability","default_limit":1000000,"default_deductible":25000},{"code":"MEDIA","name":"Media Liability","default_limit":250000,"default_deductible":10000}]',
 '[{"name":"annual_revenue","type":"numeric","weight":0.25},{"name":"employee_count","type":"numeric","weight":0.15},{"name":"security_maturity","type":"numeric","weight":0.25},{"name":"industry","type":"category","weight":0.20},{"name":"prior_incidents","type":"numeric","weight":0.15}]',
 '[{"field":"annual_revenue","operator":"between","value":[500000,50000000]},{"field":"security_maturity_score","operator":"gte","value":4},{"field":"prior_incidents","operator":"lte","value":3}]',
 '{"auto_bind_max":25000,"uw_analyst_max":100000,"senior_uw_max":250000}',
 '["US"]',
 '{"min_premium":2500,"max_premium":500000,"base_rate_per_1000":1.5}');

IF NOT EXISTS (SELECT 1 FROM products WHERE product_code = 'PI-PROF-001' OR code = 'PI-PROF-001')
INSERT INTO products (id, product_code, code, product_name, line_of_business, description, status, version, coverages, rating_factors, appetite_rules, authority_limits, territories, metadata)
VALUES
(NEWID(), 'PI-PROF-001', 'PI-PROF-001', 'Professional Indemnity', 'professional_indemnity',
 'Professional liability coverage for service firms', 'active', 1,
 '[{"code":"PI-CLAIMS","name":"Professional Liability Claims","default_limit":1000000,"default_deductible":10000},{"code":"PI-DEFENSE","name":"Defense Costs","default_limit":500000,"default_deductible":5000}]',
 '[{"name":"annual_revenue","type":"numeric","weight":0.30},{"name":"employee_count","type":"numeric","weight":0.20}]',
 '[]',
 '{"auto_bind_max":15000}',
 '["US"]',
 '{"min_premium":1500}');

IF NOT EXISTS (SELECT 1 FROM products WHERE product_code = 'DO-CORP-001' OR code = 'DO-CORP-001')
INSERT INTO products (id, product_code, code, product_name, line_of_business, description, status, version, coverages, rating_factors, appetite_rules, authority_limits, territories, metadata)
VALUES
(NEWID(), 'DO-CORP-001', 'DO-CORP-001', 'Directors & Officers', 'directors_officers',
 'D&O liability coverage for corporate boards', 'active', 1,
 '[{"code":"DO-SIDE-A","name":"Side A — Individual Directors","default_limit":2000000,"default_deductible":25000},{"code":"DO-SIDE-B","name":"Side B — Corporate Reimbursement","default_limit":2000000,"default_deductible":50000}]',
 '[{"name":"annual_revenue","type":"numeric","weight":0.35}]',
 '[]',
 '{"auto_bind_max":20000}',
 '["US"]',
 '{"min_premium":5000}');

IF NOT EXISTS (SELECT 1 FROM products WHERE product_code = 'TECH-EO-001' OR code = 'TECH-EO-001')
INSERT INTO products (id, product_code, code, product_name, line_of_business, description, status, version, coverages, rating_factors, appetite_rules, authority_limits, territories, metadata)
VALUES
(NEWID(), 'TECH-EO-001', 'TECH-EO-001', 'Technology Errors & Omissions', 'tech_eo',
 'E&O coverage for technology companies', 'draft', 1,
 '[{"code":"TECH-EO","name":"Technology E&O","default_limit":1000000,"default_deductible":15000},{"code":"TECH-MEDIA","name":"Technology Media Liability","default_limit":500000,"default_deductible":10000}]',
 '[{"name":"annual_revenue","type":"numeric","weight":0.30}]',
 '[]',
 '{"auto_bind_max":15000}',
 '["US"]',
 '{"min_premium":2000}');
GO
