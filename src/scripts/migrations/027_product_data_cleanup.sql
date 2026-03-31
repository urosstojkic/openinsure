-- =============================================================================
-- Migration 027: Product Data Cleanup & Comprehensive Seeding
-- Fixes issues: #193, #213, #233, #234, #235, #236, #237, #238, #239, #240,
--               #242, #258, #259, #260, #261, #262, #263
--
-- 1. Removes test products (Test PI Product x2)
-- 2. Removes empty shell products (commercial_property-smb, tech_eo-smb, cyber-smb)
-- 3. Fixes Technology E&O description
-- 4. Seeds coverages, rating factors, appetite rules, authority limits for ALL products
-- 5. Publishes draft products that are complete
-- Idempotent: safe to re-run.
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = '_migration_history')
CREATE TABLE _migration_history (
    migration_name NVARCHAR(200) NOT NULL UNIQUE,
    applied_at DATETIME2 DEFAULT GETUTCDATE()
);
GO

IF EXISTS (SELECT 1 FROM _migration_history WHERE migration_name = '027_product_data_cleanup')
BEGIN
    PRINT 'Migration 027_product_data_cleanup already applied — skipping.';
    RETURN;
END
GO

-- =============================================================================
-- 1. REMOVE TEST PRODUCTS
-- =============================================================================

-- Delete "Test PI Product" entries (test artifacts)
DELETE FROM product_coverages WHERE product_id IN (SELECT id FROM products WHERE product_name = 'Test PI Product');
DELETE FROM product_rating_factors WHERE product_id IN (SELECT id FROM products WHERE product_name = 'Test PI Product');
DELETE FROM rating_factor_tables WHERE product_id IN (SELECT id FROM products WHERE product_name = 'Test PI Product');
DELETE FROM product_appetite_rules WHERE product_id IN (SELECT id FROM products WHERE product_name = 'Test PI Product');
DELETE FROM product_authority_limits WHERE product_id IN (SELECT id FROM products WHERE product_name = 'Test PI Product');
DELETE FROM product_territories WHERE product_id IN (SELECT id FROM products WHERE product_name = 'Test PI Product');
DELETE FROM product_forms WHERE product_id IN (SELECT id FROM products WHERE product_name = 'Test PI Product');
DELETE FROM product_pricing WHERE product_id IN (SELECT id FROM products WHERE product_name = 'Test PI Product');
-- Soft-delete the product records
UPDATE products SET deleted_at = GETUTCDATE() WHERE product_name = 'Test PI Product' AND deleted_at IS NULL;
GO

-- =============================================================================
-- 2. REMOVE EMPTY SHELL / WRONG LOB PRODUCTS
-- =============================================================================

-- commercial_property-smb: wrong LOB (cyber instead of commercial_property), slug name, no data
UPDATE products SET deleted_at = GETUTCDATE()
WHERE product_name = 'commercial_property-smb' AND deleted_at IS NULL;
GO

-- tech_eo-smb: wrong LOB (cyber instead of tech_eo), slug name, no data
UPDATE products SET deleted_at = GETUTCDATE()
WHERE product_name = 'tech_eo-smb' AND deleted_at IS NULL;
GO

-- cyber-smb: slug name, no data, duplicate of Cyber Liability SMB
UPDATE products SET deleted_at = GETUTCDATE()
WHERE product_name = 'cyber-smb' AND deleted_at IS NULL;
GO

-- =============================================================================
-- 3. FIX TECHNOLOGY E&O DESCRIPTION
-- =============================================================================

UPDATE products
SET description = 'Technology Errors & Omissions coverage for technology companies, protecting against claims arising from software failures, service delivery errors, intellectual property infringement, and professional negligence in technology services.',
    updated_at = GETUTCDATE()
WHERE product_name = 'Technology Errors & Omissions'
  AND (description LIKE '%func test%' OR description LIKE '%Updated by%' OR description = 'Updated');
GO

-- =============================================================================
-- 4. SEED CYBER LIABILITY SMB — Rating Factors + Authority Limits
-- =============================================================================

DECLARE @cyber_id UNIQUEIDENTIFIER;
SELECT @cyber_id = id FROM products
WHERE product_name LIKE 'Cyber Liability%' AND deleted_at IS NULL;

IF @cyber_id IS NOT NULL
BEGIN
    -- Rating factor definitions
    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @cyber_id AND factor_name = 'industry')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@cyber_id, 'industry', 'string', 0.3000, 'Industry sector impacts cyber risk exposure', 1);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @cyber_id AND factor_name = 'revenue_band')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@cyber_id, 'revenue_band', 'string', 0.2000, 'Annual revenue determines exposure size', 2);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @cyber_id AND factor_name = 'security_maturity')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@cyber_id, 'security_maturity', 'numeric', 0.2500, 'Security posture maturity score (1-10)', 3);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @cyber_id AND factor_name = 'data_sensitivity')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@cyber_id, 'data_sensitivity', 'string', 0.1500, 'Type and sensitivity of data handled', 4);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @cyber_id AND factor_name = 'prior_incidents')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@cyber_id, 'prior_incidents', 'numeric', 0.1000, 'Number of prior cyber incidents in 3 years', 5);

    -- Rating factor lookup tables
    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @cyber_id AND factor_category = 'industry')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@cyber_id, 'industry', 'technology',     1.3000, 'Technology — high digital exposure',           CAST(GETUTCDATE() AS DATE), 1),
            (@cyber_id, 'industry', 'healthcare',     1.5000, 'Healthcare — PHI/HIPAA exposure',              CAST(GETUTCDATE() AS DATE), 2),
            (@cyber_id, 'industry', 'financial',      1.4000, 'Financial services — PCI/SOX exposure',        CAST(GETUTCDATE() AS DATE), 3),
            (@cyber_id, 'industry', 'retail',          1.2000, 'Retail — PCI and consumer data exposure',     CAST(GETUTCDATE() AS DATE), 4),
            (@cyber_id, 'industry', 'manufacturing',  0.9000, 'Manufacturing — lower digital exposure',       CAST(GETUTCDATE() AS DATE), 5),
            (@cyber_id, 'industry', 'professional',   1.0000, 'Professional services — baseline',             CAST(GETUTCDATE() AS DATE), 6),
            (@cyber_id, 'industry', 'education',      1.1000, 'Education — student data exposure',            CAST(GETUTCDATE() AS DATE), 7);
    END

    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @cyber_id AND factor_category = 'revenue_band')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@cyber_id, 'revenue_band', '0-1M',    0.7000, 'Micro business — minimal exposure',     CAST(GETUTCDATE() AS DATE), 1),
            (@cyber_id, 'revenue_band', '1-5M',    0.9000, 'Small business — limited exposure',      CAST(GETUTCDATE() AS DATE), 2),
            (@cyber_id, 'revenue_band', '5-25M',   1.0000, 'Mid-market — baseline',                  CAST(GETUTCDATE() AS DATE), 3),
            (@cyber_id, 'revenue_band', '25-100M', 1.3000, 'Upper mid-market — significant exposure', CAST(GETUTCDATE() AS DATE), 4),
            (@cyber_id, 'revenue_band', '100M+',   1.6000, 'Large enterprise — maximum exposure',    CAST(GETUTCDATE() AS DATE), 5);
    END

    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @cyber_id AND factor_category = 'security_maturity')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@cyber_id, 'security_maturity', '1-3',  1.5000, 'Low maturity — significant risk premium',  CAST(GETUTCDATE() AS DATE), 1),
            (@cyber_id, 'security_maturity', '4-6',  1.0000, 'Average maturity — baseline',              CAST(GETUTCDATE() AS DATE), 2),
            (@cyber_id, 'security_maturity', '7-8',  0.8000, 'Above average — modest discount',          CAST(GETUTCDATE() AS DATE), 3),
            (@cyber_id, 'security_maturity', '9-10', 0.6000, 'Excellent — maximum discount',             CAST(GETUTCDATE() AS DATE), 4);
    END

    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @cyber_id AND factor_category = 'data_sensitivity')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@cyber_id, 'data_sensitivity', 'public',        0.7000, 'Mostly public data — low breach impact',    CAST(GETUTCDATE() AS DATE), 1),
            (@cyber_id, 'data_sensitivity', 'internal',      1.0000, 'Internal business data — baseline',          CAST(GETUTCDATE() AS DATE), 2),
            (@cyber_id, 'data_sensitivity', 'pii',           1.3000, 'Personal Identifiable Information',          CAST(GETUTCDATE() AS DATE), 3),
            (@cyber_id, 'data_sensitivity', 'phi',           1.5000, 'Protected Health Information — HIPAA',       CAST(GETUTCDATE() AS DATE), 4),
            (@cyber_id, 'data_sensitivity', 'financial',     1.4000, 'Financial data — PCI/SOX',                   CAST(GETUTCDATE() AS DATE), 5);
    END

    -- Authority limits
    IF NOT EXISTS (SELECT 1 FROM product_authority_limits WHERE product_id = @cyber_id)
    INSERT INTO product_authority_limits (product_id, auto_bind_premium_max, auto_bind_limit_max, requires_senior_review_above, requires_cuo_review_above)
    VALUES (@cyber_id, 25000.00, 5000000.00, 75000.00, 250000.00);
    ELSE
    UPDATE product_authority_limits
    SET auto_bind_premium_max = 25000.00, auto_bind_limit_max = 5000000.00,
        requires_senior_review_above = 75000.00, requires_cuo_review_above = 250000.00
    WHERE product_id = @cyber_id AND auto_bind_premium_max = 0;
END
GO

-- =============================================================================
-- 5. SEED TECHNOLOGY E&O — Full Product Data
-- =============================================================================

DECLARE @teo_id UNIQUEIDENTIFIER;
SELECT @teo_id = id FROM products
WHERE product_name = 'Technology Errors & Omissions' AND deleted_at IS NULL;

IF @teo_id IS NOT NULL
BEGIN
    -- Coverages (may already have 2, add more if missing)
    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @teo_id AND coverage_code = 'TECH-EO-PRO')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@teo_id, 'TECH-EO-PRO', 'Professional Services E&O',
        'Covers claims arising from errors, omissions, or negligent acts in providing technology professional services',
        2000000.00, 10000000.00, 25000.00, 0, 1);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @teo_id AND coverage_code = 'TECH-EO-PROD')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@teo_id, 'TECH-EO-PROD', 'Technology Product Liability',
        'Covers claims arising from defects or failures in technology products including software, hardware, and SaaS platforms',
        2000000.00, 10000000.00, 25000.00, 0, 2);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @teo_id AND coverage_code = 'TECH-EO-IP')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@teo_id, 'TECH-EO-IP', 'Intellectual Property Defense',
        'Covers defense costs for claims of IP infringement including patent, copyright, and trade secret misappropriation',
        1000000.00, 5000000.00, 50000.00, 1, 3);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @teo_id AND coverage_code = 'TECH-EO-MEDIA')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@teo_id, 'TECH-EO-MEDIA', 'Technology Media Liability',
        'Covers claims of defamation, invasion of privacy, and copyright infringement in digital media and content',
        1000000.00, 5000000.00, 10000.00, 1, 4);

    -- Rating factor definitions
    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @teo_id AND factor_name = 'tech_sector')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@teo_id, 'tech_sector', 'string', 0.2500, 'Technology sector specialization', 1);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @teo_id AND factor_name = 'revenue_band')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@teo_id, 'revenue_band', 'string', 0.2000, 'Annual revenue determines exposure size', 2);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @teo_id AND factor_name = 'contract_terms')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@teo_id, 'contract_terms', 'string', 0.2000, 'Standard contract terms quality (limitation of liability)', 3);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @teo_id AND factor_name = 'claims_history')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@teo_id, 'claims_history', 'numeric', 0.2000, 'Prior E&O claims history (3 years)', 4);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @teo_id AND factor_name = 'client_concentration')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@teo_id, 'client_concentration', 'numeric', 0.1500, 'Revenue concentration in top 3 clients', 5);

    -- Rating factor lookup tables
    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @teo_id AND factor_category = 'tech_sector')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@teo_id, 'tech_sector', 'saas',         1.2000, 'SaaS — high availability expectations',         CAST(GETUTCDATE() AS DATE), 1),
            (@teo_id, 'tech_sector', 'consulting',   1.0000, 'IT consulting — baseline',                       CAST(GETUTCDATE() AS DATE), 2),
            (@teo_id, 'tech_sector', 'fintech',      1.4000, 'FinTech — regulatory and financial exposure',    CAST(GETUTCDATE() AS DATE), 3),
            (@teo_id, 'tech_sector', 'healthtech',   1.3000, 'HealthTech — PHI and patient safety exposure',   CAST(GETUTCDATE() AS DATE), 4),
            (@teo_id, 'tech_sector', 'ecommerce',    1.1000, 'E-commerce — transaction and data exposure',     CAST(GETUTCDATE() AS DATE), 5),
            (@teo_id, 'tech_sector', 'infrastructure',1.2000, 'Infrastructure — uptime criticality',           CAST(GETUTCDATE() AS DATE), 6);
    END

    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @teo_id AND factor_category = 'revenue_band')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@teo_id, 'revenue_band', '0-1M',    0.7000, 'Micro business — minimal exposure',          CAST(GETUTCDATE() AS DATE), 1),
            (@teo_id, 'revenue_band', '1-5M',    0.9000, 'Small business — limited project scope',     CAST(GETUTCDATE() AS DATE), 2),
            (@teo_id, 'revenue_band', '5-25M',   1.0000, 'Mid-market — baseline',                      CAST(GETUTCDATE() AS DATE), 3),
            (@teo_id, 'revenue_band', '25-100M', 1.3000, 'Upper mid-market — larger engagements',      CAST(GETUTCDATE() AS DATE), 4),
            (@teo_id, 'revenue_band', '100M+',   1.5000, 'Enterprise — maximum exposure',              CAST(GETUTCDATE() AS DATE), 5);
    END

    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @teo_id AND factor_category = 'contract_terms')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@teo_id, 'contract_terms', 'strong',   0.8000, 'Strong limitation of liability clauses',    CAST(GETUTCDATE() AS DATE), 1),
            (@teo_id, 'contract_terms', 'standard', 1.0000, 'Standard industry terms — baseline',        CAST(GETUTCDATE() AS DATE), 2),
            (@teo_id, 'contract_terms', 'weak',     1.3000, 'Weak or no limitation of liability',        CAST(GETUTCDATE() AS DATE), 3);
    END

    -- Appetite rules
    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @teo_id AND rule_name = 'revenue_range')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_min, numeric_max, description, sort_order)
    VALUES (@teo_id, 'revenue_range', 'annual_revenue', 'between', 'numeric', 250000.00, 100000000.00,
        'Annual revenue must be between $250K and $100M', 1);

    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @teo_id AND rule_name = 'years_in_business')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_value, description, sort_order)
    VALUES (@teo_id, 'years_in_business', 'years_in_business', '>=', 'numeric', 2.00,
        'Minimum 2 years in business required', 2);

    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @teo_id AND rule_name = 'prior_claims_max')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_value, description, sort_order)
    VALUES (@teo_id, 'prior_claims_max', 'prior_eo_claims', '<=', 'numeric', 2.00,
        'Maximum 2 prior E&O claims in 5 years', 3);

    -- Authority limits
    IF NOT EXISTS (SELECT 1 FROM product_authority_limits WHERE product_id = @teo_id)
    INSERT INTO product_authority_limits (product_id, auto_bind_premium_max, auto_bind_limit_max, requires_senior_review_above, requires_cuo_review_above)
    VALUES (@teo_id, 20000.00, 5000000.00, 60000.00, 200000.00);
    ELSE
    UPDATE product_authority_limits
    SET auto_bind_premium_max = 20000.00, auto_bind_limit_max = 5000000.00,
        requires_senior_review_above = 60000.00, requires_cuo_review_above = 200000.00
    WHERE product_id = @teo_id AND (auto_bind_premium_max = 0 OR auto_bind_premium_max IS NULL);

    -- Territory
    IF NOT EXISTS (SELECT 1 FROM product_territories WHERE product_id = @teo_id AND territory_code = 'US')
    INSERT INTO product_territories (product_id, territory_code, approval_status, effective_date)
    VALUES (@teo_id, 'US', 'approved', CAST(GETUTCDATE() AS DATE));

    -- Publish (draft → active)
    UPDATE products SET status = 'active', updated_at = GETUTCDATE()
    WHERE id = @teo_id AND status = 'draft';
END
GO

-- =============================================================================
-- 6. SEED DIRECTORS & OFFICERS — Full Product Data
-- =============================================================================

DECLARE @do_id UNIQUEIDENTIFIER;
SELECT @do_id = id FROM products
WHERE product_name = 'Directors & Officers' AND deleted_at IS NULL;

IF @do_id IS NOT NULL
BEGIN
    -- Update description if empty
    UPDATE products SET description = 'Directors & Officers liability coverage protecting corporate directors, officers, and the organization from claims of wrongful acts, mismanagement, regulatory violations, and shareholder disputes.'
    WHERE id = @do_id AND (description IS NULL OR description = '' OR description = 'Updated');

    -- Coverages
    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @do_id AND coverage_code = 'DO-SIDE-A')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@do_id, 'DO-SIDE-A', 'Side A — Individual Directors & Officers',
        'Non-indemnifiable loss coverage protecting individual directors and officers when the company cannot or will not indemnify them',
        5000000.00, 25000000.00, 0.00, 0, 1);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @do_id AND coverage_code = 'DO-SIDE-B')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@do_id, 'DO-SIDE-B', 'Side B — Corporate Reimbursement',
        'Reimburses the company for amounts paid to indemnify directors and officers for covered claims',
        5000000.00, 25000000.00, 50000.00, 0, 2);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @do_id AND coverage_code = 'DO-SIDE-C')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@do_id, 'DO-SIDE-C', 'Side C — Entity Securities Coverage',
        'Covers the company itself for securities claims brought against it (typically for public companies)',
        5000000.00, 25000000.00, 100000.00, 1, 3);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @do_id AND coverage_code = 'DO-EPL')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@do_id, 'DO-EPL', 'Employment Practices Liability',
        'Covers claims of wrongful termination, discrimination, harassment, and other employment-related wrongful acts',
        2000000.00, 10000000.00, 25000.00, 1, 4);

    -- Rating factor definitions
    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @do_id AND factor_name = 'company_type')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@do_id, 'company_type', 'string', 0.2500, 'Public, private, or non-profit entity type', 1);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @do_id AND factor_name = 'revenue_band')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@do_id, 'revenue_band', 'string', 0.2000, 'Annual revenue determines exposure size', 2);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @do_id AND factor_name = 'industry_sector')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@do_id, 'industry_sector', 'string', 0.2000, 'Industry affects regulatory and litigation exposure', 3);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @do_id AND factor_name = 'board_size')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@do_id, 'board_size', 'numeric', 0.1500, 'Number of directors and officers', 4);

    -- Rating factor lookup tables
    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @do_id AND factor_category = 'company_type')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@do_id, 'company_type', 'public',     1.5000, 'Public company — securities litigation exposure',  CAST(GETUTCDATE() AS DATE), 1),
            (@do_id, 'company_type', 'private',    1.0000, 'Private company — baseline',                        CAST(GETUTCDATE() AS DATE), 2),
            (@do_id, 'company_type', 'non_profit', 0.8000, 'Non-profit — lower litigation exposure',           CAST(GETUTCDATE() AS DATE), 3);
    END

    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @do_id AND factor_category = 'revenue_band')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@do_id, 'revenue_band', '0-10M',    0.8000, 'Small company — limited exposure',         CAST(GETUTCDATE() AS DATE), 1),
            (@do_id, 'revenue_band', '10-50M',   1.0000, 'Mid-market — baseline',                    CAST(GETUTCDATE() AS DATE), 2),
            (@do_id, 'revenue_band', '50-250M',  1.3000, 'Upper mid-market — increased exposure',    CAST(GETUTCDATE() AS DATE), 3),
            (@do_id, 'revenue_band', '250M+',    1.6000, 'Large company — maximum exposure',         CAST(GETUTCDATE() AS DATE), 4);
    END

    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @do_id AND factor_category = 'industry_sector')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@do_id, 'industry_sector', 'financial',       1.4000, 'Financial services — high regulatory exposure',   CAST(GETUTCDATE() AS DATE), 1),
            (@do_id, 'industry_sector', 'healthcare',      1.3000, 'Healthcare — compliance and patient safety',      CAST(GETUTCDATE() AS DATE), 2),
            (@do_id, 'industry_sector', 'technology',      1.2000, 'Technology — IP and securities litigation',       CAST(GETUTCDATE() AS DATE), 3),
            (@do_id, 'industry_sector', 'manufacturing',   1.0000, 'Manufacturing — baseline',                        CAST(GETUTCDATE() AS DATE), 4),
            (@do_id, 'industry_sector', 'retail',          0.9000, 'Retail — lower litigation frequency',             CAST(GETUTCDATE() AS DATE), 5);
    END

    -- Appetite rules
    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @do_id AND rule_name = 'revenue_range')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_min, numeric_max, description, sort_order)
    VALUES (@do_id, 'revenue_range', 'annual_revenue', 'between', 'numeric', 1000000.00, 500000000.00,
        'Annual revenue must be between $1M and $500M', 1);

    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @do_id AND rule_name = 'years_in_operation')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_value, description, sort_order)
    VALUES (@do_id, 'years_in_operation', 'years_in_business', '>=', 'numeric', 3.00,
        'Minimum 3 years in operation required', 2);

    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @do_id AND rule_name = 'no_bankruptcy')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, string_value, description, sort_order)
    VALUES (@do_id, 'no_bankruptcy', 'bankruptcy_history', 'not_in', 'string', 'yes,true,1',
        'No bankruptcy filings in the past 5 years', 3);

    -- Authority limits
    IF NOT EXISTS (SELECT 1 FROM product_authority_limits WHERE product_id = @do_id)
    INSERT INTO product_authority_limits (product_id, auto_bind_premium_max, auto_bind_limit_max, requires_senior_review_above, requires_cuo_review_above)
    VALUES (@do_id, 30000.00, 10000000.00, 100000.00, 500000.00);
    ELSE
    UPDATE product_authority_limits
    SET auto_bind_premium_max = 30000.00, auto_bind_limit_max = 10000000.00,
        requires_senior_review_above = 100000.00, requires_cuo_review_above = 500000.00
    WHERE product_id = @do_id AND (auto_bind_premium_max = 0 OR auto_bind_premium_max IS NULL);

    -- Territory
    IF NOT EXISTS (SELECT 1 FROM product_territories WHERE product_id = @do_id AND territory_code = 'US')
    INSERT INTO product_territories (product_id, territory_code, approval_status, effective_date)
    VALUES (@do_id, 'US', 'approved', CAST(GETUTCDATE() AS DATE));

    -- Publish (draft → active)
    UPDATE products SET status = 'active', updated_at = GETUTCDATE()
    WHERE id = @do_id AND status = 'draft';
END
GO

-- =============================================================================
-- 7. SEED PROFESSIONAL INDEMNITY — Full Product Data
-- =============================================================================

DECLARE @pi_id UNIQUEIDENTIFIER;
SELECT @pi_id = id FROM products
WHERE product_name = 'Professional Indemnity' AND deleted_at IS NULL;

IF @pi_id IS NOT NULL
BEGIN
    -- Update description if empty
    UPDATE products SET description = 'Professional Indemnity insurance covering professionals against claims of negligence, breach of duty, errors, and omissions in professional services delivery.'
    WHERE id = @pi_id AND (description IS NULL OR description = '' OR description = 'Updated');

    -- Coverages
    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @pi_id AND coverage_code = 'PI-PROF')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@pi_id, 'PI-PROF', 'Professional Negligence',
        'Covers claims of professional negligence, errors, and omissions in delivering professional services',
        2000000.00, 10000000.00, 10000.00, 0, 1);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @pi_id AND coverage_code = 'PI-BREACH')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@pi_id, 'PI-BREACH', 'Breach of Professional Duty',
        'Covers claims for breach of duty of care, fiduciary duty, and contractual obligations',
        2000000.00, 10000000.00, 10000.00, 0, 2);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @pi_id AND coverage_code = 'PI-DEFENSE')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@pi_id, 'PI-DEFENSE', 'Legal Defense Costs',
        'Covers legal defense expenses including attorney fees, court costs, and expert witness fees',
        1000000.00, 5000000.00, 5000.00, 0, 3);

    IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @pi_id AND coverage_code = 'PI-LOSS-DOC')
    INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
    VALUES (@pi_id, 'PI-LOSS-DOC', 'Loss of Documents',
        'Covers costs to reconstruct, restore, or replace documents lost or damaged while in the insured professional care',
        500000.00, 2000000.00, 5000.00, 1, 4);

    -- Rating factor definitions
    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @pi_id AND factor_name = 'profession_type')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@pi_id, 'profession_type', 'string', 0.3000, 'Type of professional practice', 1);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @pi_id AND factor_name = 'revenue_band')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@pi_id, 'revenue_band', 'string', 0.2000, 'Annual fee income determines exposure', 2);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @pi_id AND factor_name = 'years_qualified')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@pi_id, 'years_qualified', 'numeric', 0.1500, 'Years of professional qualification/experience', 3);

    IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @pi_id AND factor_name = 'claims_history')
    INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
    VALUES (@pi_id, 'claims_history', 'numeric', 0.2000, 'Prior PI claims history (5 years)', 4);

    -- Rating factor lookup tables
    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @pi_id AND factor_category = 'profession_type')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@pi_id, 'profession_type', 'accountant',   1.0000, 'Accountant — baseline',                        CAST(GETUTCDATE() AS DATE), 1),
            (@pi_id, 'profession_type', 'architect',     1.2000, 'Architect — design liability exposure',        CAST(GETUTCDATE() AS DATE), 2),
            (@pi_id, 'profession_type', 'engineer',      1.3000, 'Engineer — structural/safety exposure',        CAST(GETUTCDATE() AS DATE), 3),
            (@pi_id, 'profession_type', 'consultant',    1.1000, 'Management consultant — advisory exposure',    CAST(GETUTCDATE() AS DATE), 4),
            (@pi_id, 'profession_type', 'surveyor',      1.2000, 'Surveyor — valuation/assessment exposure',     CAST(GETUTCDATE() AS DATE), 5),
            (@pi_id, 'profession_type', 'financial',     1.4000, 'Financial advisor — fiduciary exposure',       CAST(GETUTCDATE() AS DATE), 6);
    END

    IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @pi_id AND factor_category = 'revenue_band')
    BEGIN
        INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
        VALUES
            (@pi_id, 'revenue_band', '0-500K',   0.7000, 'Small practice — limited exposure',         CAST(GETUTCDATE() AS DATE), 1),
            (@pi_id, 'revenue_band', '500K-2M',  1.0000, 'Medium practice — baseline',                CAST(GETUTCDATE() AS DATE), 2),
            (@pi_id, 'revenue_band', '2M-10M',   1.2000, 'Large practice — increased exposure',       CAST(GETUTCDATE() AS DATE), 3),
            (@pi_id, 'revenue_band', '10M+',     1.5000, 'Major firm — maximum exposure',             CAST(GETUTCDATE() AS DATE), 4);
    END

    -- Appetite rules
    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @pi_id AND rule_name = 'fee_income_range')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_min, numeric_max, description, sort_order)
    VALUES (@pi_id, 'fee_income_range', 'annual_revenue', 'between', 'numeric', 100000.00, 50000000.00,
        'Annual fee income must be between $100K and $50M', 1);

    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @pi_id AND rule_name = 'years_practicing')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_value, description, sort_order)
    VALUES (@pi_id, 'years_practicing', 'years_in_business', '>=', 'numeric', 1.00,
        'Minimum 1 year in professional practice', 2);

    IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @pi_id AND rule_name = 'prior_claims_max')
    INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_value, description, sort_order)
    VALUES (@pi_id, 'prior_claims_max', 'prior_pi_claims', '<=', 'numeric', 3.00,
        'Maximum 3 prior PI claims in 5 years', 3);

    -- Authority limits
    IF NOT EXISTS (SELECT 1 FROM product_authority_limits WHERE product_id = @pi_id)
    INSERT INTO product_authority_limits (product_id, auto_bind_premium_max, auto_bind_limit_max, requires_senior_review_above, requires_cuo_review_above)
    VALUES (@pi_id, 15000.00, 5000000.00, 50000.00, 200000.00);
    ELSE
    UPDATE product_authority_limits
    SET auto_bind_premium_max = 15000.00, auto_bind_limit_max = 5000000.00,
        requires_senior_review_above = 50000.00, requires_cuo_review_above = 200000.00
    WHERE product_id = @pi_id AND (auto_bind_premium_max = 0 OR auto_bind_premium_max IS NULL);

    -- Territory
    IF NOT EXISTS (SELECT 1 FROM product_territories WHERE product_id = @pi_id AND territory_code = 'US')
    INSERT INTO product_territories (product_id, territory_code, approval_status, effective_date)
    VALUES (@pi_id, 'US', 'approved', CAST(GETUTCDATE() AS DATE));
END
GO

-- =============================================================================
-- 8. UPDATE COMMERCIAL PROPERTY — Fix authority_limits if auto_bind_limit_max is 0
-- =============================================================================

DECLARE @cp_id UNIQUEIDENTIFIER;
SELECT @cp_id = id FROM products
WHERE product_name = 'Commercial Property' AND deleted_at IS NULL;

IF @cp_id IS NOT NULL
BEGIN
    UPDATE product_authority_limits
    SET auto_bind_limit_max = 10000000.00
    WHERE product_id = @cp_id AND (auto_bind_limit_max IS NULL OR auto_bind_limit_max = 0);
END
GO

-- =============================================================================
-- 9. RECORD MIGRATION
-- =============================================================================

INSERT INTO _migration_history (migration_name) VALUES ('027_product_data_cleanup');
GO

PRINT 'Migration 027_product_data_cleanup applied successfully.';
GO
