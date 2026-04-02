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
            # Also sync structured rating_factor_tables → rating_factor_tables SQL table (#319)
            await self._sync_rating_factor_tables(product_id, product_data.get("rating_factor_tables", []))
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
        """Get coverages from relational table, mapped to API field names."""
        rows = await self.db.fetch_all(
            "SELECT * FROM product_coverages WHERE product_id = ? ORDER BY sort_order",
            [product_id],
        )
        return [self._coverage_to_api(r) for r in rows]

    async def get_rating_factors(self, product_id: str) -> list[dict[str, Any]]:
        """Get rating factors from relational table."""
        rows = await self.db.fetch_all(
            "SELECT * FROM product_rating_factors WHERE product_id = ? ORDER BY sort_order",
            [product_id],
        )
        return [self._row_to_dict(r) for r in rows]

    async def get_rating_factor_tables(self, product_id: str) -> list[dict[str, Any]]:
        """Get rating factor lookup tables grouped by category.

        The SQL table stores one row per factor_key.  The API model
        expects ``{name, description, entries: [{key, multiplier, description}]}``
        grouped by ``factor_category``.
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM rating_factor_tables WHERE product_id = ? ORDER BY factor_category, sort_order",
            [product_id],
        )
        return self._group_rating_factors(rows)

    async def get_appetite_rules(self, product_id: str) -> list[dict[str, Any]]:
        """Get appetite rules mapped to the API model shape.

        SQL columns ``field_name``, ``rule_name``, ``numeric_value``, etc.
        are mapped to the API model fields ``field``, ``name``, ``value``.
        """
        rows = await self.db.fetch_all(
            "SELECT * FROM product_appetite_rules WHERE product_id = ? ORDER BY sort_order",
            [product_id],
        )
        return [self._appetite_rule_to_api(r) for r in rows]

    async def get_authority_limits(self, product_id: str) -> dict[str, Any] | None:
        """Get authority limits from relational table, mapped to API shape."""
        row = await self.db.fetch_one(
            "SELECT * FROM product_authority_limits WHERE product_id = ?",
            [product_id],
        )
        return self._authority_to_api(row) if row else None

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
            # Auto-generate coverage code from name when not provided (API-created products)
            if not code and name:
                code = name.upper().replace(" ", "-").replace("/", "-")[:50]
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

    async def _sync_rating_factor_tables(self, product_id: str, tables: Any) -> None:
        """Upsert structured rating factor tables into ``rating_factor_tables`` (#319).

        The API model stores tables as ``[{name, description, entries: [{key, multiplier, description}]}]``.
        The SQL table stores one row per (factor_category, factor_key).
        """
        items = self._ensure_list(tables)
        if not items:
            return

        await self.db.execute_query("DELETE FROM rating_factor_tables WHERE product_id = ?", [product_id])

        from uuid import uuid4

        sort_order = 0
        for table in items:
            if not isinstance(table, dict):
                continue
            category = table.get("name") or table.get("factor_category", "")
            if not category:
                continue
            table_desc = table.get("description", "")
            for entry in self._ensure_list(table.get("entries", [])):
                if not isinstance(entry, dict):
                    continue
                factor_key = entry.get("key") or entry.get("factor_key", "")
                if not factor_key:
                    continue
                multiplier = self._dec(entry.get("multiplier", 1.0))
                entry_desc = entry.get("description", table_desc)
                await self.db.execute_query(
                    """INSERT INTO rating_factor_tables
                       (id, product_id, factor_category, factor_key, multiplier,
                        description, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [
                        str(uuid4()),
                        product_id,
                        str(category),
                        str(factor_key),
                        multiplier,
                        entry_desc,
                        sort_order,
                    ],
                )
                sort_order += 1

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

            operator = str(ar.get("operator", "="))
            api_value = ar.get("value")  # API model uses 'value', not SQL column names

            # Extract numeric_value / numeric_min / numeric_max from API 'value'
            # when the SQL column names aren't present in the dict.
            numeric_value = ar.get("numeric_value")
            numeric_min = ar.get("numeric_min")
            numeric_max = ar.get("numeric_max")
            string_value = ar.get("string_value")

            if (
                api_value is not None
                and numeric_value is None
                and numeric_min is None
                and numeric_max is None
                and string_value is None
            ):
                if operator == "between" and isinstance(api_value, dict):
                    numeric_min = api_value.get("min")
                    numeric_max = api_value.get("max")
                elif operator in ("in", "not_in"):
                    if isinstance(api_value, list):
                        string_value = ",".join(str(v) for v in api_value)
                    else:
                        string_value = str(api_value)
                elif isinstance(api_value, (int, float)):
                    numeric_value = api_value
                elif isinstance(api_value, str):
                    try:
                        numeric_value = float(api_value)
                    except (ValueError, TypeError):
                        string_value = api_value

            await self.db.execute_query(
                """INSERT INTO product_appetite_rules
                   (product_id, rule_name, field_name, operator, value_type,
                    numeric_value, numeric_min, numeric_max, string_value,
                    description, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    product_id,
                    ar.get("rule_name") or ar.get("name"),
                    str(field),
                    operator,
                    str(ar.get("value_type", "numeric")),
                    self._dec(numeric_value),
                    self._dec(numeric_min),
                    self._dec(numeric_max),
                    string_value,
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

        # Accept both SQL column names and API model names
        auto_bind_premium = self._dec(limits.get("auto_bind_premium_max") or limits.get("max_auto_bind_premium"))
        auto_bind_limit = self._dec(limits.get("auto_bind_limit_max") or limits.get("max_auto_bind_limit"))

        await self.db.execute_query(
            """INSERT INTO product_authority_limits
               (product_id, auto_bind_premium_max, auto_bind_limit_max,
                requires_senior_review_above, requires_cuo_review_above)
               VALUES (?, ?, ?, ?, ?)""",
            [
                product_id,
                auto_bind_premium,
                auto_bind_limit,
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
                """SELECT factor_category, factor_key, multiplier
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
                result[cat][str(r.get("factor_key", ""))] = float(r.get("multiplier", 1.0))
            return result
        except Exception:
            logger.debug(
                "product_relations.get_factors_flat_fallback",
                product_id=product_id,
                exc_info=True,
            )
            return {}

    async def get_rating_factors_as_of(self, product_id: str, as_of_date: str) -> dict[str, dict[str, float]]:
        """Return rating factors effective at a specific date.

        Filters ``rating_factor_tables`` to rows where:
        - effective_date <= as_of_date (or effective_date IS NULL)
        - expiration_date > as_of_date (or expiration_date IS NULL)

        Used for historical rating / regulatory audit.
        """
        try:
            rows = await self.db.fetch_all(
                """SELECT factor_category, factor_key, multiplier
                   FROM rating_factor_tables
                   WHERE product_id = ?
                     AND (effective_date IS NULL OR effective_date <= ?)
                     AND (expiration_date IS NULL OR expiration_date > ?)
                   ORDER BY factor_category, sort_order""",
                [product_id, as_of_date, as_of_date],
            )
            result: dict[str, dict[str, float]] = {}
            for r in rows:
                cat = str(r.get("factor_category", ""))
                if cat not in result:
                    result[cat] = {}
                result[cat][str(r.get("factor_key", ""))] = float(r.get("multiplier", 1.0))
            return result
        except Exception:
            logger.debug(
                "product_relations.get_factors_as_of_fallback",
                product_id=product_id,
                as_of_date=as_of_date,
                exc_info=True,
            )
            return {}

    async def version_rating_factor(
        self,
        product_id: str,
        factor_category: str,
        factor_key: str,
        new_multiplier: float,
        description: str | None = None,
    ) -> dict[str, Any] | None:
        """Insert a new version of a rating factor and expire the old one.

        Instead of UPDATE, this implements version history:
        1. SET expiration_date on the current active row
        2. INSERT a new row with the new multiplier and today's effective_date
        """
        from datetime import UTC, datetime

        today = datetime.now(UTC).strftime("%Y-%m-%d")

        # Expire the current active version
        await self.db.execute_query(
            """UPDATE rating_factor_tables
               SET expiration_date = ?
               WHERE product_id = ?
                 AND factor_category = ?
                 AND factor_key = ?
                 AND (expiration_date IS NULL OR expiration_date > ?)""",
            [today, product_id, factor_category, factor_key, today],
        )

        # Insert new version
        from uuid import uuid4

        new_id = str(uuid4())
        await self.db.execute_query(
            """INSERT INTO rating_factor_tables
               (id, product_id, factor_category, factor_key, multiplier,
                description, effective_date, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
            [
                new_id,
                product_id,
                factor_category,
                factor_key,
                new_multiplier,
                description,
                today,
            ],
        )

        return {
            "id": new_id,
            "product_id": product_id,
            "factor_category": factor_category,
            "factor_key": factor_key,
            "multiplier": new_multiplier,
            "effective_date": today,
        }

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

    @staticmethod
    def _coverage_to_api(row: dict[str, Any]) -> dict[str, Any]:
        """Map relational coverage row to CoverageDefinition API shape."""
        return {
            "name": row.get("coverage_name") or row.get("name") or row.get("coverage_code", ""),
            "description": str(row.get("description") or ""),
            "default_limit": float(row.get("default_limit") or 0),
            "max_limit": float(row.get("max_limit") or 0),
            "default_deductible": float(row.get("default_deductible") or 0),
            "is_optional": bool(row.get("is_optional", False)),
        }

    @staticmethod
    def _authority_to_api(row: dict[str, Any]) -> dict[str, Any]:
        """Map relational authority limits row to AuthorityLimit API shape."""
        return {
            "max_auto_bind_premium": float(row.get("auto_bind_premium_max") or 0),
            "max_auto_bind_limit": float(row.get("auto_bind_limit_max") or 0),
            "requires_senior_review_above": float(row.get("requires_senior_review_above") or 0),
            "requires_cuo_review_above": float(row.get("requires_cuo_review_above") or 0),
        }

    @staticmethod
    def _group_rating_factors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group flat SQL rows into ``RatingFactorTable``-shaped dicts.

        SQL stores one row per (factor_category, factor_key).  The API
        model expects ``{name, description, entries: [{key, multiplier, description}]}``
        grouped by ``factor_category``.
        """
        from collections import OrderedDict

        groups: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for r in rows:
            cat = str(r.get("factor_category") or r.get("name") or "unknown")
            if cat not in groups:
                groups[cat] = {
                    "name": cat,
                    "description": str(r.get("description") or ""),
                    "entries": [],
                }
            groups[cat]["entries"].append(
                {
                    "key": str(r.get("factor_key") or ""),
                    "multiplier": float(r.get("multiplier") or r.get("factor_value") or 1.0),
                    "description": str(r.get("description") or ""),
                }
            )
        return list(groups.values())

    @staticmethod
    def _appetite_rule_to_api(row: dict[str, Any]) -> dict[str, Any]:
        """Map a relational appetite rule row to ``AppetiteRule`` API shape.

        SQL columns: ``rule_name``, ``field_name``, ``operator``,
        ``value_type``, ``numeric_value``, ``numeric_min``, ``numeric_max``,
        ``string_value``, ``description``.

        API model: ``name``, ``field``, ``operator``, ``value``, ``description``.
        """
        operator = str(row.get("operator") or "eq")
        value_type = str(row.get("value_type") or "numeric")

        # Determine value based on operator and value_type
        if operator == "between":
            num_min = row.get("numeric_min")
            num_max = row.get("numeric_max")
            value: Any = {
                "min": float(num_min) if num_min is not None else 0,
                "max": float(num_max) if num_max is not None else 0,
            }
        elif operator in ("in", "not_in"):
            sv = row.get("string_value") or ""
            value = [v.strip() for v in str(sv).split(",") if v.strip()]
        elif value_type == "numeric" or row.get("numeric_value") is not None:
            nv = row.get("numeric_value")
            value = float(nv) if nv is not None else 0
        else:
            value = row.get("string_value") or ""

        return {
            "name": str(row.get("rule_name") or row.get("name") or ""),
            "field": str(row.get("field_name") or row.get("field") or ""),
            "operator": operator,
            "value": value,
            "description": str(row.get("description") or ""),
        }
