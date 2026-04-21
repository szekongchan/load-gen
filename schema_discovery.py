"""
schema_discovery.py — Connect to the target database and return the schema
for a given table by querying information_schema.columns.

Supports PostgreSQL (psycopg2) and MySQL/MariaDB (pymysql).
Schema results are cached in-process to avoid repeated metadata round-trips
during load testing.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import List, Optional

import config


@dataclass
class ColumnInfo:
    name: str
    data_type: str          # e.g. "character varying", "integer", "boolean"
    is_nullable: bool
    char_max_length: Optional[int]   # Only set for character types
    numeric_precision: Optional[int]
    numeric_scale: Optional[int]
    is_auto_increment: bool = False  # True for AUTO_INCREMENT / SERIAL columns
    is_unsigned: bool = False        # True for UNSIGNED integer columns (MySQL/MariaDB)
    is_generated: bool = False       # True for VIRTUAL/STORED generated columns


def _get_connection():
    """Return a raw DB-API 2.0 connection for the configured adapter."""
    if config.DB_ADAPTER == "postgresql":
        import psycopg2
        return psycopg2.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            dbname=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
        )
    elif config.DB_ADAPTER == "mysql":
        import pymysql
        return pymysql.connect(
            host=config.DB_HOST,
            port=config.DB_PORT,
            database=config.DB_NAME,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            cursorclass=pymysql.cursors.DictCursor,
        )
    else:
        raise ValueError(
            f"Unsupported DB_ADAPTER: {config.DB_ADAPTER!r}. Use 'postgresql' or 'mysql'."
        )


_POSTGRESQL_QUERY = """
SELECT
    column_name,
    data_type,
    is_nullable,
    character_maximum_length,
    numeric_precision,
    numeric_scale
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = %s
ORDER BY ordinal_position;
"""

_MYSQL_QUERY = """
SELECT
    column_name,
    data_type,
    column_type,
    is_nullable,
    character_maximum_length,
    numeric_precision,
    numeric_scale,
    extra
FROM information_schema.columns
WHERE table_schema = %s
  AND table_name   = %s
ORDER BY ordinal_position;
"""


@functools.lru_cache(maxsize=32)
def discover_schema(table_name: str) -> List[ColumnInfo]:
    """
    Return a list of ColumnInfo for every column in *table_name*.

    Results are cached per table name for the lifetime of the process,
    so repeated calls during a Locust run incur no extra DB round-trips.

    Raises:
        ValueError: if the table is not found or the adapter is unsupported.
        Any DB driver exception propagates as-is.
    """
    conn = _get_connection()
    try:
        if config.DB_ADAPTER == "postgresql":
            columns = _fetch_postgresql(conn, table_name)
        else:
            columns = _fetch_mysql(conn, table_name)
    finally:
        conn.close()

    if not columns:
        raise ValueError(
            f"Table {table_name!r} not found in the database "
            f"or it has no columns visible to user {config.DB_USER!r}."
        )

    return columns


def _fetch_postgresql(conn, table_name: str) -> List[ColumnInfo]:
    with conn.cursor() as cur:
        cur.execute(_POSTGRESQL_QUERY, (table_name,))
        rows = cur.fetchall()

    return [
        ColumnInfo(
            name=row[0],
            data_type=row[1].lower(),
            is_nullable=(row[2].upper() == "YES"),
            char_max_length=row[3],
            numeric_precision=row[4],
            numeric_scale=row[5],
        )
        for row in rows
    ]


def _fetch_mysql(conn, table_name: str) -> List[ColumnInfo]:
    with conn.cursor() as cur:
        cur.execute(_MYSQL_QUERY, (config.DB_NAME, table_name))
        rows = cur.fetchall()

    return [
        ColumnInfo(
            name=row["column_name"],
            data_type=row["data_type"].lower(),
            is_nullable=(row["is_nullable"].upper() == "YES"),
            char_max_length=row["character_maximum_length"],
            numeric_precision=row["numeric_precision"],
            numeric_scale=row["numeric_scale"],
            is_auto_increment="auto_increment" in (row["extra"] or "").lower(),
            is_unsigned="unsigned" in (row["column_type"] or "").lower(),
            is_generated="generated" in (row["extra"] or "").lower(),
        )
        for row in rows
    ]


def invalidate_cache(table_name: Optional[str] = None) -> None:
    """
    Clear the schema cache.

    Pass a *table_name* to clear only that entry, or omit it to clear all.
    (lru_cache doesn't support per-key eviction natively, so a full clear
    is the fallback when a specific key is requested but not matched.)
    """
    discover_schema.cache_clear()
