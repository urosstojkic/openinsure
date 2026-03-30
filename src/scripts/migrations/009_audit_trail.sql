-- Migration 009: Data-level audit trail — change_log table
-- Idempotent: safe to run multiple times

IF OBJECT_ID('change_log', 'U') IS NULL
BEGIN
    CREATE TABLE change_log (
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        entity_type NVARCHAR(50) NOT NULL,
        entity_id UNIQUEIDENTIFIER NOT NULL,
        action NVARCHAR(20) NOT NULL CHECK (action IN ('create','update','delete','restore','anonymize')),
        changed_by NVARCHAR(200) NOT NULL,
        changed_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        changes NVARCHAR(MAX),
        reason NVARCHAR(500),
        ip_address NVARCHAR(45)
    );

    CREATE INDEX IX_change_log_entity ON change_log(entity_type, entity_id);
    CREATE INDEX IX_change_log_time ON change_log(changed_at);
END
