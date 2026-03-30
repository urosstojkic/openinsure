-- =============================================================================
-- Migration 021: Polymorphic Documents Table
-- Unified document tracking for any entity (submission, policy, claim, etc.).
-- Replaces per-entity document tables with a single polymorphic table.
-- Idempotent: safe to re-run (IF OBJECT_ID ... IS NULL guards).
-- =============================================================================

IF OBJECT_ID('documents', 'U') IS NULL
CREATE TABLE documents (
    id                          UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    entity_type                 NVARCHAR(50)     NOT NULL,
    entity_id                   UNIQUEIDENTIFIER NOT NULL,
    document_type               NVARCHAR(50)     NOT NULL,
    filename                    NVARCHAR(500)    NOT NULL,
    storage_url                 NVARCHAR(2000),
    content_type                NVARCHAR(100),
    file_size_bytes             BIGINT,
    extracted_data              NVARCHAR(MAX),
    classification_confidence   FLOAT,
    uploaded_by                 NVARCHAR(200),
    uploaded_at                 DATETIME2        DEFAULT GETUTCDATE(),
    deleted_at                  DATETIME2
);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'IX_docs_entity' AND object_id = OBJECT_ID('documents')
)
CREATE INDEX IX_docs_entity ON documents(entity_type, entity_id);
GO

-- Migrate existing submission_documents data into the unified table
IF OBJECT_ID('submission_documents', 'U') IS NOT NULL
BEGIN
    INSERT INTO documents (
        id, entity_type, entity_id, document_type,
        filename, storage_url, extracted_data,
        classification_confidence, uploaded_at
    )
    SELECT
        sd.id,
        'submission',
        sd.submission_id,
        sd.document_type,
        sd.filename,
        sd.storage_url,
        sd.extracted_data,
        sd.classification_confidence,
        sd.uploaded_at
    FROM submission_documents sd
    WHERE NOT EXISTS (
        SELECT 1 FROM documents d WHERE d.id = sd.id
    );
END
GO
