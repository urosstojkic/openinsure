"""Azure SQL Database adapter with connection pooling and async wrappers.

Uses ``DefaultAzureCredential`` for passwordless AAD authentication and
``pyodbc`` for the underlying ODBC connection. All blocking I/O is
offloaded to a thread-pool executor so the adapter is safe to call from
an ``asyncio`` event loop.
"""

from __future__ import annotations

import asyncio
import functools
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

import pyodbc
import structlog
from azure.identity import DefaultAzureCredential

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = structlog.get_logger()

# Azure AD resource identifier for Azure SQL
_SQL_RESOURCE = "https://database.windows.net/.default"


def _detect_odbc_driver() -> str:
    """Return the best available SQL Server ODBC driver."""
    drivers = pyodbc.drivers()
    for preferred in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if preferred in drivers:
            return preferred
    return "ODBC Driver 18 for SQL Server"


class DatabaseAdapter:
    """Async-friendly wrapper around ``pyodbc`` for Azure SQL.

    Parameters
    ----------
    connection_string_or_server:
        Either a full ODBC connection string (if it contains "Driver=")
        or a server hostname (e.g. ``myserver.database.windows.net``).
    database:
        Target database name (ignored when a full connection string is provided).
    credential:
        An Azure credential instance.  Defaults to ``DefaultAzureCredential``.
    pool_size:
        Maximum number of connections kept in the thread-pool.
    """

    def __init__(
        self,
        connection_string_or_server: str,
        database: str = "",
        *,
        credential: DefaultAzureCredential | None = None,
        pool_size: int = 5,
    ) -> None:
        self._credential = credential or DefaultAzureCredential()
        self._pool_size = pool_size
        self._executor = ThreadPoolExecutor(max_workers=pool_size)

        # Detect if this is a full ODBC connection string or just a server name
        if "Driver=" in connection_string_or_server or "driver=" in connection_string_or_server:
            # Full connection string — strip any Authentication= clause (we use token auth)
            cs = connection_string_or_server
            import re

            cs = re.sub(r"Authentication=[^;]*;?", "", cs)
            # Replace driver with best available on this system
            driver = _detect_odbc_driver()
            cs = re.sub(r"Driver=\{[^}]+\}", f"Driver={{{driver}}}", cs)
            self._connection_string = cs
        else:
            self._server = connection_string_or_server
            self._database = database
            driver = _detect_odbc_driver()
            self._connection_string = (
                f"Driver={{{driver}}};"
                f"Server={connection_string_or_server};"
                f"Database={database};"
                f"Encrypt=yes;TrustServerCertificate=no;"
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        token = self._credential.get_token(_SQL_RESOURCE)
        return token.token

    def _connect(self) -> pyodbc.Connection:
        """Create a new connection using AAD access-token authentication.

        The access token must be passed as a UTF-16-LE encoded byte string
        via the SQL_COPT_SS_ACCESS_TOKEN (1256) connection attribute.
        """
        import struct

        token = self._get_access_token()

        # pyodbc requires the token as bytes in a specific format:
        # UTF-16-LE encoded string preceded by its length as a 4-byte little-endian int
        token_bytes = token.encode("UTF-16-LE")
        token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)

        conn = pyodbc.connect(
            self._connection_string,
            attrs_before={
                1256: token_struct,  # SQL_COPT_SS_ACCESS_TOKEN
            },
        )
        conn.autocommit = False
        return conn

    async def _run_in_executor(self, fn, *args: Any, **kwargs: Any) -> Any:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, functools.partial(fn, *args, **kwargs))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_query(self, query: str, params: Sequence[Any] | None = None) -> int:
        """Execute a write query (INSERT / UPDATE / DELETE).

        Returns the number of rows affected.
        """

        def _execute(q: str, p: Sequence[Any] | None) -> int:
            conn = self._connect()
            try:
                cursor = conn.cursor()
                cursor.execute(q, p or [])
                rowcount = cursor.rowcount
                conn.commit()
                return rowcount
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        rowcount: int = await self._run_in_executor(_execute, query, params)
        logger.debug("database.execute_query", rows_affected=rowcount)
        return rowcount

    async def fetch_one(self, query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        """Fetch a single row as a dictionary, or ``None``."""

        def _fetch(q: str, p: Sequence[Any] | None) -> dict[str, Any] | None:
            conn = self._connect()
            try:
                cursor = conn.cursor()
                cursor.execute(q, p or [])
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row, strict=False))
            finally:
                conn.close()

        return await self._run_in_executor(_fetch, query, params)

    async def fetch_all(self, query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all rows as a list of dictionaries."""

        def _fetch(q: str, p: Sequence[Any] | None) -> list[dict[str, Any]]:
            conn = self._connect()
            try:
                cursor = conn.cursor()
                cursor.execute(q, p or [])
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
            finally:
                conn.close()

        return await self._run_in_executor(_fetch, query, params)

    async def execute_many(
        self,
        query: str,
        params_list: Sequence[Sequence[Any]],
    ) -> int:
        """Execute a parameterized query for each set of params in a batch.

        Returns total rows affected.
        """

        def _exec_many(q: str, pl: Sequence[Sequence[Any]]) -> int:
            conn = self._connect()
            try:
                cursor = conn.cursor()
                cursor.fast_executemany = True
                cursor.executemany(q, pl)
                rowcount = cursor.rowcount
                conn.commit()
                return rowcount
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

        rowcount: int = await self._run_in_executor(_exec_many, query, params_list)
        logger.debug("database.execute_many", rows_affected=rowcount)
        return rowcount

    async def health_check(self) -> dict[str, Any]:
        """Verify connectivity and return basic server info."""

        def _check() -> dict[str, Any]:
            conn = self._connect()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT @@VERSION AS version, GETUTCDATE() AS server_time")
                row = cursor.fetchone()
                return {
                    "status": "healthy",
                    "server": self._server,
                    "database": self._database,
                    "version": row[0] if row else "unknown",
                    "server_time": str(row[1]) if row else "unknown",
                }
            except Exception as exc:
                return {
                    "status": "unhealthy",
                    "server": self._server,
                    "database": self._database,
                    "error": str(exc),
                }
            finally:
                conn.close()

        return await self._run_in_executor(_check)

    async def close(self) -> None:
        """Shut down the thread-pool executor."""
        self._executor.shutdown(wait=False)
        logger.info("database.closed", server=self._server)
