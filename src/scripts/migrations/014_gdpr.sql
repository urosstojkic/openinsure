-- Migration 014: GDPR compliance tables
-- Issue #165 — idempotent via IF NOT EXISTS / IF OBJECT_ID checks

-- Consent tracking (Art. 7)
IF OBJECT_ID('consent_records', 'U') IS NULL
BEGIN
    CREATE TABLE consent_records (
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        party_id UNIQUEIDENTIFIER NOT NULL,
        purpose NVARCHAR(100) NOT NULL,
        status NVARCHAR(20) NOT NULL CHECK (status IN ('granted','withdrawn','expired')),
        granted_at DATETIME2,
        withdrawn_at DATETIME2,
        expires_at DATETIME2,
        evidence NVARCHAR(MAX),
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        FOREIGN KEY (party_id) REFERENCES parties(id) ON DELETE CASCADE
    );
END;

-- Retention policies (Art. 5)
IF OBJECT_ID('retention_policies', 'U') IS NULL
BEGIN
    CREATE TABLE retention_policies (
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        entity_type NVARCHAR(50) NOT NULL UNIQUE,
        retention_years INT NOT NULL,
        legal_basis NVARCHAR(200),
        auto_anonymize BIT DEFAULT 1
    );
END;

-- Seed retention policies (idempotent — only if table is empty)
IF NOT EXISTS (SELECT 1 FROM retention_policies)
BEGIN
    INSERT INTO retention_policies (id, entity_type, retention_years, legal_basis) VALUES
    (NEWID(), 'policies', 10, 'Insurance regulation — record retention'),
    (NEWID(), 'claims', 10, 'Insurance regulation — claims records'),
    (NEWID(), 'submissions', 7, 'Business records retention'),
    (NEWID(), 'parties', 10, 'Insurance regulation — customer records');
END;

-- Index on consent_records for party lookups
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_consent_records_party_id')
    CREATE INDEX IX_consent_records_party_id ON consent_records(party_id);

-- Index on consent_records for purpose lookups
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_consent_records_purpose')
    CREATE INDEX IX_consent_records_purpose ON consent_records(party_id, purpose);
