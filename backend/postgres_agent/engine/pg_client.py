"""
PostgreSQL Client with connection pooling and async support.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple
import asyncpg
from asyncpg.pool import Pool
import logging

logger = logging.getLogger(__name__)


class PGClient:
    """PostgreSQL client with connection pool management."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "postgres",
        user: str = "postgres",
        password: str = "",
        min_connections: int = 2,
        max_connections: int = 10,
        ssl: Optional[str] = None
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.ssl = ssl
        self._pool: Optional[Pool] = None

    @property
    def dsn(self) -> str:
        """Generate connection DSN."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    async def connect(self) -> None:
        """Initialize connection pool."""
        if self._pool is not None:
            return

        try:
            self._pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=60,
                ssl=self.ssl
            )
            logger.info(f"Connection pool created for {self.database}@{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("Connection pool closed")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        if self._pool is None:
            await self.connect()

        async with self._pool.acquire() as connection:
            yield connection

    async def execute(self, query: str, *args, timeout: float = None) -> str:
        """Execute a query without returning results."""
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)

    async def fetch(self, query: str, *args, timeout: float = None) -> List[asyncpg.Record]:
        """Execute a query and fetch all results."""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)

    async def fetchrow(self, query: str, *args, timeout: float = None) -> Optional[asyncpg.Record]:
        """Execute a query and fetch a single row."""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)

    async def fetchval(self, query: str, *args, column: int = 0, timeout: float = None) -> Any:
        """Execute a query and fetch a single value."""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, column=column, timeout=timeout)

    async def fetch_as_dict(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute a query and return results as list of dictionaries."""
        records = await self.fetch(query, *args)
        return [dict(record) for record in records]

    async def test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            result = await self.fetchval("SELECT 1")
            return result == 1
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    async def get_version(self) -> str:
        """Get PostgreSQL version."""
        return await self.fetchval("SELECT version()")

    async def get_database_size(self) -> int:
        """Get database size in bytes."""
        return await self.fetchval(
            "SELECT pg_database_size(current_database())"
        )

    async def get_current_database(self) -> str:
        """Get current database name."""
        return await self.fetchval("SELECT current_database()")

    async def get_current_user(self) -> str:
        """Get current user."""
        return await self.fetchval("SELECT current_user")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Global connection pool factory
_global_pool: Optional[PGClient] = None


async def get_connection_pool(
    host: str = "localhost",
    port: int = 5432,
    database: str = "postgres",
    user: str = "postgres",
    password: str = "",
    **kwargs
) -> PGClient:
    """Get or create a global connection pool."""
    global _global_pool

    if _global_pool is None:
        _global_pool = PGClient(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            **kwargs
        )
        await _global_pool.connect()

    return _global_pool


async def close_global_pool() -> None:
    """Close the global connection pool."""
    global _global_pool

    if _global_pool is not None:
        await _global_pool.disconnect()
        _global_pool = None
