"""Postgres connection pool (psycopg 3).

One pool for the process. Every query is parameterised with %s placeholders —
never f-strings or concatenation, so there is no injection surface.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator, Sequence

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings

pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=10,
    timeout=10,
    open=False,
    kwargs={"row_factory": dict_row},
)


def open_pool() -> None:
    """Called on app startup."""
    pool.open()
    pool.wait(timeout=15)


def close_pool() -> None:
    """Called on app shutdown."""
    pool.close()


@contextmanager
def connection() -> Iterator[Any]:
    """A connection from the pool. Commits on success, rolls back on error."""
    with pool.connection() as conn:
        yield conn


def fetch_all(sql: str, params: Sequence[Any] = ()) -> list[dict]:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def fetch_one(sql: str, params: Sequence[Any] = ()) -> dict | None:
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def execute(sql: str, params: Sequence[Any] = ()) -> int:
    """Run a statement. Returns the number of rows affected."""
    with pool.connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount
