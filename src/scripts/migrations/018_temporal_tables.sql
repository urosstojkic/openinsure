-- Migration 018: Temporal Tables (System-Versioned)
-- Enables SQL Server temporal tables on policies and claims for time-travel queries.
-- Azure SQL / SQL Server 2016+ feature. Skips gracefully if not supported.
-- Idempotent: safe to re-run.

-- ============================================================
-- 1. POLICIES — enable system-versioned temporal table
-- ============================================================

-- Only proceed if temporal is supported (SQL Server 2016+ / Azure SQL)
-- and the table is not already system-versioned.
IF SERVERPROPERTY('EngineEdition') IN (5, 8)  -- Azure SQL DB / Azure SQL Managed Instance
   OR CAST(SERVERPROPERTY('ProductMajorVersion') AS INT) >= 13  -- SQL Server 2016+
BEGIN
    -- 1a. Add temporal columns if they don't exist yet
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'policies' AND COLUMN_NAME = 'valid_from'
    )
    BEGIN
        ALTER TABLE policies ADD
            valid_from DATETIME2 GENERATED ALWAYS AS ROW START HIDDEN
                CONSTRAINT DF_policies_valid_from DEFAULT GETUTCDATE(),
            valid_to DATETIME2 GENERATED ALWAYS AS ROW END HIDDEN
                CONSTRAINT DF_policies_valid_to DEFAULT CONVERT(DATETIME2, '9999-12-31 23:59:59.9999999'),
            PERIOD FOR SYSTEM_TIME (valid_from, valid_to);
    END

    -- 1b. Enable system versioning if not already enabled
    IF NOT EXISTS (
        SELECT 1 FROM sys.tables
        WHERE name = 'policies' AND temporal_type = 2
    )
    BEGIN
        ALTER TABLE policies SET (
            SYSTEM_VERSIONING = ON (HISTORY_TABLE = dbo.policies_history)
        );
    END
END

GO

-- ============================================================
-- 2. CLAIMS — enable system-versioned temporal table
-- ============================================================

IF SERVERPROPERTY('EngineEdition') IN (5, 8)
   OR CAST(SERVERPROPERTY('ProductMajorVersion') AS INT) >= 13
BEGIN
    -- 2a. Add temporal columns if they don't exist yet
    IF NOT EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'claims' AND COLUMN_NAME = 'valid_from'
    )
    BEGIN
        ALTER TABLE claims ADD
            valid_from DATETIME2 GENERATED ALWAYS AS ROW START HIDDEN
                CONSTRAINT DF_claims_valid_from DEFAULT GETUTCDATE(),
            valid_to DATETIME2 GENERATED ALWAYS AS ROW END HIDDEN
                CONSTRAINT DF_claims_valid_to DEFAULT CONVERT(DATETIME2, '9999-12-31 23:59:59.9999999'),
            PERIOD FOR SYSTEM_TIME (valid_from, valid_to);
    END

    -- 2b. Enable system versioning if not already enabled
    IF NOT EXISTS (
        SELECT 1 FROM sys.tables
        WHERE name = 'claims' AND temporal_type = 2
    )
    BEGIN
        ALTER TABLE claims SET (
            SYSTEM_VERSIONING = ON (HISTORY_TABLE = dbo.claims_history)
        );
    END
END
