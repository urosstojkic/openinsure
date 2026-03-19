"""Run SQL migrations against the deployed Azure SQL database.

Uses the same connection pattern as the application's DatabaseAdapter —
``DefaultAzureCredential`` for passwordless AAD authentication via
``pyodbc`` and ``SQL_COPT_SS_ACCESS_TOKEN``.

Usage:
    # Run all pending migrations
    python src/scripts/run_migration.py

    # Run a specific migration file
    python src/scripts/run_migration.py src/scripts/migrations/002_carrier_modules_schema.sql

    # Override the connection string (default reads OPENINSURE_SQL_CONNECTION_STRING from .env)
    OPENINSURE_SQL_CONNECTION_STRING=myserver.database.windows.net python src/scripts/run_migration.py

Environment variables:
    OPENINSURE_SQL_CONNECTION_STRING  — server hostname or full ODBC connection string
    OPENINSURE_SQL_DATABASE_NAME     — target database (default: "openinsure")
"""

from __future__ import annotations

import os
import re
import struct
import sys
from pathlib import Path

try:
    import pyodbc
    from azure.identity import DefaultAzureCredential
except ImportError:
    print("ERROR: pyodbc and azure-identity are required.")
    print("  pip install pyodbc azure-identity")
    sys.exit(1)

# Load .env if dotenv is available
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MIGRATION_DIR = Path(__file__).parent / "migrations"
SQL_RESOURCE = "https://database.windows.net/.default"

CONN_STRING_OR_SERVER = os.environ.get("OPENINSURE_SQL_CONNECTION_STRING", "")
DATABASE = os.environ.get("OPENINSURE_SQL_DATABASE_NAME", "openinsure")

TRACKING_TABLE_DDL = """
IF NOT EXISTS (
    SELECT 1 FROM sys.tables WHERE name = '_migration_history'
)
CREATE TABLE _migration_history (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    migration_name  NVARCHAR(200) NOT NULL UNIQUE,
    applied_at      DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    checksum        NVARCHAR(64)
);
"""


# ---------------------------------------------------------------------------
# Connection helper (mirrors database.py)
# ---------------------------------------------------------------------------


def _detect_odbc_driver() -> str:
    """Return the best available SQL Server ODBC driver."""
    drivers = pyodbc.drivers()
    for preferred in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if preferred in drivers:
            return preferred
    # Last resort
    return "ODBC Driver 17 for SQL Server"


def connect(conn_str_or_server: str, database: str) -> pyodbc.Connection:
    """Create a pyodbc connection using AAD access-token authentication."""
    credential = DefaultAzureCredential()
    token = credential.get_token(SQL_RESOURCE).token
    token_bytes = token.encode("UTF-16-LE")
    token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

    if "Driver=" in conn_str_or_server or "driver=" in conn_str_or_server:
        odbc_str = re.sub(r"Authentication=[^;]*;?", "", conn_str_or_server)
        # Replace driver if the specified one isn't available
        driver = _detect_odbc_driver()
        odbc_str = re.sub(r"Driver=\{[^}]+\}", f"Driver={{{driver}}}", odbc_str)
    else:
        driver = _detect_odbc_driver()
        odbc_str = (
            f"Driver={{{driver}}};"
            f"Server={conn_str_or_server};"
            f"Database={database};"
            f"Encrypt=yes;TrustServerCertificate=no;"
        )

    conn = pyodbc.connect(odbc_str, attrs_before={1256: token_struct})
    conn.autocommit = True  # DDL statements need autocommit
    return conn


# ---------------------------------------------------------------------------
# Migration logic
# ---------------------------------------------------------------------------


def ensure_tracking_table(conn: pyodbc.Connection) -> None:
    """Create the migration tracking table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute(TRACKING_TABLE_DDL)
    cursor.close()


def already_applied(conn: pyodbc.Connection, name: str) -> bool:
    """Check if a migration has already been applied."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM _migration_history WHERE migration_name = ?",
        [name],
    )
    row = cursor.fetchone()
    cursor.close()
    return row[0] > 0 if row else False


def record_migration(conn: pyodbc.Connection, name: str, checksum: str) -> None:
    """Record that a migration was applied."""
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO _migration_history (migration_name, checksum) VALUES (?, ?)",
        [name, checksum],
    )
    cursor.close()


def compute_checksum(sql: str) -> str:
    """Simple hash of the SQL content for change detection."""
    import hashlib

    return hashlib.sha256(sql.encode()).hexdigest()[:16]


def run_migration_file(conn: pyodbc.Connection, path: Path) -> bool:
    """Execute a single migration file against the database.

    Splits the file on ``GO`` batch separators and executes each batch.
    Handles ``BEGIN TRANSACTION`` / ``COMMIT`` by stripping them (we run
    each batch in autocommit mode since DDL in Azure SQL cannot be
    inside explicit transactions for some statements).

    Returns True if the migration was applied, False if skipped.
    """
    name = path.name
    if already_applied(conn, name):
        print(f"  SKIP {name} (already applied)")
        return False

    sql = path.read_text(encoding="utf-8")
    checksum = compute_checksum(sql)

    # Strip transaction wrappers — Azure SQL DDL runs better in autocommit
    sql = re.sub(r"(?i)\bBEGIN\s+TRANSACTION\b;?", "", sql)
    sql = re.sub(r"(?i)\bCOMMIT\s+TRANSACTION\b;?", "", sql)
    sql = re.sub(r"(?i)\bCOMMIT\b;?", "", sql)

    # Split on GO batch separator
    batches = re.split(r"(?m)^\s*GO\s*$", sql)
    if len(batches) == 1:
        # No GO separators — split on semicolons for individual statements
        batches = [b.strip() for b in sql.split(";") if b.strip()]

    cursor = conn.cursor()
    executed = 0
    for batch in batches:
        batch = batch.strip()
        if not batch or batch.upper().startswith("PRINT"):
            continue
        try:
            cursor.execute(batch)
            executed += 1
        except pyodbc.ProgrammingError as e:
            # Table/index already exists — skip gracefully
            err_msg = str(e)
            if "already an object named" in err_msg or "already exists" in err_msg:
                obj_match = re.search(r"named '([^']+)'", err_msg)
                obj_name = obj_match.group(1) if obj_match else "?"
                print(f"    INFO: {obj_name} already exists, skipping")
                continue
            raise
    cursor.close()

    record_migration(conn, name, checksum)
    print(f"  ✓ {name} ({executed} batches executed)")
    return True


def discover_migrations() -> list[Path]:
    """Return migration files in order."""
    if not MIGRATION_DIR.is_dir():
        return []
    return sorted(MIGRATION_DIR.glob("*.sql"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if not CONN_STRING_OR_SERVER:
        print("ERROR: OPENINSURE_SQL_CONNECTION_STRING is not set.")
        print("Set it in .env or as an environment variable.")
        sys.exit(1)

    print("=" * 60)
    print("  OpenInsure SQL Migration Runner")
    print("=" * 60)
    print(f"  Server:   {CONN_STRING_OR_SERVER[:50]}...")
    print(f"  Database: {DATABASE}")
    print()

    conn = connect(CONN_STRING_OR_SERVER, DATABASE)
    print("  Connected to Azure SQL ✓")

    ensure_tracking_table(conn)

    # Determine which migrations to run
    if len(sys.argv) > 1:
        # Run a specific file
        files = [Path(sys.argv[1])]
    else:
        # Run all pending
        files = discover_migrations()

    if not files:
        print("  No migration files found.")
        conn.close()
        return

    print(f"\n  Found {len(files)} migration file(s):")
    applied = 0
    skipped = 0
    for f in files:
        if not f.exists():
            print(f"  ERROR: {f} not found")
            continue
        if run_migration_file(conn, f):
            applied += 1
        else:
            skipped += 1

    print(f"\n  Done: {applied} applied, {skipped} skipped")
    conn.close()


if __name__ == "__main__":
    main()
