-- Migration 013: Party indexes for deduplication
-- Issue #157 — idempotent via IF NOT EXISTS checks

-- Index on tax_id for exact-match party resolution (filtered: non-NULL only)
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_parties_tax_id')
    CREATE INDEX IX_parties_tax_id ON parties(tax_id) WHERE tax_id IS NOT NULL;

-- Index on name for case-insensitive party search
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_parties_name')
    CREATE INDEX IX_parties_name ON parties(name);

-- Unique constraint on tax_id (where not NULL) to prevent duplicate parties
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'UQ_parties_tax_id')
    CREATE UNIQUE INDEX UQ_parties_tax_id ON parties(tax_id) WHERE tax_id IS NOT NULL;

-- Index on registration_number for exact-match lookup
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_parties_registration_number')
    CREATE INDEX IX_parties_registration_number ON parties(registration_number) WHERE registration_number IS NOT NULL;
