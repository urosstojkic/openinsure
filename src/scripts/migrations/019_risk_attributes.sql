-- Migration 019: Typed Risk Attributes
-- Decomposes JSON risk data into queryable, typed rows.
-- Idempotent: safe to re-run (IF OBJECT_ID ... IS NULL guards).

IF OBJECT_ID('risk_attributes', 'U') IS NULL
CREATE TABLE risk_attributes (
    id                UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    submission_id     UNIQUEIDENTIFIER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    attribute_group   NVARCHAR(50)     NOT NULL,
    attribute_name    NVARCHAR(100)    NOT NULL,
    attribute_type    NVARCHAR(20)     NOT NULL
        CHECK (attribute_type IN ('string', 'numeric', 'boolean', 'date', 'json')),
    string_value      NVARCHAR(MAX),
    numeric_value     DECIMAL(18,4),
    boolean_value     BIT,
    date_value        DATE,
    display_order     INT              DEFAULT 0,
    created_at        DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT UQ_risk_attr UNIQUE (submission_id, attribute_group, attribute_name)
);

GO

-- Indexes for cross-submission analytics queries
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_risk_attr_group')
    CREATE INDEX IX_risk_attr_group
    ON risk_attributes (attribute_group, attribute_name);

GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_risk_attr_numeric')
    CREATE INDEX IX_risk_attr_numeric
    ON risk_attributes (attribute_name, numeric_value)
    WHERE numeric_value IS NOT NULL;

GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_risk_attr_submission')
    CREATE INDEX IX_risk_attr_submission
    ON risk_attributes (submission_id);
