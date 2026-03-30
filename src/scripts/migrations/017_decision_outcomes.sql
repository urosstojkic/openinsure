-- =============================================================================
-- Migration 017: Decision Outcomes
-- Tracks whether AI decisions (triage, underwriting, claims) were accurate
-- by recording real-world outcomes and computing accuracy scores.
-- Idempotent: safe to re-run (IF OBJECT_ID ... IS NULL guards).
-- =============================================================================

IF OBJECT_ID('decision_outcomes', 'U') IS NULL
CREATE TABLE decision_outcomes (
    id              UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    decision_id     UNIQUEIDENTIFIER NOT NULL,
    outcome_type    NVARCHAR(50)     NOT NULL,
    outcome_value   DECIMAL(18,4),
    accuracy_score  FLOAT,
    measured_at     DATETIME2        DEFAULT GETUTCDATE(),
    notes           NVARCHAR(MAX),
    CONSTRAINT FK_outcomes_decision FOREIGN KEY (decision_id)
        REFERENCES decision_records(id)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_outcomes_decision' AND object_id = OBJECT_ID('decision_outcomes'))
    CREATE INDEX IX_outcomes_decision ON decision_outcomes(decision_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_outcomes_type' AND object_id = OBJECT_ID('decision_outcomes'))
    CREATE INDEX IX_outcomes_type ON decision_outcomes(outcome_type);
GO
