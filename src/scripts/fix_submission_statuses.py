"""Fix submission statuses to match realistic distribution.

One-time migration: updates all submissions (currently stuck at 'received')
to a realistic status distribution matching what the seed script intended.

Uses go-sqlcmd with Azure AD Default authentication to connect directly
to Azure SQL.

Usage:
    python src/scripts/fix_submission_statuses.py
"""

from __future__ import annotations

import random
import subprocess
import sys
import tempfile
from pathlib import Path

random.seed(42)

SERVER = "openinsure-dev-sql-knshtzbusr734.database.windows.net"
DATABASE = "openinsure-db"
SQLCMD = r"C:\Program Files\SqlCmd\sqlcmd.exe"

STATUSES = ["bound", "declined", "quoted", "underwriting", "triaging", "received"]
WEIGHTS = [0.35, 0.20, 0.15, 0.10, 0.10, 0.10]


def run_sql(query: str) -> str:
    """Execute SQL via go-sqlcmd and return the output."""
    result = subprocess.run(
        [
            SQLCMD,
            "-S", SERVER,
            "-d", DATABASE,
            "--authentication-method=ActiveDirectoryDefault",
            "-Q", query,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return result.stdout


def run_sql_file(path: str) -> str:
    """Execute a .sql file via go-sqlcmd and return the output."""
    result = subprocess.run(
        [
            SQLCMD,
            "-S", SERVER,
            "-d", DATABASE,
            "--authentication-method=ActiveDirectoryDefault",
            "-i", path,
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        raise SystemExit(1)
    return result.stdout


def main() -> None:
    # -- Current state ------------------------------------------------------
    print("Current status distribution:")
    output = run_sql(
        "SELECT status, COUNT(*) as cnt FROM submissions GROUP BY status ORDER BY status"
    )
    print(output)

    # -- Get all submission IDs ---------------------------------------------
    output = run_sql("SELECT id FROM submissions ORDER BY created_at")
    ids = [
        line.strip()
        for line in output.strip().splitlines()
        if line.strip()
        and not line.startswith("-")
        and "id" not in line.lower()
        and "rows affected" not in line.lower()
    ]
    total = len(ids)
    print(f"Total submissions: {total}")

    if total == 0:
        print("No submissions found — nothing to do.")
        return

    # -- Build target distribution ------------------------------------------
    random.shuffle(ids)

    counts = [int(total * w) for w in WEIGHTS]
    counts[-1] = total - sum(counts[:-1])  # remainder goes to 'received'

    print(f"\nTarget distribution ({total} total):")
    for status, count in zip(STATUSES, counts):
        print(f"  {status:15s}: {count}")

    # -- Generate SQL UPDATE batch ------------------------------------------
    assignments: list[tuple[str, str]] = []
    offset = 0
    for status, count in zip(STATUSES, counts):
        for i in range(count):
            assignments.append((ids[offset + i], status))
        offset += count

    # Write a batch SQL file to update all records
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sql", delete=False, encoding="utf-8"
    ) as f:
        sql_path = f.name
        f.write("SET NOCOUNT ON;\n")
        f.write("BEGIN TRANSACTION;\n")
        for sid, status in assignments:
            if status == "received":
                continue  # already 'received', skip
            escaped_id = sid.replace("'", "''")
            f.write(
                f"UPDATE submissions SET status = '{status}' WHERE id = '{escaped_id}';\n"
            )
        f.write("COMMIT;\n")
        f.write("SET NOCOUNT OFF;\n")

    updates_count = len([a for a in assignments if a[1] != "received"])
    print(f"\nExecuting {updates_count} UPDATE statements...")
    output = run_sql_file(sql_path)
    print(output if output.strip() else "  (no output — updates applied)")

    # Clean up temp file
    Path(sql_path).unlink(missing_ok=True)

    # -- Verify -------------------------------------------------------------
    print("\nFinal status distribution:")
    output = run_sql(
        "SELECT status, COUNT(*) as cnt FROM submissions GROUP BY status ORDER BY status"
    )
    print(output)
    print("Done.")


if __name__ == "__main__":
    main()
