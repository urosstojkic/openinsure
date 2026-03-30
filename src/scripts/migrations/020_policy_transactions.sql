-- =============================================================================
-- Migration 020: Policy Transactions
-- Transaction-based policy history enabling time-travel queries.
-- Every mutation to a policy creates a transaction record.
-- Idempotent: safe to re-run (IF OBJECT_ID ... IS NULL guards).
-- =============================================================================

IF OBJECT_ID('policy_transactions', 'U') IS NULL
CREATE TABLE policy_transactions (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    policy_id           UNIQUEIDENTIFIER NOT NULL REFERENCES policies(id),
    transaction_type    NVARCHAR(30)     NOT NULL
        CHECK (transaction_type IN (
            'new_business','endorsement','renewal',
            'cancellation','reinstatement','audit'
        )),
    effective_date      DATE             NOT NULL,
    expiration_date     DATE,
    premium_change      DECIMAL(18,2)    DEFAULT 0,
    description         NVARCHAR(MAX),
    coverages_snapshot  NVARCHAR(MAX),
    terms_snapshot      NVARCHAR(MAX),
    created_by          NVARCHAR(200),
    created_at          DATETIME2        DEFAULT GETUTCDATE(),
    version             INT              NOT NULL DEFAULT 1
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_policy_txn' AND object_id = OBJECT_ID('policy_transactions')
)
CREATE INDEX IX_policy_txn ON policy_transactions(policy_id, effective_date);
GO
