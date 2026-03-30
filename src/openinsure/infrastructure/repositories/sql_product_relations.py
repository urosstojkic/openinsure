"""Dual-write repository for normalised product relational tables.

Syncs JSON blob data from the ``products`` table into dedicated relational
tables (coverages, rating factors, appetite rules, etc.) so they can be
queried, indexed, and joined without parsing JSON at read time.

The JSON columns on ``products`` remain the source of truth during the
transition period.  Reads fall back to JSON when relational rows are empty.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from openinsure.infrastructure.database import DatabaseAdapter

logger = structlog.get_logger()


class ProductRelationsRepository:
    """Manages relational product data (coverages, factors, rules, etc.).

    Designed for **dual-write**: after every product create/update the caller
    invokes :meth:`sync_from_product` which upserts all child tables from the
    product dict.  Reads prefer the relational tables and fall back to the
    original JSON columns when no relational rows exist yet.
    """

    def __init__(self, db: DatabaseAdapter) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Public sync entry point
    # ------------------------------------------------------------------

    async def sync_from_product(self, product_id: str, product_data: dict[str, Any]) -> None:
        """Sync all relational tables from a product dict (dual-write)."""
        try:
            await self._sync_coverages(product_id, product_data.get("coverages", []))
            await self._sync_rating_factors(product_id, product_data.get("rating_factors", []))
            await self._sync_appetite_rules(product_id, product_data.get("appetite_rules", []))
            await self._sync_authority_limits(product_id, product_data.get("authority_limits", {}))
            await self._sync_territories(product_id, product_data.get("territories", []))
            await self._sync_forms(product_id, product_data.get("forms", []))
            await self._sync_pricing(product_id, product_data.get("metadata", {}))
        except Exception:
            logger.warning(
                "product_relations_sync_failed",
                product_id=product_id,
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Public read helpers
    # ------------------------------------------------------------------

    async def get_coverages(self, product_id: str) -> list[dict[str, Any]]:
        """Get coverages from relational table."""
        rows = await self.db.fetch_all(
            "SELECT * FROM product_coverages WHERE product_id = ? ORDER BY sort_order",
            [product_id],
        )
        return [self._row_to_dict(r) for r in rows]

    async def get_rating_factors(self, product_id: str) -> list[dict[str, Any]]:
        """Get rating factors from relational table."""
        rows = await self.db.fetch_all(
            "SELECT * FROM product_rating_factors WHERE product_id = ? ORDER BY sort_order",
            [product_id],
        )
        return [self._row_to_dict(r) for r in rows]

    async def get_rating_factor_tables(self, product_id: str) -> list[dict[str, Any]]:
        """Get rating factor lookup tables from relational table."""
        rows = await self.db.fetch_all(
            "SELECT * FROM rating_factor_tables WHERE product_id = ? ORDER BY factor_category, sort_order",
            [product_id],
        )
        return [self._row_to_dict(r) for r in rows]

    async def get_appetite_rules(self, product_id: str) -> list[dict[str, Any]]:
        """Get appetite rules from relational table."""
        rows = await self.db.fetch_all(
            "SELECT * FROM product_appetite_rules WHERE product_id = ? ORDER BY sort_order",
            [product_id],
        )
        return [self._row_to_dict(r) for r in rows]

    async def get_authority_limits(self, product_id: str) -> dict[str, Any] | None:
        """Get authority limits from relational table."""
        row = await self.db.fetch_one(
            "SELECT * FROM product_authority_limits WHERE product_id = ?",
            [product_id],
        )
        return self._row_to_dict(row) if row else None

    async def get_territories(self, product_id: str) -> list[dict[str, Any]]:
        """Get territories from relational table."""
        rows = await self.db.fetch_all(
            "SELECT * FROM product_territories WHERE product_id = ? ORDER BY territory_code",
            [product_id],
        )
        return [self._row_to_dict(r) for r in rows]

    async def get_forms(self, product_id: str) -> list[dict[str, Any]]:
        """Get forms from relational table."""
        rows = await self.db.fetch_all(
            "SELECT * FROM product_forms WHERE product_id = ? ORDER BY form_code",
            [product_id],
        )
        return [self._row_to_dict(r) for r in rows]

    async def get_pricing(self, product_id: str) -> dict[str, Any] | None:
        """Get pricing from relational table."""
        row = await self.db.fetch_one(
            "SELECT * FROM product_pricing WHERE product_id = ?",
            [product_id],
        )
        return self._row_to_dict(row) if row else None

    # ------------------------------------------------------------------
    # Private sync helpers
    # ------------------------------------------------------------------

    async def _sync_coverages(self, product_id: str, coverages: Any) -> None:
        """Upsert coverages into ``product_coverages``."""
        items = self._ensure_list(coverages)
        if not items:
            return

        # Delete existing rows and re-insert (simpler than row-level merge)
        await self.db.execute_query("DELETE FROM product_coverages WHERE product_id = ?", [product_id])

        for idx, cov in enumerate(items):
            if not isinstance(cov, dict):
                continue
            code = cov.get("code") or cov.get("coverage_code")
            name = cov.get("name") or cov.get("coverage_name") or code
            if not code:
                continue
            await self.db.execute_query(
                """INSERT INTO product_coverages
                   (product_id, coverage_code, coverage_name, description,
                    default_limit, min_limit, max_limit, default_deductible,
                    is_optional, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    product_id,
                    str(code),
                    str(name),
                    cov.get("description"),
                    self._dec(cov.get("default_limit")),
                    self._dec(cov.get("min_limit")),
                    self._dec(cov.get("max_limit")),
                    self._dec(cov.get("default_deductible")),
                    1 if cov.get("is_optional") else 0,
                    idx,
                ],
            )

    async def _sync_rating_factors(self, product_id: str, factors: Any) -> None:
        """Upsert rating factors into ``product_rating_factors``."""
        items = self._ensure_list(factors)
        if not items:
            return

        await self.db.execute_query("DELETE FROM product_rating_factors WHERE product_id = ?", [product_id])

        for idx, rf in enumerate(items):
            if not isinstance(rf, dict):
                continue
            name = rf.get("factor_name") or rf.get("name")
            if not name:
                continue
            await self.db.execute_query(
                """INSERT INTO product_rating_factors
                   (product_id, factor_name, factor_type, weight, description, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    product_id,
                    str(name),
                    str(rf.get("factor_type", "numeric")),
                    self._dec(rf.get("weight")),
                    rf.get("description"),
                    idx,
                ],
            )

    async def _sync_appetite_rules(self, product_id: str, rules: Any) -> None:
        """Upsert appetite rules into ``product_appetite_rules``."""
        items = self._ensure_list(rules)
        if not items:
            return

        await self.db.execute_query("DELETE FROM product_appetite_rules WHERE product_id = ?", [product_id])

        for idx, ar in enumerate(items):
            if not isinstance(ar, dict):
                continue
            field = ar.get("field_name") or ar.get("field")
            if not field:
                continue
            await self.db.execute_query(
                """INSERT INTO product_appetite_rules
                   (product_id, rule_name, field_name, operator, value_type,
                    numeric_value, numeric_min, numeric_max, string_value,
                    description, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    product_id,
                    ar.get("rule_name"),
                    str(field),
                    str(ar.get("operator", "=")),
                    str(ar.get("value_type", "numeric")),
                    self._dec(ar.get("numeric_value")),
                    self._dec(ar.get("numeric_min")),
                    self._dec(ar.get("numeric_max")),
                    ar.get("string_value"),
                    ar.get("description"),
                    idx,
                ],
            )

    async def _sync_authority_limits(self, product_id: str, limits: Any) -> None:
        """Upsert authority limits into ``product_authority_limits``."""
        if not limits or not isinstance(limits, dict):
            return

        # Use MERGE-style: delete then insert (only one row per product)
        await self.db.execute_query("DELETE FROM product_authority_limits WHERE product_id = ?", [product_id])

        await self.db.execute_query(
            """INSERT INTO product_authority_limits
               (product_id, auto_bind_premium_max, auto_bind_limit_max,
                requires_senior_review_above, requires_cuo_review_above)
               VALUES (?, ?, ?, ?, ?)""",
            [
                product_id,
                self._dec(limits.get("auto_bind_premium_max")),
                self._dec(limits.get("auto_bind_limit_max")),
                self._dec(limits.get("requires_senior_review_above")),
                self._dec(limits.get("requires_cuo_review_above")),
            ],
        )

    async def _sync_territories(self, product_id: str, territories: Any) -> None:
        """Upsert territories into ``product_territories``."""
        items = self._ensure_list(territories)
        if not items:
            return

        await self.db.execute_query("DELETE FROM product_territories WHERE product_id = ?", [product_id])

        for territory in items:
            # Territories can be plain strings ("US") or dicts ({"code": "US", ...})
            if isinstance(territory, dict):
                code = territory.get("territory_code") or territory.get("code", "")
                status = territory.get("approval_status", "approved")
                ref = territory.get("filing_reference")
                eff = territory.get("effective_date")
                exp = territory.get("expiration_date")
            else:
                code = str(territory).strip()
                status = "approved"
                ref = None
                eff = None
                exp = None

            if not code:
                continue

            await self.db.execute_query(
                """INSERT INTO product_territories
                   (product_id, territory_code, approval_status,
                    filing_reference, effective_date, expiration_date)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [product_id, code, status, ref, eff, exp],
            )

    async def _sync_forms(self, product_id: str, forms: Any) -> None:
        """Upsert forms into ``product_forms``."""
        items = self._ensure_list(forms)
        if not items:
            return

        await self.db.execute_query("DELETE FROM product_forms WHERE product_id = ?", [product_id])

        for form in items:
            if not isinstance(form, dict):
                continue
            code = form.get("form_code") or form.get("code")
            if not code:
                continue
            await self.db.execute_query(
                """INSERT INTO product_forms
                   (product_id, form_code, form_name, form_type,
                    form_version, required, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    product_id,
                    str(code),
                    form.get("form_name") or form.get("name"),
                    form.get("form_type") or form.get("type"),
                    form.get("form_version") or form.get("version"),
                    1 if form.get("required", True) else 0,
                    form.get("url"),
                ],
            )

    async def _sync_pricing(self, product_id: str, metadata: Any) -> None:
        """Upsert pricing into ``product_pricing`` from metadata dict."""
        if not metadata or not isinstance(metadata, dict):
            return

        # Only sync if there are pricing-relevant keys
        pricing_keys = {"min_premium", "max_premium", "base_rate_per_1000", "currency"}
        if not pricing_keys & set(metadata.keys()):
            return

        await self.db.execute_query("DELETE FROM product_pricing WHERE product_id = ?", [product_id])

        await self.db.execute_query(
            """INSERT INTO product_pricing
               (product_id, min_premium, max_premium, base_rate_per_1000, currency)
               VALUES (?, ?, ?, ?, ?)""",
            [
                product_id,
                self._dec(metadata.get("min_premium")),
                self._dec(metadata.get("max_premium")),
                self._dec(metadata.get("base_rate_per_1000")),
                metadata.get("currency", "USD"),
            ],
        )

    # ------------------------------------------------------------------
    # Read: rating factors — flat dict for rating engine
    # ------------------------------------------------------------------

    async def get_rating_factors_flat(self, product_id: str) -> dict[str, dict[str, float]]:
        """Return rating factor lookup tables as ``{category: {key: multiplier}}``.

        Used by the rating engine to load product-specific factors from
        the relational ``rating_factor_tables`` table.  Returns an empty
        dict when no relational rows exist (caller should fall back to
        hardcoded factors).
        """
        try:
            rows = await self.db.fetch_all(
                """SELECT factor_category, factor_key, factor_value
                   FROM rating_factor_tables
                   WHERE product_id = ?
                   ORDER BY factor_category, sort_order""",
                [product_id],
            )
            result: dict[str, dict[str, float]] = {}
            for r in rows:
                cat = str(r.get("factor_category", ""))
                if cat not in result:
                    result[cat] = {}
                result[cat][str(r.get("factor_key", ""))] = float(r.get("factor_value", 1.0))
            return result
        except Exception:
            logger.debug(
                "product_relations.get_factors_flat_fallback",
                product_id=product_id,
                exc_info=True,
            )
            return {}

    # ------------------------------------------------------------------
    # Evaluate appetite rules against risk data
    # ------------------------------------------------------------------

    async def check_appetite(self, product_id: str, risk_data: dict[str, Any]) -> tuple[bool, list[str]]:
        """Evaluate all appetite rules for *product_id* against *risk_data*.

        Returns ``(passes, reasons)`` where *passes* is ``True`` when
        every rule is satisfied.  When the relational table has no rows,
        returns ``(True, [])`` so the caller can fall back to legacy
        logic.
        """
        rules = await self.get_appetite_rules(product_id)
        if not rules:
            return True, []

        reasons: list[str] = []
        for rule in rules:
            field = str(rule.get("field_name", rule.get("field", "")))
            operator = str(rule.get("operator", "="))
            actual = risk_data.get(field)

            if actual is None:
                continue  # skip rules for fields not present in risk data

            if not self._evaluate_rule(actual, operator, rule):
                label = rule.get("rule_name") or field
                reasons.append(f"{label}: failed ({field} {operator}, actual={actual})")

        return len(reasons) == 0, reasons

    @staticmethod
    def _evaluate_rule(actual: Any, operator: str, rule: dict[str, Any]) -> bool:
        """Evaluate one appetite rule against an actual value."""
        try:
            # Numeric checks use the dedicated numeric columns
            num_val = rule.get("numeric_value")
            num_min = rule.get("numeric_min")
            num_max = rule.get("numeric_max")
            str_val = rule.get("string_value", "")

            if operator in (">=", "gte"):
                return float(actual) >= float(num_val or num_min or 0)
            if operator in ("<=", "lte"):
                return float(actual) <= float(num_val or num_max or 0)
            if operator in (">", "gt"):
                return float(actual) > float(num_val or num_min or 0)
            if operator in ("<", "lt"):
                return float(actual) < float(num_val or num_max or 0)
            if operator in ("=", "eq"):
                if num_val is not None:
                    return float(actual) == float(num_val)
                return str(actual).lower() == str(str_val).lower()
            if operator in ("!=", "neq"):
                if num_val is not None:
                    return float(actual) != float(num_val)
                return str(actual).lower() != str(str_val).lower()
            if operator == "between":
                if num_min is not None and num_max is not None:
                    return float(num_min) <= float(actual) <= float(num_max)
                return True
            if operator == "in":
                vals = [v.strip().lower() for v in (str_val or "").split(",") if v.strip()]
                return str(actual).lower() in vals
            if operator == "not_in":
                vals = [v.strip().lower() for v in (str_val or "").split(",") if v.strip()]
                return str(actual).lower() not in vals
        except (ValueError, TypeError):
            return True  # fail-open on parse errors
        return True

    # ------------------------------------------------------------------
    # Summary counts (for lightweight list endpoint)
    # ------------------------------------------------------------------

    async def get_relation_counts(self, product_id: str) -> dict[str, int]:
        """Return summary counts of child rows (coverages, factors, rules).

        Used by the list endpoint to include summary fields without
        loading full relation data.
        """
        counts: dict[str, int] = {
            "coverage_count": 0,
            "factor_count": 0,
            "appetite_rule_count": 0,
        }
        try:
            for table, key in [
                ("product_coverages", "coverage_count"),
                ("rating_factor_tables", "factor_count"),
                ("product_appetite_rules", "appetite_rule_count"),
            ]:
                row = await self.db.fetch_one(
                    f"SELECT COUNT(*) AS cnt FROM {table} WHERE product_id = ?",  # noqa: S608
                    [product_id],
                )
                if row:
                    counts[key] = int(row.get("cnt", 0))
        except Exception:
            logger.debug(
                "product_relations.get_counts_failed",
                product_id=product_id,
                exc_info=True,
            )
        return counts

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_list(value: Any) -> list[Any]:
        """Coerce a value into a list, deserialising JSON strings if needed."""
        if value is None:
            return []
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            return []
        if isinstance(value, list):
            return value
        return []

    @staticmethod
    def _dec(value: Any) -> Any:
        """Convert a value to float for SQL parameter binding, or None."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
        """Convert a SQL row dict, serialising UUID/datetime values."""
        result: dict[str, Any] = {}
        for key, val in row.items():
            if hasattr(val, "isoformat"):
                result[key] = val.isoformat()
            elif isinstance(val, (bytes, bytearray)):
                result[key] = val.hex()
            else:
                result[key] = val
        return result
