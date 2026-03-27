"""Azure SQL Database adapter with connection pooling and async wrappers.

Uses ``DefaultAzureCredential`` for passwordless AAD authentication and
``pyodbc`` for the underlying ODBC connection. All blocking I/O is
offloaded to a thread-pool executor so the adapter is safe to call from
an ``asyncio`` event loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import functools
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import pyodbc
import structlog
from azure.identity import DefaultAzureCredential
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

logger = structlog.get_logger()

# Azure AD resource identifier for Azure SQL
_SQL_RESOURCE = "https://database.windows.net/.default"

_TRANSIENT_SQLSTATES = {"08S01", "08001", "40001", "40P01", "HYT00", "HY008"}


def _is_transient(exc: BaseException) -> bool:
    """Check if a pyodbc error is transient and worth retrying."""
    if isinstance(exc, pyodbc.Error):
        sqlstate = getattr(exc, "args", [None, None])[0] if exc.args else None
        if sqlstate and str(sqlstate) in _TRANSIENT_SQLSTATES:
            return True
        msg = str(exc).lower()
        return any(kw in msg for kw in ("timeout", "connection", "deadlock", "login failed"))
    return False


def _detect_odbc_driver() -> str:
    """Return the best available SQL Server ODBC driver."""
    drivers = pyodbc.drivers()
    for preferred in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server"):
        if preferred in drivers:
            return preferred
    return "ODBC Driver 18 for SQL Server"


class TransactionContext:
    """Provides query execution methods within a single database transaction.

    Both synchronous (for use inside an executor thread) and asynchronous
    wrappers are provided.  The async variants offload work to the supplied
    ``executor`` so they are safe to ``await`` from the event loop.
    """

    def __init__(self, conn: pyodbc.Connection, executor: ThreadPoolExecutor) -> None:
        self._conn = conn
        self._executor = executor

    # -- synchronous helpers (called inside executor thread) -----------------

    def execute_query(self, query: str, params: Sequence[Any] | None = None) -> int:
        """Execute a write query within the transaction. Synchronous — called inside executor."""
        cursor = self._conn.cursor()
        cursor.execute(query, params or [])
        return cursor.rowcount

    def fetch_one(self, query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        """Fetch a single row within the transaction. Synchronous."""
        cursor = self._conn.cursor()
        cursor.execute(query, params or [])
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row, strict=False))

    def fetch_all(self, query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all rows within the transaction. Synchronous."""
        cursor = self._conn.cursor()
        cursor.execute(query, params or [])
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    # -- async wrappers (safe to call from the event loop) -------------------

    async def async_execute_query(self, query: str, params: Sequence[Any] | None = None) -> int:
        """Execute a write query within the transaction. Async-safe."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.execute_query, query, params)

    async def async_fetch_one(self, query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        """Fetch a single row within the transaction. Async-safe."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.fetch_one, query, params)

    async def async_fetch_all(self, query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all rows within the transaction. Async-safe."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.fetch_all, query, params)


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
        self._pool: queue.Queue[pyodbc.Connection] = queue.Queue(maxsize=pool_size)
        self._cached_token: str | None = None
        self._token_expires_at: float = 0.0
        self._token_lock = threading.Lock()

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
        """Get an AAD access token, using a cached value if still valid."""
        with self._token_lock:
            now = time.monotonic()
            # Refresh if token expires within 5 minutes
            if self._cached_token and now < self._token_expires_at - 300:
                return self._cached_token

            token_response = self._credential.get_token(_SQL_RESOURCE)
            self._cached_token = token_response.token
            # Azure tokens typically expire in 1 hour; use 55 minutes
            self._token_expires_at = now + 3300
            logger.debug("database.token_refreshed")
            return self._cached_token

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

    def _acquire(self) -> pyodbc.Connection:
        """Get a connection from the pool, creating one if needed."""
        try:
            conn = self._pool.get_nowait()
            try:
                conn.execute("SELECT 1")
                return conn
            except Exception:
                with contextlib.suppress(Exception):
                    conn.close()
        except queue.Empty:
            pass
        return self._connect()

    def _release(self, conn: pyodbc.Connection) -> None:
        """Return a connection to the pool."""
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            conn.close()

    async def _run_with_retry(self, fn, *args: Any, **kwargs: Any) -> Any:
        """Run a function in the executor with retry for transient errors."""

        @retry(
            retry=retry_if_exception(_is_transient),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=5),
            reraise=True,
        )
        def _retryable():
            return fn(*args, **kwargs)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, _retryable)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_query(self, query: str, params: Sequence[Any] | None = None) -> int:
        """Execute a write query (INSERT / UPDATE / DELETE).

        Returns the number of rows affected.
        """

        def _execute(q: str, p: Sequence[Any] | None) -> int:
            conn = self._acquire()
            try:
                cursor = conn.cursor()
                cursor.execute(q, p or [])
                rowcount = cursor.rowcount
                conn.commit()
                self._release(conn)
                return rowcount
            except Exception:
                conn.rollback()
                with contextlib.suppress(Exception):
                    conn.close()
                raise

        rowcount: int = await self._run_with_retry(_execute, query, params)
        logger.debug("database.execute_query", rows_affected=rowcount)
        return rowcount

    async def fetch_one(self, query: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
        """Fetch a single row as a dictionary, or ``None``."""

        def _fetch(q: str, p: Sequence[Any] | None) -> dict[str, Any] | None:
            conn = self._acquire()
            try:
                cursor = conn.cursor()
                cursor.execute(q, p or [])
                row = cursor.fetchone()
                if row is None:
                    self._release(conn)
                    return None
                columns = [desc[0] for desc in cursor.description]
                self._release(conn)
                return dict(zip(columns, row, strict=False))
            except Exception:
                with contextlib.suppress(Exception):
                    conn.close()
                raise

        return await self._run_with_retry(_fetch, query, params)

    async def fetch_all(self, query: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all rows as a list of dictionaries."""

        def _fetch(q: str, p: Sequence[Any] | None) -> list[dict[str, Any]]:
            conn = self._acquire()
            try:
                cursor = conn.cursor()
                cursor.execute(q, p or [])
                columns = [desc[0] for desc in cursor.description]
                result = [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
                self._release(conn)
                return result
            except Exception:
                with contextlib.suppress(Exception):
                    conn.close()
                raise

        return await self._run_with_retry(_fetch, query, params)

    async def execute_many(
        self,
        query: str,
        params_list: Sequence[Sequence[Any]],
    ) -> int:
        """Execute a parameterized query for each set of params in a batch.

        Returns total rows affected.
        """

        def _exec_many(q: str, pl: Sequence[Sequence[Any]]) -> int:
            conn = self._acquire()
            try:
                cursor = conn.cursor()
                cursor.fast_executemany = True
                cursor.executemany(q, pl)
                rowcount = cursor.rowcount
                conn.commit()
                self._release(conn)
                return rowcount
            except Exception:
                conn.rollback()
                with contextlib.suppress(Exception):
                    conn.close()
                raise

        rowcount: int = await self._run_with_retry(_exec_many, query, params_list)
        logger.debug("database.execute_many", rows_affected=rowcount)
        return rowcount

    async def health_check(self) -> dict[str, Any]:
        """Verify connectivity and return basic server info."""

        def _check() -> dict[str, Any]:
            conn = self._acquire()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT @@VERSION AS version, GETUTCDATE() AS server_time")
                row = cursor.fetchone()
                self._release(conn)
                return {
                    "status": "healthy",
                    "server": getattr(self, "_server", "unknown"),
                    "database": getattr(self, "_database", "unknown"),
                    "version": row[0] if row else "unknown",
                    "server_time": str(row[1]) if row else "unknown",
                }
            except Exception as exc:
                with contextlib.suppress(Exception):
                    conn.close()
                return {
                    "status": "unhealthy",
                    "server": getattr(self, "_server", "unknown"),
                    "database": getattr(self, "_database", "unknown"),
                    "error": str(exc),
                }

        return await self._run_in_executor(_check)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[TransactionContext]:
        """Async context manager that wraps multiple operations in a single transaction.

        Usage::

            async with db.transaction() as txn:
                txn.execute_query("INSERT INTO ...", [...])
                txn.execute_query("UPDATE ...", [...])
            # auto-commits on exit; rolls back on exception
        """

        def _begin() -> tuple[pyodbc.Connection, TransactionContext]:
            conn = self._acquire()
            return conn, TransactionContext(conn, self._executor)

        conn, txn = await self._run_in_executor(_begin)

        try:
            yield txn
            await self._run_in_executor(conn.commit)
            logger.debug("database.transaction.committed")
        except Exception:
            await self._run_in_executor(conn.rollback)
            logger.warning("database.transaction.rolled_back", exc_info=True)
            raise
        finally:
            await self._run_in_executor(conn.close)

    async def close(self) -> None:
        """Shut down connection pool and thread-pool executor."""
        while not self._pool.empty():
            with contextlib.suppress(Exception):
                conn = self._pool.get_nowait()
                conn.close()
        self._executor.shutdown(wait=False)
        logger.info("database.closed", server=getattr(self, "_server", "unknown"))
