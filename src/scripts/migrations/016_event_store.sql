-- =============================================================================
-- Migration 016: Event Store
-- Persists domain events for replay, ML pipelines, and regulatory auditing.
-- Idempotent: safe to re-run (IF OBJECT_ID ... IS NULL guards).
-- =============================================================================

IF OBJECT_ID('domain_events', 'U') IS NULL
CREATE TABLE domain_events (
    id              BIGINT IDENTITY PRIMARY KEY,
    event_id        UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID(),
    event_type      NVARCHAR(100)    NOT NULL,
    aggregate_type  NVARCHAR(50)     NOT NULL,
    aggregate_id    UNIQUEIDENTIFIER NOT NULL,
    version         INT              NOT NULL DEFAULT 1,
    payload         NVARCHAR(MAX)    NOT NULL,
    metadata        NVARCHAR(MAX),
    actor           NVARCHAR(200),
    occurred_at     DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT UQ_event UNIQUE (aggregate_id, version)
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_events_aggregate' AND object_id = OBJECT_ID('domain_events'))
    CREATE INDEX IX_events_aggregate ON domain_events(aggregate_type, aggregate_id);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_events_type' AND object_id = OBJECT_ID('domain_events'))
    CREATE INDEX IX_events_type ON domain_events(event_type);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_events_time' AND object_id = OBJECT_ID('domain_events'))
    CREATE INDEX IX_events_time ON domain_events(occurred_at);
GO
