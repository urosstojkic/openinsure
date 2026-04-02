# SQL Gotchas

Lessons learned from OpenInsure database development.

## Column Name Mappings

| API / Model Field | Actual SQL Column | Confidence |
|-------------------|-------------------|------------|
| `risk_data` | `cyber_risk_data` | High |
| `metadata` | `extracted_data` | High |

**Gotcha:** When both `metadata` and `extracted_data` are passed in an update, the SET clause gets duplicated. Handle deduplication explicitly.

## NULL Constraints

| Column | Constraint | Required Default | Confidence |
|--------|-----------|-----------------|------------|
| `effective_date` | NOT NULL | Default to today (`GETDATE()`) | High |
| `product_code` | NOT NULL | Auto-generate on create | High |

**Gotcha:** If you omit `effective_date` on insert, the DB will reject the row. Always provide a default.

## Type Coercion

| Column | SQL Type | Common Mistake | Fix | Confidence |
|--------|----------|---------------|-----|------------|
| `version` | INT | Passing string `"1.0"` | Coerce to int: `int(float(version))` | High |

## Auto-Managed Columns

| Column | Behavior | Implication |
|--------|----------|-------------|
| `updated_at` | Auto-set by trigger/default | Skip in UPDATE SET clause — do not include in update loop |

**Gotcha:** Including `updated_at` in your dynamic update builder will overwrite the auto-managed value. Filter it out of the column list before building the SET clause.
