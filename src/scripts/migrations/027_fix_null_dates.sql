-- Migration 027: Fix NULL effective/expiration dates on policies
-- Addresses issue #214: Some policies have NULL effective/expiration dates

-- Set effective_date to created_at date (or today) for policies missing it
UPDATE policies
SET effective_date = COALESCE(CAST(created_at AS DATE), CAST(GETUTCDATE() AS DATE))
WHERE effective_date IS NULL;

-- Set expiration_date to effective_date + 1 year for policies missing it
UPDATE policies
SET expiration_date = DATEADD(YEAR, 1, effective_date)
WHERE expiration_date IS NULL;

-- Backfill written_premium from total_premium where NULL
UPDATE policies
SET written_premium = COALESCE(total_premium, 0)
WHERE written_premium IS NULL OR written_premium = 0;
