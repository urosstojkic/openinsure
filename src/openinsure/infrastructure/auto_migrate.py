"""Auto-apply pending SQL migrations on application startup.

Reads migration files from ``src/scripts/migrations/`` (relative to the
project root) and applies any that haven't been recorded in the
``_migration_history`` tracking table.  Each migration is idempotent —
already-existing objects are silently skipped.

This module is invoked from ``main.py`` on startup when ``storage_mode``
is ``"azure"`` and a SQL connection string is configured.
"""

from __future__ import annotations

import asyncio
import logging
import re
from functools import partial
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Migration directory — resolved relative to the package root.
# When running from source (local dev), parents[2] is ``src/``.
# When installed in a container, try ``/app/src/`` as fallback.
_MIGRATION_DIR = Path(__file__).resolve().parents[2] / "scripts" / "migrations"
if not _MIGRATION_DIR.is_dir():
    _MIGRATION_DIR = Path("/app/src/scripts/migrations")


async def apply_pending_migrations() -> list[str]:
    """Apply all pending SQL migrations.  Returns list of applied filenames."""
    from openinsure.infrastructure.factory import get_database_adapter

    db = get_database_adapter()
    if db is None:
        return []

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, partial(_apply_sync, db))


def _apply_sync(db: Any) -> list[str]:
    """Synchronous migration runner — runs in executor thread."""
    import pyodbc

    conn = db._connect()  # noqa: SLF001 — internal but needed for DDL
    conn.autocommit = True

    # Ensure tracking table exists
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = '_migration_history')
        CREATE TABLE _migration_history (
            id              INT IDENTITY(1,1) PRIMARY KEY,
            migration_name  NVARCHAR(200) NOT NULL UNIQUE,
            applied_at      DATETIME2 NOT NULL DEFAULT GETUTCDATE()
        )
    """)
    cursor.close()

    # Discover and apply
    if not _MIGRATION_DIR.is_dir():
        logger.warning("Migration directory not found: %s", _MIGRATION_DIR)
        conn.close()
        return []

    applied: list[str] = []
    for path in sorted(_MIGRATION_DIR.glob("*.sql")):
        name = path.name

        # Check if already applied
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM _migration_history WHERE migration_name = ?",
            [name],
        )
        row = cursor.fetchone()
        cursor.close()

        already_recorded = row and row[0] > 0

        # Repair: if recorded but target tables/columns are missing,
        # delete the stale record so the migration re-runs.
        if already_recorded:
            sql_text = path.read_text(encoding="utf-8")
            missing = False
            cursor = conn.cursor()

            # Check CREATE TABLE targets
            table_names = re.findall(r"(?i)CREATE\s+TABLE\s+(\w+)", sql_text)
            for tbl in table_names:
                cursor.execute(
                    "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
                    [tbl],
                )
                tbl_row = cursor.fetchone()
                if not tbl_row or tbl_row[0] == 0:
                    missing = True
                    break

            # Check ALTER TABLE ADD column targets (exclude CONSTRAINT additions)
            if not missing:
                alter_cols = re.findall(
                    r"(?i)ALTER\s+TABLE\s+(\w+)\s+ADD\s+(?!CONSTRAINT\b)(\w+)",
                    sql_text,
                )
                for tbl, col in alter_cols:
                    cursor.execute(
                        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_NAME = ? AND COLUMN_NAME = ?",
                        [tbl, col],
                    )
                    col_row = cursor.fetchone()
                    if not col_row or col_row[0] == 0:
                        # Verify table exists first
                        cursor.execute(
                            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?",
                            [tbl],
                        )
                        tbl_row = cursor.fetchone()
                        if tbl_row and tbl_row[0] > 0:
                            missing = True
                            break
            cursor.close()

            if missing:
                logger.info("Repair: migration %s recorded but objects missing, re-applying", name)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM _migration_history WHERE migration_name = ?",
                    [name],
                )
                cursor.close()
                already_recorded = False

        if already_recorded:
            continue

        # Read and execute
        sql = path.read_text(encoding="utf-8")
        sql = re.sub(r"(?i)\bBEGIN\s+TRANSACTION\b;?", "", sql)
        sql = re.sub(r"(?i)\bCOMMIT\s+TRANSACTION\b;?", "", sql)
        sql = re.sub(r"(?i)\bCOMMIT\b;?", "", sql)

        # Split on GO batch separator (T-SQL convention). If no GO
        # separators are present, execute the entire SQL as one batch
        # to preserve BEGIN/END blocks that contain semicolons.
        if re.search(r"^\s*GO\s*$", sql, re.MULTILINE):
            batches = [b.strip() for b in re.split(r"^\s*GO\s*$", sql, flags=re.MULTILINE) if b.strip()]
        else:
            batches = [sql.strip()] if sql.strip() else []

        cursor = conn.cursor()
        executed = 0
        for batch in batches:
            if not batch or batch.upper().startswith("PRINT"):
                continue
            try:
                cursor.execute(batch)
                executed += 1
            except pyodbc.ProgrammingError as e:
                err_msg = str(e)
                if "already an object named" in err_msg or "already exists" in err_msg:
                    continue
                logger.exception("Migration %s batch failed: %s", name, err_msg)
                raise
            except pyodbc.IntegrityError as e:
                err_msg = str(e)
                if "duplicate key" in err_msg:
                    logger.warning(
                        "Migration %s: duplicate key (data issue), skipping batch: %s",
                        name, err_msg[:200],
                    )
                    continue
                logger.exception("Migration %s integrity error: %s", name, err_msg)
                raise
        cursor.close()

        # Record (use IF NOT EXISTS to handle re-runs gracefully)
        cursor = conn.cursor()
        cursor.execute(
            "IF NOT EXISTS (SELECT 1 FROM _migration_history WHERE migration_name = ?) "
            "INSERT INTO _migration_history (migration_name) VALUES (?)",
            [name, name],
        )
        cursor.close()

        logger.info("Applied migration %s (%d batches)", name, executed)
        applied.append(name)

    conn.close()
    return applied
