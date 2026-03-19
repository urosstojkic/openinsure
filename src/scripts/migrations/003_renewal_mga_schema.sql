-- ============================================================================
-- OpenInsure Renewal & MGA Schema Migration
-- Migration: 003_renewal_mga_schema.sql
-- Target: Azure SQL Database (openinsure-db)
-- Purpose: Add SQL tables for renewal tracking and MGA oversight
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- RENEWALS
-- ============================================================================

CREATE TABLE renewal_records (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    original_policy_id  UNIQUEIDENTIFIER NOT NULL REFERENCES policies(id),
    renewal_policy_id   UNIQUEIDENTIFIER REFERENCES policies(id),
    status              NVARCHAR(30)     NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'terms_generated', 'offered', 'accepted', 'declined', 'non_renewed', 'lapsed')),
    expiring_premium    DECIMAL(18,2),
    renewal_premium     DECIMAL(18,2),
    rate_change_pct     DECIMAL(6,2),
    recommendation      NVARCHAR(30)     DEFAULT 'review_required',
    conditions          NVARCHAR(MAX),
    generated_by        NVARCHAR(50)     DEFAULT 'system',
    created_at          DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at          DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

-- ============================================================================
-- MGA OVERSIGHT
-- ============================================================================

CREATE TABLE mga_authorities (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    mga_id              NVARCHAR(50)     NOT NULL UNIQUE,
    mga_name            NVARCHAR(200)    NOT NULL,
    status              NVARCHAR(20)     NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'suspended', 'expired', 'terminated')),
    effective_date      DATE             NOT NULL,
    expiration_date     DATE             NOT NULL,
    lines_of_business   NVARCHAR(MAX),
    premium_authority   DECIMAL(18,2)    NOT NULL DEFAULT 0,
    premium_written     DECIMAL(18,2)    NOT NULL DEFAULT 0,
    claims_authority    DECIMAL(18,2)    NOT NULL DEFAULT 0,
    loss_ratio          DECIMAL(6,4)     DEFAULT 0,
    compliance_score    INT              DEFAULT 100,
    last_audit_date     DATE,
    created_at          DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at          DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE mga_bordereaux (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    mga_id              NVARCHAR(50)     NOT NULL,
    period              NVARCHAR(20)     NOT NULL,
    premium_reported    DECIMAL(18,2)    NOT NULL DEFAULT 0,
    claims_reported     DECIMAL(18,2)    NOT NULL DEFAULT 0,
    loss_ratio          DECIMAL(6,4)     DEFAULT 0,
    policy_count        INT              NOT NULL DEFAULT 0,
    claim_count         INT              NOT NULL DEFAULT 0,
    status              NVARCHAR(20)     NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'validated', 'exceptions', 'rejected')),
    exceptions          NVARCHAR(MAX),
    submitted_at        DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    validated_at        DATETIME2
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IX_renewal_records_policy    ON renewal_records(original_policy_id);
CREATE INDEX IX_renewal_records_status    ON renewal_records(status);
CREATE INDEX IX_mga_authorities_status    ON mga_authorities(status);
CREATE INDEX IX_mga_bordereaux_mga        ON mga_bordereaux(mga_id);

COMMIT TRANSACTION;

PRINT 'Migration 003_renewal_mga_schema completed successfully.';
