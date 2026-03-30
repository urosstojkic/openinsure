-- ============================================================================
-- OpenInsure Initial Schema Migration
-- Migration: 001_initial_schema.sql
-- Target: Azure SQL Database (openinsure-db)
--
-- DOWN MIGRATION (manual rollback):
--   DROP TABLE IF EXISTS billing_transactions;
--   DROP TABLE IF EXISTS invoices;
--   DROP TABLE IF EXISTS billing_accounts;
--   DROP TABLE IF EXISTS payments;
--   DROP TABLE IF EXISTS reserves;
--   DROP TABLE IF EXISTS claims;
--   DROP TABLE IF EXISTS endorsements;
--   DROP TABLE IF EXISTS coverages;
--   DROP TABLE IF EXISTS policies;
--   DROP TABLE IF EXISTS products;
--   DROP TABLE IF EXISTS submissions;
--   DROP TABLE IF EXISTS addresses;
--   DROP TABLE IF EXISTS contacts;
--   DROP TABLE IF EXISTS parties;
--   DELETE FROM _migration_history WHERE migration_name = '001_initial_schema.sql';
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- PARTIES
-- ============================================================================

CREATE TABLE parties (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    name                NVARCHAR(500)    NOT NULL,
    party_type          NVARCHAR(20)     NOT NULL CHECK (party_type IN ('individual', 'organization')),
    tax_id              NVARCHAR(50),
    registration_number NVARCHAR(100),
    created_at          DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at          DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE party_roles (
    party_id UNIQUEIDENTIFIER NOT NULL REFERENCES parties(id),
    role     NVARCHAR(20)     NOT NULL CHECK (role IN ('insured', 'broker', 'agent', 'claimant', 'vendor', 'adjuster')),
    PRIMARY KEY (party_id, role)
);

CREATE TABLE party_addresses (
    id           UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    party_id     UNIQUEIDENTIFIER NOT NULL REFERENCES parties(id),
    address_type NVARCHAR(20)     NOT NULL,
    street       NVARCHAR(500),
    city         NVARCHAR(200),
    state        NVARCHAR(100),
    zip_code     NVARCHAR(20),
    country      NVARCHAR(3)      NOT NULL DEFAULT 'US'
);

CREATE TABLE party_contacts (
    id           UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    party_id     UNIQUEIDENTIFIER NOT NULL REFERENCES parties(id),
    contact_type NVARCHAR(20)     NOT NULL,
    name         NVARCHAR(200),
    email        NVARCHAR(300),
    phone        NVARCHAR(50)
);

-- ============================================================================
-- PRODUCTS
-- ============================================================================

CREATE TABLE products (
    id               UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_code     NVARCHAR(50)     NOT NULL UNIQUE,
    product_name     NVARCHAR(200)    NOT NULL,
    description      NVARCHAR(MAX),
    line_of_business NVARCHAR(50)     NOT NULL,
    status           NVARCHAR(20)     NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'filed', 'suspended', 'retired')),
    version          INT              NOT NULL DEFAULT 1,
    min_premium      DECIMAL(18,2),
    max_premium      DECIMAL(18,2),
    effective_date   DATE             NOT NULL,
    expiration_date  DATE,
    config_json      NVARCHAR(MAX),
    created_at       DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at       DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

-- ============================================================================
-- SUBMISSIONS
-- ============================================================================

CREATE TABLE submissions (
    id                       UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    submission_number        NVARCHAR(50)     NOT NULL UNIQUE,
    status                   NVARCHAR(20)     NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'triaging', 'underwriting', 'quoted', 'bound', 'declined', 'expired')),
    channel                  NVARCHAR(20)     NOT NULL CHECK (channel IN ('email', 'api', 'portal', 'broker_platform')),
    line_of_business         NVARCHAR(50)     NOT NULL,
    applicant_id             UNIQUEIDENTIFIER REFERENCES parties(id),
    broker_id                UNIQUEIDENTIFIER REFERENCES parties(id),
    product_id               UNIQUEIDENTIFIER REFERENCES products(id),
    requested_effective_date DATE,
    requested_expiration_date DATE,
    extracted_data           NVARCHAR(MAX),
    cyber_risk_data          NVARCHAR(MAX),
    triage_result            NVARCHAR(MAX),
    quoted_premium           DECIMAL(18,2),
    received_at              DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    triaged_at               DATETIME2,
    quoted_at                DATETIME2,
    bound_at                 DATETIME2,
    declined_at              DATETIME2,
    created_at               DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at               DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE submission_documents (
    id                        UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    submission_id             UNIQUEIDENTIFIER NOT NULL REFERENCES submissions(id),
    document_type             NVARCHAR(50)     NOT NULL,
    filename                  NVARCHAR(500)    NOT NULL,
    storage_url               NVARCHAR(2000),
    extracted_data            NVARCHAR(MAX),
    classification_confidence FLOAT,
    uploaded_at               DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

-- ============================================================================
-- POLICIES
-- ============================================================================

CREATE TABLE policies (
    id               UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    policy_number    NVARCHAR(50)     NOT NULL UNIQUE,
    status           NVARCHAR(20)     NOT NULL DEFAULT 'pending' CHECK (status IN ('active', 'expired', 'cancelled', 'pending', 'suspended')),
    product_id       UNIQUEIDENTIFIER NOT NULL REFERENCES products(id),
    submission_id    UNIQUEIDENTIFIER REFERENCES submissions(id),
    insured_id       UNIQUEIDENTIFIER NOT NULL REFERENCES parties(id),
    broker_id        UNIQUEIDENTIFIER REFERENCES parties(id),
    effective_date   DATE             NOT NULL,
    expiration_date  DATE             NOT NULL,
    total_premium    DECIMAL(18,2)    NOT NULL,
    written_premium  DECIMAL(18,2)    NOT NULL DEFAULT 0,
    earned_premium   DECIMAL(18,2)    NOT NULL DEFAULT 0,
    unearned_premium DECIMAL(18,2)    NOT NULL DEFAULT 0,
    bound_at         DATETIME2,
    cancelled_at     DATETIME2,
    cancel_reason    NVARCHAR(500),
    created_at       DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at       DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE policy_coverages (
    id             UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    policy_id      UNIQUEIDENTIFIER NOT NULL REFERENCES policies(id),
    coverage_code  NVARCHAR(50)     NOT NULL,
    coverage_name  NVARCHAR(200)    NOT NULL,
    limit_amount   DECIMAL(18,2)    NOT NULL,
    deductible     DECIMAL(18,2)    NOT NULL,
    premium        DECIMAL(18,2)    NOT NULL,
    sublimits      NVARCHAR(MAX)
);

CREATE TABLE policy_endorsements (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    policy_id           UNIQUEIDENTIFIER NOT NULL REFERENCES policies(id),
    endorsement_number  NVARCHAR(50)     NOT NULL,
    effective_date      DATE             NOT NULL,
    description         NVARCHAR(MAX),
    premium_change      DECIMAL(18,2)    NOT NULL DEFAULT 0,
    coverages_modified  NVARCHAR(MAX),
    created_at          DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

-- ============================================================================
-- CLAIMS
-- ============================================================================

CREATE TABLE claims (
    id                UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    claim_number      NVARCHAR(50)     NOT NULL UNIQUE,
    status            NVARCHAR(20)     NOT NULL DEFAULT 'fnol' CHECK (status IN ('fnol', 'investigating', 'reserved', 'settling', 'closed', 'reopened', 'denied')),
    policy_id         UNIQUEIDENTIFIER NOT NULL REFERENCES policies(id),
    loss_date         DATE             NOT NULL,
    report_date       DATE             NOT NULL DEFAULT GETUTCDATE(),
    loss_type         NVARCHAR(100),
    cause_of_loss     NVARCHAR(50)     CHECK (cause_of_loss IN ('data_breach', 'ransomware', 'social_engineering', 'system_failure', 'unauthorized_access', 'denial_of_service', 'other')),
    description       NVARCHAR(MAX),
    severity          NVARCHAR(20)     DEFAULT 'moderate' CHECK (severity IN ('simple', 'moderate', 'complex', 'catastrophe')),
    assigned_adjuster UNIQUEIDENTIFIER REFERENCES parties(id),
    fraud_score       FLOAT,
    closed_at         DATETIME2,
    close_reason      NVARCHAR(500),
    created_at        DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at        DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE claim_reserves (
    id           UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    claim_id     UNIQUEIDENTIFIER NOT NULL REFERENCES claims(id),
    reserve_type NVARCHAR(20)     NOT NULL CHECK (reserve_type IN ('indemnity', 'expense')),
    amount       DECIMAL(18,2)    NOT NULL,
    set_date     DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    set_by       NVARCHAR(100)    NOT NULL,
    confidence   FLOAT
);

CREATE TABLE claim_payments (
    id           UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    claim_id     UNIQUEIDENTIFIER NOT NULL REFERENCES claims(id),
    amount       DECIMAL(18,2)    NOT NULL,
    payee_id     UNIQUEIDENTIFIER REFERENCES parties(id),
    payment_date DATETIME2        NOT NULL,
    payment_type NVARCHAR(30)     NOT NULL CHECK (payment_type IN ('indemnity', 'expense', 'deductible_recovery'))
);

-- ============================================================================
-- BILLING
-- ============================================================================

CREATE TABLE billing_accounts (
    id            UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    policy_id     UNIQUEIDENTIFIER NOT NULL REFERENCES policies(id),
    billing_plan  NVARCHAR(20)     NOT NULL CHECK (billing_plan IN ('full_pay', 'quarterly', 'monthly', 'agency_bill', 'direct_bill')),
    total_premium DECIMAL(18,2)    NOT NULL,
    balance_due   DECIMAL(18,2)    NOT NULL DEFAULT 0,
    created_at    DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    updated_at    DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE invoices (
    id                 UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    invoice_number     NVARCHAR(50)     NOT NULL UNIQUE,
    billing_account_id UNIQUEIDENTIFIER NOT NULL REFERENCES billing_accounts(id),
    status             NVARCHAR(20)     NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'issued', 'paid', 'overdue', 'cancelled', 'void')),
    issue_date         DATE             NOT NULL,
    due_date           DATE             NOT NULL,
    amount             DECIMAL(18,2)    NOT NULL,
    paid_amount        DECIMAL(18,2)    NOT NULL DEFAULT 0,
    line_items         NVARCHAR(MAX),
    created_at         DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

-- ============================================================================
-- AI / AUDIT
-- ============================================================================

CREATE TABLE decision_records (
    id                     UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    agent_id               NVARCHAR(100)    NOT NULL,
    agent_version          NVARCHAR(20),
    model_used             NVARCHAR(50),
    model_version          NVARCHAR(50),
    decision_type          NVARCHAR(100)    NOT NULL,
    input_summary          NVARCHAR(MAX),
    data_sources_used      NVARCHAR(MAX),
    knowledge_graph_queries NVARCHAR(MAX),
    output_data            NVARCHAR(MAX),
    reasoning              NVARCHAR(MAX),
    confidence             FLOAT            NOT NULL,
    fairness_metrics       NVARCHAR(MAX),
    human_oversight        NVARCHAR(MAX),
    execution_time_ms      INT,
    error_message          NVARCHAR(MAX),
    created_at             DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

CREATE TABLE audit_events (
    id             UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    event_type     NVARCHAR(100)    NOT NULL,
    actor_type     NVARCHAR(20)     NOT NULL CHECK (actor_type IN ('agent', 'human', 'system')),
    actor_id       NVARCHAR(100)    NOT NULL,
    resource_type  NVARCHAR(50)     NOT NULL,
    resource_id    NVARCHAR(100)    NOT NULL,
    action         NVARCHAR(100)    NOT NULL,
    details        NVARCHAR(MAX),
    correlation_id UNIQUEIDENTIFIER,
    created_at     DATETIME2        NOT NULL DEFAULT GETUTCDATE()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX IX_submissions_status            ON submissions(status);
CREATE INDEX IX_submissions_line_of_business  ON submissions(line_of_business);

CREATE INDEX IX_policies_status               ON policies(status);
CREATE INDEX IX_policies_insured_id           ON policies(insured_id);

CREATE INDEX IX_claims_status                 ON claims(status);
CREATE INDEX IX_claims_policy_id              ON claims(policy_id);

CREATE INDEX IX_decision_records_agent_id     ON decision_records(agent_id);
CREATE INDEX IX_decision_records_type         ON decision_records(decision_type);
CREATE INDEX IX_decision_records_created_at   ON decision_records(created_at);

CREATE INDEX IX_audit_events_resource         ON audit_events(resource_type, resource_id);
CREATE INDEX IX_audit_events_created_at       ON audit_events(created_at);

COMMIT TRANSACTION;

PRINT 'Migration 001_initial_schema completed successfully.';
