-- =============================================================================
-- Migration 024: Product Template Inheritance
-- Adds parent_product_id and is_template columns to the products table,
-- enabling product inheritance (e.g. "Cyber SMB Plus" inherits from
-- "Cyber SMB" and overrides specific coverages/limits).
-- Idempotent: uses IF COL_LENGTH(...) IS NULL guards.
-- GitHub Issue: #177
-- =============================================================================

-- ---------------------------------------------------------------
-- 1. parent_product_id — self-referencing FK for inheritance chain
-- ---------------------------------------------------------------
IF COL_LENGTH('products', 'parent_product_id') IS NULL
    ALTER TABLE products ADD parent_product_id UNIQUEIDENTIFIER NULL
        CONSTRAINT FK_products_parent REFERENCES products(id);
GO

-- ---------------------------------------------------------------
-- 2. is_template — marks a product as a template (not directly quotable)
-- ---------------------------------------------------------------
IF COL_LENGTH('products', 'is_template') IS NULL
    ALTER TABLE products ADD is_template BIT DEFAULT 0;
GO

-- ---------------------------------------------------------------
-- 3. Index on parent_product_id for efficient hierarchy lookups
-- ---------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_products_parent')
    CREATE INDEX IX_products_parent ON products(parent_product_id)
    WHERE parent_product_id IS NOT NULL;
GO
