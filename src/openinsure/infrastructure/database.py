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


class DatabaseAdapter:
    """Async-friendly wrapper around ``pyodbc`` for Azure SQL.

    Parameters
    ----------
    server:
        Fully-qualified server name, e.g. ``myserver.database.windows.net``.
    database:
        Target database name.
    credential:
        An Azure credential instance.  Defaults to ``DefaultAzureCredential``.
    pool_size:
        Maximum number of connections kept in the thread-pool.
    """

    def __init__(
        self,
        server: str,
        database: str,
        *,
        credential: DefaultAzureCredential | None = None,
        pool_size: int = 5,
    ) -> None:
        self._server = server
        self._database = database
        self._credential = credential or DefaultAzureCredential()
        self._pool_size = pool_size
        self._executor = ThreadPoolExecutor(max_workers=pool_size)
        self._connection_string = f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={server};DATABASE={database};"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_access_token(self) -> str:
        token = self._credential.get_token(_SQL_RESOURCE)
        return token.token

    def _connect(self) -> pyodbc.Connection:
        """Create a new connection using AAD access-token authentication."""
        token = self._get_access_token()
        conn = pyodbc.connect(
            self._connection_string,
            attrs_before={
                # SQL_COPT_SS_ACCESS_TOKEN — pyodbc constant for token auth
                1256: token,
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
