-- =============================================================================
-- Migration 022: Work Items
-- Structured task tracking with owners, deadlines, and SLA tracking.
-- Provides inbox-style work queues for underwriters, claims adjusters, etc.
-- Idempotent: safe to re-run (IF OBJECT_ID ... IS NULL guards).
-- =============================================================================

IF OBJECT_ID('work_items', 'U') IS NULL
CREATE TABLE work_items (
    id              UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    entity_type     NVARCHAR(50)     NOT NULL,
    entity_id       UNIQUEIDENTIFIER NOT NULL,
    work_type       NVARCHAR(50)     NOT NULL,
    title           NVARCHAR(500)    NOT NULL,
    description     NVARCHAR(MAX),
    assigned_to     NVARCHAR(200),
    assigned_role   NVARCHAR(50),
    priority        NVARCHAR(20)     DEFAULT 'medium'
        CHECK (priority IN ('low','medium','high','urgent')),
    status          NVARCHAR(20)     DEFAULT 'open'
        CHECK (status IN ('open','in_progress','completed','cancelled','escalated')),
    due_date        DATETIME2,
    sla_hours       INT,
    completed_at    DATETIME2,
    completed_by    NVARCHAR(200),
    created_at      DATETIME2        DEFAULT GETUTCDATE()
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_work_items_assignee' AND object_id = OBJECT_ID('work_items')
)
CREATE INDEX IX_work_items_assignee ON work_items(assigned_to, status);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_work_items_due' AND object_id = OBJECT_ID('work_items')
)
CREATE INDEX IX_work_items_due ON work_items(due_date)
    WHERE status IN ('open','in_progress');
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_work_items_entity' AND object_id = OBJECT_ID('work_items')
)
CREATE INDEX IX_work_items_entity ON work_items(entity_type, entity_id);
GO
