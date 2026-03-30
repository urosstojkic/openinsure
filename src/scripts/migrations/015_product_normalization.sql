-- =============================================================================
-- Migration 015: Product Normalization
-- Normalizes product JSON blobs into relational tables for queryability,
-- indexing, and referential integrity.
-- Idempotent: safe to re-run (IF OBJECT_ID ... IS NULL guards).
-- =============================================================================

-- 1. PRODUCT_COVERAGES
IF OBJECT_ID('product_coverages', 'U') IS NULL
CREATE TABLE product_coverages (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id          UNIQUEIDENTIFIER NOT NULL,
    coverage_code       NVARCHAR(50)     NOT NULL,
    coverage_name       NVARCHAR(200)    NOT NULL,
    description         NVARCHAR(MAX),
    default_limit       DECIMAL(15,2),
    min_limit           DECIMAL(15,2),
    max_limit           DECIMAL(15,2),
    default_deductible  DECIMAL(15,2),
    is_optional         BIT              DEFAULT 0,
    sort_order          INT              DEFAULT 0,
    created_at          DATETIME2        DEFAULT GETUTCDATE(),
    updated_at          DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT FK_prod_cov_product FOREIGN KEY (product_id)
        REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT UQ_prod_cov UNIQUE (product_id, coverage_code)
);
GO

-- 2. COVERAGE_DEDUCTIBLES
IF OBJECT_ID('coverage_deductibles', 'U') IS NULL
CREATE TABLE coverage_deductibles (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    coverage_id         UNIQUEIDENTIFIER NOT NULL,
    deductible_amount   DECIMAL(15,2)    NOT NULL,
    available           BIT              DEFAULT 1,
    sort_order          INT              DEFAULT 0,
    CONSTRAINT FK_cov_ded FOREIGN KEY (coverage_id)
        REFERENCES product_coverages(id) ON DELETE CASCADE,
    CONSTRAINT UQ_cov_ded UNIQUE (coverage_id, deductible_amount)
);
GO

-- 3. PRODUCT_RATING_FACTORS
IF OBJECT_ID('product_rating_factors', 'U') IS NULL
CREATE TABLE product_rating_factors (
    id           UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id   UNIQUEIDENTIFIER NOT NULL,
    factor_name  NVARCHAR(50)     NOT NULL,
    factor_type  NVARCHAR(20)     NOT NULL,
    weight       DECIMAL(5,4),
    description  NVARCHAR(MAX),
    sort_order   INT              DEFAULT 0,
    created_at   DATETIME2        DEFAULT GETUTCDATE(),
    updated_at   DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT FK_rf_product FOREIGN KEY (product_id)
        REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT UQ_rf UNIQUE (product_id, factor_name)
);
GO

-- 4. RATING_FACTOR_TABLES (lookup values for each factor)
IF OBJECT_ID('rating_factor_tables', 'U') IS NULL
CREATE TABLE rating_factor_tables (
    id              UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id      UNIQUEIDENTIFIER NOT NULL,
    factor_category NVARCHAR(50)     NOT NULL,
    factor_key      NVARCHAR(50)     NOT NULL,
    multiplier      DECIMAL(10,4)    NOT NULL DEFAULT 1.0,
    description     NVARCHAR(MAX),
    effective_date  DATE,
    expiration_date DATE,
    sort_order      INT              DEFAULT 0,
    created_at      DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT FK_rft_product FOREIGN KEY (product_id)
        REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT UQ_rft UNIQUE (product_id, factor_category, factor_key)
);
GO

-- 5. PRODUCT_APPETITE_RULES
IF OBJECT_ID('product_appetite_rules', 'U') IS NULL
CREATE TABLE product_appetite_rules (
    id            UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id    UNIQUEIDENTIFIER NOT NULL,
    rule_name     NVARCHAR(100),
    field_name    NVARCHAR(50)     NOT NULL,
    operator      NVARCHAR(20)     NOT NULL,
    value_type    NVARCHAR(20)     DEFAULT 'numeric',
    numeric_value DECIMAL(15,2),
    numeric_min   DECIMAL(15,2),
    numeric_max   DECIMAL(15,2),
    string_value  NVARCHAR(MAX),
    description   NVARCHAR(MAX),
    sort_order    INT              DEFAULT 0,
    created_at    DATETIME2        DEFAULT GETUTCDATE(),
    updated_at    DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT FK_ar_product FOREIGN KEY (product_id)
        REFERENCES products(id) ON DELETE CASCADE
);
GO

-- 6. PRODUCT_AUTHORITY_LIMITS
IF OBJECT_ID('product_authority_limits', 'U') IS NULL
CREATE TABLE product_authority_limits (
    id                            UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id                    UNIQUEIDENTIFIER NOT NULL UNIQUE,
    auto_bind_premium_max         DECIMAL(15,2),
    auto_bind_limit_max           DECIMAL(15,2),
    requires_senior_review_above  DECIMAL(15,2),
    requires_cuo_review_above     DECIMAL(15,2),
    updated_at                    DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT FK_al_product FOREIGN KEY (product_id)
        REFERENCES products(id) ON DELETE CASCADE
);
GO

-- 7. PRODUCT_TERRITORIES
IF OBJECT_ID('product_territories', 'U') IS NULL
CREATE TABLE product_territories (
    id               UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id       UNIQUEIDENTIFIER NOT NULL,
    territory_code   NVARCHAR(10)     NOT NULL,
    approval_status  NVARCHAR(20)     DEFAULT 'approved',
    filing_reference NVARCHAR(200),
    effective_date   DATE,
    expiration_date  DATE,
    CONSTRAINT FK_terr_product FOREIGN KEY (product_id)
        REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT UQ_terr UNIQUE (product_id, territory_code)
);
GO

-- 8. PRODUCT_FORMS
IF OBJECT_ID('product_forms', 'U') IS NULL
CREATE TABLE product_forms (
    id           UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id   UNIQUEIDENTIFIER NOT NULL,
    form_code    NVARCHAR(50)     NOT NULL,
    form_name    NVARCHAR(200),
    form_type    NVARCHAR(20),
    form_version NVARCHAR(20),
    required     BIT              DEFAULT 1,
    url          NVARCHAR(500),
    CONSTRAINT FK_forms_product FOREIGN KEY (product_id)
        REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT UQ_forms UNIQUE (product_id, form_code)
);
GO

-- 9. PRODUCT_PRICING
IF OBJECT_ID('product_pricing', 'U') IS NULL
CREATE TABLE product_pricing (
    id                UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id        UNIQUEIDENTIFIER NOT NULL UNIQUE,
    min_premium       DECIMAL(15,2),
    max_premium       DECIMAL(15,2),
    base_rate_per_1000 DECIMAL(10,4),
    currency          NVARCHAR(3)      DEFAULT 'USD',
    effective_date    DATE,
    expiration_date   DATE,
    updated_at        DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT FK_pricing_product FOREIGN KEY (product_id)
        REFERENCES products(id) ON DELETE CASCADE
);
GO

-- =============================================================================
-- DATA MIGRATION: Populate relational tables from existing JSON blobs
-- Each INSERT uses NOT EXISTS to be idempotent.
-- =============================================================================

-- Populate product_coverages from JSON
INSERT INTO product_coverages (product_id, coverage_code, coverage_name, default_limit, default_deductible, sort_order)
SELECT p.id,
    JSON_VALUE(c.value, '$.code') AS coverage_code,
    COALESCE(JSON_VALUE(c.value, '$.name'), JSON_VALUE(c.value, '$.coverage_name')) AS coverage_name,
    CAST(COALESCE(JSON_VALUE(c.value, '$.default_limit'), '0') AS DECIMAL(15,2)),
    CAST(COALESCE(JSON_VALUE(c.value, '$.default_deductible'), '0') AS DECIMAL(15,2)),
    c.[key] AS sort_order
FROM products p
CROSS APPLY OPENJSON(p.coverages) c
WHERE p.coverages IS NOT NULL AND ISJSON(p.coverages) = 1
  AND JSON_VALUE(c.value, '$.code') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM product_coverages pc
      WHERE pc.product_id = p.id
        AND pc.coverage_code = JSON_VALUE(c.value, '$.code')
  );
GO

-- Populate product_rating_factors from JSON
INSERT INTO product_rating_factors (product_id, factor_name, factor_type, weight, description, sort_order)
SELECT p.id,
    JSON_VALUE(rf.value, '$.factor_name') AS factor_name,
    COALESCE(JSON_VALUE(rf.value, '$.factor_type'), 'numeric') AS factor_type,
    CAST(COALESCE(JSON_VALUE(rf.value, '$.weight'), '1.0') AS DECIMAL(5,4)),
    JSON_VALUE(rf.value, '$.description'),
    rf.[key] AS sort_order
FROM products p
CROSS APPLY OPENJSON(p.rating_factors) rf
WHERE p.rating_factors IS NOT NULL AND ISJSON(p.rating_factors) = 1
  AND JSON_VALUE(rf.value, '$.factor_name') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM product_rating_factors prf
      WHERE prf.product_id = p.id
        AND prf.factor_name = JSON_VALUE(rf.value, '$.factor_name')
  );
GO

-- Populate product_appetite_rules from JSON
INSERT INTO product_appetite_rules (product_id, rule_name, field_name, operator, value_type,
                                     numeric_value, numeric_min, numeric_max, string_value, description, sort_order)
SELECT p.id,
    JSON_VALUE(ar.value, '$.rule_name') AS rule_name,
    JSON_VALUE(ar.value, '$.field_name') AS field_name,
    COALESCE(JSON_VALUE(ar.value, '$.operator'), '=') AS operator,
    COALESCE(JSON_VALUE(ar.value, '$.value_type'), 'numeric') AS value_type,
    CAST(JSON_VALUE(ar.value, '$.numeric_value') AS DECIMAL(15,2)),
    CAST(JSON_VALUE(ar.value, '$.numeric_min') AS DECIMAL(15,2)),
    CAST(JSON_VALUE(ar.value, '$.numeric_max') AS DECIMAL(15,2)),
    JSON_VALUE(ar.value, '$.string_value'),
    JSON_VALUE(ar.value, '$.description'),
    ar.[key] AS sort_order
FROM products p
CROSS APPLY OPENJSON(p.appetite_rules) ar
WHERE p.appetite_rules IS NOT NULL AND ISJSON(p.appetite_rules) = 1
  AND JSON_VALUE(ar.value, '$.field_name') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM product_appetite_rules par
      WHERE par.product_id = p.id
        AND par.field_name = JSON_VALUE(ar.value, '$.field_name')
        AND COALESCE(par.rule_name, '') = COALESCE(JSON_VALUE(ar.value, '$.rule_name'), '')
  );
GO

-- Populate product_authority_limits from JSON
INSERT INTO product_authority_limits (product_id, auto_bind_premium_max, auto_bind_limit_max,
                                      requires_senior_review_above, requires_cuo_review_above)
SELECT p.id,
    CAST(JSON_VALUE(p.authority_limits, '$.auto_bind_premium_max') AS DECIMAL(15,2)),
    CAST(JSON_VALUE(p.authority_limits, '$.auto_bind_limit_max') AS DECIMAL(15,2)),
    CAST(JSON_VALUE(p.authority_limits, '$.requires_senior_review_above') AS DECIMAL(15,2)),
    CAST(JSON_VALUE(p.authority_limits, '$.requires_cuo_review_above') AS DECIMAL(15,2))
FROM products p
WHERE p.authority_limits IS NOT NULL AND ISJSON(p.authority_limits) = 1
  AND NOT EXISTS (
      SELECT 1 FROM product_authority_limits pal
      WHERE pal.product_id = p.id
  );
GO

-- Populate product_territories from JSON
-- Territories is stored as a JSON array of strings, e.g. ["US","CA","UK"]
INSERT INTO product_territories (product_id, territory_code)
SELECT p.id,
    TRIM(REPLACE(t.value, '"', '')) AS territory_code
FROM products p
CROSS APPLY OPENJSON(p.territories) t
WHERE p.territories IS NOT NULL AND ISJSON(p.territories) = 1
  AND TRIM(REPLACE(t.value, '"', '')) <> ''
  AND NOT EXISTS (
      SELECT 1 FROM product_territories pt
      WHERE pt.product_id = p.id
        AND pt.territory_code = TRIM(REPLACE(t.value, '"', ''))
  );
GO

-- Populate product_forms from JSON
INSERT INTO product_forms (product_id, form_code, form_name, form_type, form_version, required, url)
SELECT p.id,
    JSON_VALUE(f.value, '$.form_code') AS form_code,
    JSON_VALUE(f.value, '$.form_name') AS form_name,
    JSON_VALUE(f.value, '$.form_type') AS form_type,
    JSON_VALUE(f.value, '$.form_version') AS form_version,
    COALESCE(CAST(JSON_VALUE(f.value, '$.required') AS BIT), 1),
    JSON_VALUE(f.value, '$.url')
FROM products p
CROSS APPLY OPENJSON(p.forms) f
WHERE p.forms IS NOT NULL AND ISJSON(p.forms) = 1
  AND JSON_VALUE(f.value, '$.form_code') IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM product_forms pf
      WHERE pf.product_id = p.id
        AND pf.form_code = JSON_VALUE(f.value, '$.form_code')
  );
GO

-- Populate product_pricing from metadata JSON
INSERT INTO product_pricing (product_id, min_premium, max_premium, base_rate_per_1000,
                              currency, effective_date, expiration_date)
SELECT p.id,
    COALESCE(
        CAST(JSON_VALUE(p.metadata, '$.min_premium') AS DECIMAL(15,2)),
        p.min_premium
    ),
    COALESCE(
        CAST(JSON_VALUE(p.metadata, '$.max_premium') AS DECIMAL(15,2)),
        p.max_premium
    ),
    CAST(JSON_VALUE(p.metadata, '$.base_rate_per_1000') AS DECIMAL(10,4)),
    COALESCE(JSON_VALUE(p.metadata, '$.currency'), 'USD'),
    p.effective_date,
    p.expiration_date
FROM products p
WHERE NOT EXISTS (
    SELECT 1 FROM product_pricing pp
    WHERE pp.product_id = p.id
);
GO
