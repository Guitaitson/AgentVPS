"""
Connection pooling with asyncpg for PostgreSQL.

Provides efficient async database connection management optimized
for the VPS environment with limited resources (2.4 GB RAM).
"""

import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import asyncpg
import structlog

logger = structlog.get_logger(__name__)

# Global pool instance
_pool: Optional[asyncpg.Pool] = None


class DatabasePool:
    """
    Async database connection pool manager.

    Configured for VPS environment with limited resources.
    Default pool size: 5-10 connections (low memory footprint).
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 5432,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
        min_size: int = 2,
        max_size: int = 10,
        command_timeout: float = 60.0,
    ):
        """
        Initialize database pool configuration.

        Args:
            dsn: Full PostgreSQL DSN string (optional)
            host: Database host
            port: Database port
            user: Database user
            password: Database password
            database: Database name
            min_size: Minimum pool connections
            max_size: Maximum pool connections (VPS safe: max 10)
            command_timeout: Query timeout in seconds
        """
        self.dsn = dsn or self._build_dsn(host, port, user, password, database)
        self.min_size = min_size
        self.max_size = max_size
        self.command_timeout = command_timeout
        self._pool: Optional[asyncpg.Pool] = None

    def _build_dsn(
        self,
        host: Optional[str],
        port: int,
        user: Optional[str],
        password: Optional[str],
        database: Optional[str],
    ) -> str:
        """Build DSN from individual parameters."""
        host = host or os.getenv("POSTGRES_HOST", "localhost")
        user = user or os.getenv("POSTGRES_USER", "postgres")
        password = password or os.getenv("POSTGRES_PASSWORD", "")
        database = database or os.getenv("POSTGRES_DB", "vps_agent")

        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    async def initialize(self) -> asyncpg.Pool:
        """Initialize the connection pool."""
        if self._pool is not None:
            return self._pool

        try:
            self._pool = await asyncpg.create_pool(
                self.dsn,
                min_size=self.min_size,
                max_size=self.max_size,
                command_timeout=self.command_timeout,
                init=self._init_connection,
            )

            logger.info(
                "database_pool.initialized",
                min_size=self.min_size,
                max_size=self.max_size,
            )

            return self._pool

        except asyncpg.PostgresError as e:
            logger.error("database_pool.init_failed", error=str(e))
            raise

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize connection with custom settings."""
        # Set application name for monitoring
        await conn.execute("SET application_name = 'vps_agent'")

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("database_pool.closed")

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.

        Usage:
            async with pool.acquire() as conn:
                result = await conn.fetch("SELECT * FROM table")
        """
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as connection:
            yield connection

    async def fetch(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> List[asyncpg.Record]:
        """
        Execute a SELECT query and return all results.

        Args:
            query: SQL query string
            *args: Query parameters
            timeout: Query timeout

        Returns:
            List of records
        """
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchrow(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> Optional[asyncpg.Record]:
        """
        Execute a SELECT query and return first result.

        Args:
            query: SQL query string
            *args: Query parameters
            timeout: Query timeout

        Returns:
            Single record or None
        """
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    async def fetchval(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> Any:
        """
        Execute a SELECT query and return single value.

        Args:
            query: SQL query string
            *args: Query parameters
            timeout: Query timeout

        Returns:
            Single value or None
        """
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, timeout=timeout)

    async def execute(
        self, query: str, *args, timeout: Optional[float] = None
    ) -> str:
        """
        Execute a query (INSERT, UPDATE, DELETE).

        Args:
            query: SQL query string
            *args: Query parameters
            timeout: Query timeout

        Returns:
            Command completion status
        """
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def executemany(
        self, query: str, args: List[tuple], timeout: Optional[float] = None
    ) -> str:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL query string
            args: List of parameter tuples
            timeout: Query timeout

        Returns:
            Command completion status
        """
        async with self.acquire() as conn:
            return await conn.executemany(query, args, timeout=timeout)

    async def transaction(self):
        """
        Start a database transaction.

        Usage:
            async with pool.transaction() as conn:
                await conn.execute("INSERT ...")
                await conn.execute("UPDATE ...")
        """
        return self._pool.transaction()

    @property
    def is_initialized(self) -> bool:
        """Check if pool is initialized."""
        return self._pool is not None

    @property
    def size(self) -> int:
        """Current pool size."""
        return self._pool.get_size() if self._pool else 0

    @property
    def free_size(self) -> int:
        """Number of free connections in pool."""
        return self._pool.get_free_size() if self._pool else 0


# Global pool instance for singleton pattern
_db_pool: Optional[DatabasePool] = None


async def init_db_pool(
    dsn: Optional[str] = None,
    min_size: int = 2,
    max_size: int = 10,
) -> DatabasePool:
    """
    Initialize global database pool.

    Args:
        dsn: Database DSN (optional, uses env vars if not provided)
        min_size: Minimum pool size
        max_size: Maximum pool size

    Returns:
        DatabasePool instance
    """
    global _db_pool

    if _db_pool is None:
        _db_pool = DatabasePool(dsn=dsn, min_size=min_size, max_size=max_size)
        await _db_pool.initialize()

    return _db_pool


async def close_db_pool() -> None:
    """Close global database pool."""
    global _db_pool

    if _db_pool:
        await _db_pool.close()
        _db_pool = None


def get_db_pool() -> DatabasePool:
    """
    Get global database pool instance.

    Raises:
        RuntimeError: If pool is not initialized

    Returns:
        DatabasePool instance
    """
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db_pool() first.")

    return _db_pool


async def health_check() -> Dict[str, Any]:
    """
    Perform database health check.

    Returns:
        Health status dictionary
    """
    try:
        pool = get_db_pool()

        async with pool.acquire() as conn:
            result = await conn.fetchrow("SELECT version(), now() as current_time")

            return {
                "status": "healthy",
                "version": result["version"],
                "current_time": result["current_time"].isoformat(),
                "pool_size": pool.size,
                "pool_free": pool.free_size,
            }

    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }