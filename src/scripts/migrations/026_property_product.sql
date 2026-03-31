-- =============================================================================
-- Migration 026: Commercial Property Product
-- Seeds a comprehensive Commercial Property insurance product using the
-- relational tables created in migration 015 (product normalization).
-- Proves LOB-agnostic architecture: completely different from Cyber.
-- Idempotent: safe to re-run (IF EXISTS guards).
-- =============================================================================

-- Migration tracking
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = '_migration_history')
CREATE TABLE _migration_history (
    migration_name NVARCHAR(200) NOT NULL UNIQUE,
    applied_at DATETIME2 DEFAULT GETUTCDATE()
);
GO

IF EXISTS (SELECT 1 FROM _migration_history WHERE migration_name = '026_property_product')
BEGIN
    PRINT 'Migration 026_property_product already applied — skipping.';
    RETURN;
END
GO

-- =============================================================================
-- 1. PRODUCT RECORD
-- =============================================================================
DECLARE @prop_id UNIQUEIDENTIFIER = NEWID();

IF NOT EXISTS (SELECT 1 FROM products WHERE product_code = 'PROP-COMM-001')
BEGIN
    INSERT INTO products (id, product_code, code, product_name, line_of_business, description, status, version, effective_date)
    VALUES (
        @prop_id,
        'PROP-COMM-001',
        'PROP-COMM-001',
        'Commercial Property',
        'commercial_property',
        'All-risk commercial property coverage for buildings, contents, and business income',
        'active',
        1,
        GETUTCDATE()
    );
END
ELSE
BEGIN
    SELECT @prop_id = id FROM products WHERE product_code = 'PROP-COMM-001';
END

-- =============================================================================
-- 2. COVERAGES (6 — very different from Cyber)
-- =============================================================================

-- 2a. Building Coverage
IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @prop_id AND coverage_code = 'BLDG-COV')
INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
VALUES (@prop_id, 'BLDG-COV', 'Building Coverage',
    'Covers the insured building structure against all-risk perils including fire, wind, hail, and vandalism',
    5000000.00, 50000000.00, 10000.00, 0, 1);

-- 2b. Business Personal Property
IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @prop_id AND coverage_code = 'BPP')
INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
VALUES (@prop_id, 'BPP', 'Business Personal Property',
    'Covers furniture, equipment, inventory, and other business personal property',
    1000000.00, 10000000.00, 5000.00, 0, 2);

-- 2c. Business Income / Extra Expense
IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @prop_id AND coverage_code = 'BI-EE')
INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
VALUES (@prop_id, 'BI-EE', 'Business Income / Extra Expense',
    'Covers lost income and extra expenses when business operations are interrupted by a covered peril. Deductible expressed as 72-hour waiting period.',
    500000.00, 5000000.00, 0.00, 0, 3);

-- 2d. Equipment Breakdown
IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @prop_id AND coverage_code = 'EQUIP-BD')
INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
VALUES (@prop_id, 'EQUIP-BD', 'Equipment Breakdown',
    'Covers mechanical and electrical breakdown of boilers, HVAC, electrical panels, and production equipment',
    500000.00, 5000000.00, 5000.00, 0, 4);

-- 2e. Ordinance or Law
IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @prop_id AND coverage_code = 'ORD-LAW')
INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
VALUES (@prop_id, 'ORD-LAW', 'Ordinance or Law',
    'Covers increased costs to comply with building codes and ordinances after a covered loss',
    250000.00, 2500000.00, 0.00, 0, 5);

-- 2f. Flood (optional)
IF NOT EXISTS (SELECT 1 FROM product_coverages WHERE product_id = @prop_id AND coverage_code = 'FLOOD')
INSERT INTO product_coverages (product_id, coverage_code, coverage_name, description, default_limit, max_limit, default_deductible, is_optional, sort_order)
VALUES (@prop_id, 'FLOOD', 'Flood',
    'Optional flood coverage for buildings and contents in flood-prone areas',
    1000000.00, 10000000.00, 25000.00, 1, 6);

-- =============================================================================
-- 3. RATING FACTORS (property-specific — different from Cyber)
-- =============================================================================

-- 3a. Construction Type factor definition
IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @prop_id AND factor_name = 'construction_type')
INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
VALUES (@prop_id, 'construction_type', 'string', 0.2500, 'Building construction material impacts fire and structural risk', 1);

-- Construction type multiplier lookup values
IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @prop_id AND factor_category = 'construction_type')
BEGIN
    INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
    VALUES
        (@prop_id, 'construction_type', 'frame',                  1.8000, 'Wood-frame construction — highest fire risk', CAST(GETUTCDATE() AS DATE), 1),
        (@prop_id, 'construction_type', 'joisted_masonry',        1.2000, 'Joisted masonry — moderate fire risk',        CAST(GETUTCDATE() AS DATE), 2),
        (@prop_id, 'construction_type', 'masonry',                1.0000, 'Non-combustible masonry — baseline',          CAST(GETUTCDATE() AS DATE), 3),
        (@prop_id, 'construction_type', 'fire_resistive',         0.7000, 'Fire-resistive — lowest risk',                CAST(GETUTCDATE() AS DATE), 4),
        (@prop_id, 'construction_type', 'modified_fire_resistive',0.8000, 'Modified fire-resistive — low risk',          CAST(GETUTCDATE() AS DATE), 5);
END

-- 3b. Fire Protection Class factor definition
IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @prop_id AND factor_name = 'fire_protection_class')
INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
VALUES (@prop_id, 'fire_protection_class', 'numeric', 0.2000, 'ISO fire protection class rating (1=best, 10=worst)', 2);

IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @prop_id AND factor_category = 'fire_protection_class')
BEGIN
    INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
    VALUES
        (@prop_id, 'fire_protection_class', '1-3',  0.8000, 'Excellent fire protection — well-served area',     CAST(GETUTCDATE() AS DATE), 1),
        (@prop_id, 'fire_protection_class', '4-6',  1.0000, 'Average fire protection — baseline',               CAST(GETUTCDATE() AS DATE), 2),
        (@prop_id, 'fire_protection_class', '7-8',  1.3000, 'Below average fire protection — rural or limited', CAST(GETUTCDATE() AS DATE), 3),
        (@prop_id, 'fire_protection_class', '9-10', 2.0000, 'Poor fire protection — unprotected area',          CAST(GETUTCDATE() AS DATE), 4);
END

-- 3c. Building Age factor definition
IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @prop_id AND factor_name = 'building_age')
INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
VALUES (@prop_id, 'building_age', 'numeric', 0.1500, 'Years since construction — older buildings have higher loss potential', 3);

IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @prop_id AND factor_category = 'building_age')
BEGIN
    INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
    VALUES
        (@prop_id, 'building_age', '0-10',  0.9000, 'New construction — modern codes',         CAST(GETUTCDATE() AS DATE), 1),
        (@prop_id, 'building_age', '10-30', 1.0000, 'Standard age — baseline',                 CAST(GETUTCDATE() AS DATE), 2),
        (@prop_id, 'building_age', '30-50', 1.2000, 'Aging building — increased maintenance',  CAST(GETUTCDATE() AS DATE), 3),
        (@prop_id, 'building_age', '50+',   1.5000, 'Older building — highest risk of issues', CAST(GETUTCDATE() AS DATE), 4);
END

-- 3d. Occupancy Type factor definition
IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @prop_id AND factor_name = 'occupancy_type')
INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
VALUES (@prop_id, 'occupancy_type', 'string', 0.2000, 'Type of business occupying the building', 4);

IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @prop_id AND factor_category = 'occupancy_type')
BEGIN
    INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
    VALUES
        (@prop_id, 'occupancy_type', 'office',        0.8000, 'Office — low combustible content',          CAST(GETUTCDATE() AS DATE), 1),
        (@prop_id, 'occupancy_type', 'retail',         1.0000, 'Retail — moderate risk baseline',          CAST(GETUTCDATE() AS DATE), 2),
        (@prop_id, 'occupancy_type', 'restaurant',     1.5000, 'Restaurant — cooking fire exposure',       CAST(GETUTCDATE() AS DATE), 3),
        (@prop_id, 'occupancy_type', 'manufacturing',  1.3000, 'Manufacturing — machinery and materials',  CAST(GETUTCDATE() AS DATE), 4),
        (@prop_id, 'occupancy_type', 'warehouse',      1.1000, 'Warehouse — storage concentration',       CAST(GETUTCDATE() AS DATE), 5);
END

-- 3e. Sprinkler System factor definition
IF NOT EXISTS (SELECT 1 FROM product_rating_factors WHERE product_id = @prop_id AND factor_name = 'sprinkler_system')
INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
VALUES (@prop_id, 'sprinkler_system', 'boolean', 0.1000, 'Automatic sprinkler system present', 5);

IF NOT EXISTS (SELECT 1 FROM rating_factor_tables WHERE product_id = @prop_id AND factor_category = 'sprinkler_system')
BEGIN
    INSERT INTO rating_factor_tables (product_id, factor_category, factor_key, multiplier, description, effective_date, sort_order)
    VALUES
        (@prop_id, 'sprinkler_system', 'yes', 0.7000, 'Full automatic sprinkler system — significant fire risk reduction', CAST(GETUTCDATE() AS DATE), 1),
        (@prop_id, 'sprinkler_system', 'no',  1.0000, 'No sprinkler system — baseline',                                   CAST(GETUTCDATE() AS DATE), 2);
END

-- =============================================================================
-- 4. APPETITE RULES (property-specific)
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @prop_id AND rule_name = 'building_value_min')
INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_min, numeric_max, description, sort_order)
VALUES (@prop_id, 'building_value_min', 'building_value', 'between', 'numeric', 100000.00, 50000000.00,
    'Building value must be between $100K and $50M', 1);

IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @prop_id AND rule_name = 'fire_protection_max')
INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_value, description, sort_order)
VALUES (@prop_id, 'fire_protection_max', 'fire_protection_class', '<=', 'numeric', 8.00,
    'Fire protection class must be 8 or better (lower is better)', 2);

IF NOT EXISTS (SELECT 1 FROM product_appetite_rules WHERE product_id = @prop_id AND rule_name = 'prior_losses_max')
INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type, numeric_value, description, sort_order)
VALUES (@prop_id, 'prior_losses_max', 'prior_property_losses', '<=', 'numeric', 500000.00,
    'No prior property losses exceeding $500K in 3 years', 3);

-- =============================================================================
-- 5. AUTHORITY LIMITS
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM product_authority_limits WHERE product_id = @prop_id)
INSERT INTO product_authority_limits (product_id, auto_bind_premium_max, requires_senior_review_above, requires_cuo_review_above)
VALUES (@prop_id, 15000.00, 50000.00, 200000.00);

-- =============================================================================
-- 6. TERRITORIES
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM product_territories WHERE product_id = @prop_id AND territory_code = 'US')
INSERT INTO product_territories (product_id, territory_code, approval_status, effective_date)
VALUES (@prop_id, 'US', 'approved', CAST(GETUTCDATE() AS DATE));

-- =============================================================================
-- 7. PRODUCT PRICING
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM product_pricing WHERE product_id = @prop_id)
INSERT INTO product_pricing (product_id, min_premium, max_premium, base_rate_per_1000, currency, effective_date)
VALUES (@prop_id, 2500.00, 1000000.00, 0.5000, 'USD', CAST(GETUTCDATE() AS DATE));

-- =============================================================================
-- 8. WORKFLOW TEMPLATE (property-specific new business workflow)
-- =============================================================================

IF NOT EXISTS (SELECT 1 FROM workflow_templates WHERE product_id = @prop_id AND workflow_type = 'new_business')
BEGIN
    DECLARE @prop_wf_id UNIQUEIDENTIFIER = NEWID();
    INSERT INTO workflow_templates (id, product_id, workflow_type, version, status, description)
    VALUES (@prop_wf_id, @prop_id, 'new_business', 1, 'active', 'Commercial Property new business workflow');

    INSERT INTO workflow_steps (template_id, step_name, step_order, agent_name, is_parallel, depends_on, timeout_seconds, is_optional, skip_condition, prompt_key)
    VALUES
        (@prop_wf_id, 'orchestration',  1, 'openinsure-orchestrator', 0, NULL,             60, 0, NULL, 'new_business_orchestration'),
        (@prop_wf_id, 'enrichment',     2, 'openinsure-enrichment',   0, 'orchestration',  60, 1, NULL, 'new_business_enrichment'),
        (@prop_wf_id, 'intake',         3, 'openinsure-submission',   0, 'orchestration',  60, 0, NULL, 'new_business_intake'),
        (@prop_wf_id, 'underwriting',   4, 'openinsure-underwriting', 0, 'intake',         60, 0, NULL, 'new_business_underwriting'),
        (@prop_wf_id, 'compliance',     5, 'openinsure-compliance',   0, 'intake,underwriting', 60, 0, NULL, 'new_business_compliance');
END
GO

-- =============================================================================
-- Record migration
-- =============================================================================
INSERT INTO _migration_history (migration_name) VALUES ('026_property_product');
GO

PRINT 'Migration 026_property_product applied successfully.';
GO
