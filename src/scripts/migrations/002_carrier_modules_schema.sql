-- ============================================================================
-- OpenInsure Carrier Modules Schema Migration
-- Migration: 002_carrier_modules_schema.sql
-- Target: Azure SQL Database (openinsure-db)
-- Purpose: Add SQL tables for carrier-only modules: reinsurance, actuarial
--
-- DOWN MIGRATION (manual rollback):
--   DROP TABLE IF EXISTS rate_adequacy;
--   DROP TABLE IF EXISTS loss_triangles;
--   DROP TABLE IF EXISTS actuarial_reserves;
--   DROP TABLE IF EXISTS reinsurance_recoveries;
--   DROP TABLE IF EXISTS reinsurance_cessions;
--   DROP TABLE IF EXISTS reinsurance_treaties;
--   DELETE FROM _migration_history WHERE migration_name = '002_carrier_modules_schema.sql';
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- REINSURANCE
-- ============================================================================

CREATE TABLE reinsurance_treaties (
    id                UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    treaty_number     NVARCHAR(50)     NOT NULL UNIQUE,
    treaty_type       NVARCHAR(30)     NOT NULL CHECK (treaty_type IN ('quota_share', 'excess_of_loss', 'surplus', 'facultative')),
    reinsurer_name    NVARCHAR(200)    NOT NULL,
    status            NVARCHAR(20)     NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled', 'pending', 'exhausted')),
    effective_date    DATE             NOT NULL,
    expiration_date   DATE             NOT NULL,
    lines_of_business NVARCHAR(MAX),
    retention         DECIMAL(18,2)    NOT NULL DEFAULT 0,
    treaty_limit      DECIMAL(18,2)    NOT NULL DEFAULT 0,
    rate              DECIMAL(10,6)    NOT NULL DEFAULT 0,
    capacity_total    DECIMAL(18,2)    NOT NULL DEFAULT 0,
    capacity_used     DECIMAL(18,2)    NOT NULL DEFAULT 0,
    reinstatements    INT              NOT NULL DEFAULT 0,
    description       NVARCHAR(MAX),
    created_at        DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at        DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE reinsurance_cessions (
    id             UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    treaty_id      UNIQUEIDENTIFIER NOT NULL REFERENCES reinsurance_treaties(id),
    policy_id      UNIQUEIDENTIFIER NOT NULL REFERENCES policies(id),
    policy_number  NVARCHAR(50)     NOT NULL,
    ceded_premium  DECIMAL(18,2)    NOT NULL,
    ceded_limit    DECIMAL(18,2)    NOT NULL,
    cession_date   DATE             NOT NULL,
    created_at     DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE reinsurance_recoveries (
    id              UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    treaty_id       UNIQUEIDENTIFIER NOT NULL REFERENCES reinsurance_treaties(id),
    claim_id        UNIQUEIDENTIFIER NOT NULL REFERENCES claims(id),
    claim_number    NVARCHAR(50)     NOT NULL,
    recovery_amount DECIMAL(18,2)    NOT NULL,
    recovery_date   DATE             NOT NULL,
    status          NVARCHAR(20)     NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'submitted', 'collected', 'disputed')),
    created_at      DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

-- ============================================================================
-- ACTUARIAL
-- ============================================================================

CREATE TABLE actuarial_reserves (
    id                UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    line_of_business  NVARCHAR(50)     NOT NULL,
    accident_year     INT              NOT NULL,
    reserve_type      NVARCHAR(20)     NOT NULL CHECK (reserve_type IN ('case', 'ibnr', 'bulk')),
    carried_amount    DECIMAL(18,2)    NOT NULL DEFAULT 0,
    indicated_amount  DECIMAL(18,2)    NOT NULL DEFAULT 0,
    selected_amount   DECIMAL(18,2)    NOT NULL DEFAULT 0,
    as_of_date        DATE,
    analyst           NVARCHAR(200),
    approved_by       NVARCHAR(200),
    notes             NVARCHAR(MAX),
    created_at        DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at        DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE loss_triangle_entries (
    id                 UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    line_of_business   NVARCHAR(50)     NOT NULL,
    accident_year      INT              NOT NULL,
    development_month  INT              NOT NULL,
    incurred_amount    DECIMAL(18,2)    NOT NULL DEFAULT 0,
    paid_amount        DECIMAL(18,2)    NOT NULL DEFAULT 0,
    case_reserve       DECIMAL(18,2)    NOT NULL DEFAULT 0,
    claim_count        INT              NOT NULL DEFAULT 0,
    created_at         DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    UNIQUE (line_of_business, accident_year, development_month)
);

CREATE TABLE rate_adequacy (
    id                UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    line_of_business  NVARCHAR(50)     NOT NULL,
    segment           NVARCHAR(100)    NOT NULL,
    current_rate      DECIMAL(10,4)    NOT NULL,
    indicated_rate    DECIMAL(10,4)    NOT NULL,
    adequacy_ratio    DECIMAL(10,4)    NOT NULL,
    as_of_date        DATE,
    created_at        DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    UNIQUE (line_of_business, segment)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IX_treaties_status            ON reinsurance_treaties(status);
CREATE INDEX IX_treaties_reinsurer         ON reinsurance_treaties(reinsurer_name);
CREATE INDEX IX_cessions_treaty_id         ON reinsurance_cessions(treaty_id);
CREATE INDEX IX_cessions_policy_id         ON reinsurance_cessions(policy_id);
CREATE INDEX IX_recoveries_treaty_id       ON reinsurance_recoveries(treaty_id);
CREATE INDEX IX_recoveries_claim_id        ON reinsurance_recoveries(claim_id);
CREATE INDEX IX_actuarial_reserves_lob     ON actuarial_reserves(line_of_business);
CREATE INDEX IX_loss_triangles_lob         ON loss_triangle_entries(line_of_business);

COMMIT TRANSACTION;

PRINT 'Migration 002_carrier_modules_schema completed successfully.';
