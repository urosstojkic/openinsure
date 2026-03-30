-- =============================================================================
-- Migration 023: Multi-Currency Foundation
-- Adds currency NVARCHAR(3) DEFAULT 'USD' to all monetary tables and creates
-- an exchange_rates reference table for future currency conversion.
-- Idempotent: uses IF COL_LENGTH(...) IS NULL guards.
-- GitHub Issue: #174
-- =============================================================================

-- ---------------------------------------------------------------
-- 1. policies
-- ---------------------------------------------------------------
IF COL_LENGTH('policies', 'currency') IS NULL
    ALTER TABLE policies ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 2. claims
-- ---------------------------------------------------------------
IF COL_LENGTH('claims', 'currency') IS NULL
    ALTER TABLE claims ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 3. claim_reserves
-- ---------------------------------------------------------------
IF COL_LENGTH('claim_reserves', 'currency') IS NULL
    ALTER TABLE claim_reserves ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 4. claim_payments
-- ---------------------------------------------------------------
IF COL_LENGTH('claim_payments', 'currency') IS NULL
    ALTER TABLE claim_payments ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 5. billing_accounts
-- ---------------------------------------------------------------
IF COL_LENGTH('billing_accounts', 'currency') IS NULL
    ALTER TABLE billing_accounts ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 6. invoices
-- ---------------------------------------------------------------
IF COL_LENGTH('invoices', 'currency') IS NULL
    ALTER TABLE invoices ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 7. reinsurance_treaties
-- ---------------------------------------------------------------
IF COL_LENGTH('reinsurance_treaties', 'currency') IS NULL
    ALTER TABLE reinsurance_treaties ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 8. reinsurance_cessions
-- ---------------------------------------------------------------
IF COL_LENGTH('reinsurance_cessions', 'currency') IS NULL
    ALTER TABLE reinsurance_cessions ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 9. reinsurance_recoveries
-- ---------------------------------------------------------------
IF COL_LENGTH('reinsurance_recoveries', 'currency') IS NULL
    ALTER TABLE reinsurance_recoveries ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 10. products
-- ---------------------------------------------------------------
IF COL_LENGTH('products', 'currency') IS NULL
    ALTER TABLE products ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 11. product_pricing — already has currency (migration 015),
--     but guard anyway for safety
-- ---------------------------------------------------------------
IF COL_LENGTH('product_pricing', 'currency') IS NULL
    ALTER TABLE product_pricing ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 12. submissions — currency on quoted_premium
-- ---------------------------------------------------------------
IF COL_LENGTH('submissions', 'currency') IS NULL
    ALTER TABLE submissions ADD currency NVARCHAR(3) DEFAULT 'USD';
GO

-- ---------------------------------------------------------------
-- 13. exchange_rates reference table
-- ---------------------------------------------------------------
IF OBJECT_ID('exchange_rates', 'U') IS NULL
CREATE TABLE exchange_rates (
    id              UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    from_currency   NVARCHAR(3)      NOT NULL,
    to_currency     NVARCHAR(3)      NOT NULL,
    rate            DECIMAL(18,8)    NOT NULL,
    effective_date  DATE             NOT NULL,
    created_at      DATETIME2        NOT NULL DEFAULT GETUTCDATE(),
    CONSTRAINT UQ_exchange_rate UNIQUE (from_currency, to_currency, effective_date)
);
GO

-- Index for efficient lookups by currency pair + date
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_exchange_rates_pair_date')
    CREATE INDEX IX_exchange_rates_pair_date
        ON exchange_rates(from_currency, to_currency, effective_date DESC);
GO

-- Seed common exchange rates (baseline rates as of 2026-01-01)
INSERT INTO exchange_rates (from_currency, to_currency, rate, effective_date)
SELECT 'USD', 'GBP', 0.79000000, '2026-01-01'
WHERE NOT EXISTS (
    SELECT 1 FROM exchange_rates
    WHERE from_currency = 'USD' AND to_currency = 'GBP' AND effective_date = '2026-01-01'
);

INSERT INTO exchange_rates (from_currency, to_currency, rate, effective_date)
SELECT 'USD', 'EUR', 0.92000000, '2026-01-01'
WHERE NOT EXISTS (
    SELECT 1 FROM exchange_rates
    WHERE from_currency = 'USD' AND to_currency = 'EUR' AND effective_date = '2026-01-01'
);

INSERT INTO exchange_rates (from_currency, to_currency, rate, effective_date)
SELECT 'GBP', 'USD', 1.26580000, '2026-01-01'
WHERE NOT EXISTS (
    SELECT 1 FROM exchange_rates
    WHERE from_currency = 'GBP' AND to_currency = 'USD' AND effective_date = '2026-01-01'
);

INSERT INTO exchange_rates (from_currency, to_currency, rate, effective_date)
SELECT 'EUR', 'USD', 1.08700000, '2026-01-01'
WHERE NOT EXISTS (
    SELECT 1 FROM exchange_rates
    WHERE from_currency = 'EUR' AND to_currency = 'USD' AND effective_date = '2026-01-01'
);
GO
