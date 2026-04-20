"""
sql_builder.py — Build parameterized SQL statements for INSERT and SELECT.

All statements use DB-API 2.0 placeholders (%s) so values are always passed
separately to the driver — never interpolated into the query string — which
prevents SQL injection by design.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import config


def build_insert(table: str, row: Dict[str, Any]) -> Tuple[str, List[Any]]:
    """
    Build a parameterized INSERT statement.

    Args:
        table:  Target table name.
        row:    {column_name: value} dict produced by data_generator.generate_row().

    Returns:
        (sql, params) where *sql* contains %s placeholders and *params* is the
        corresponding list of values in column order.

    Example (PostgreSQL)::

        sql, params = build_insert("orders", {"id": 1, "amount": 9.99})
        # sql    → 'INSERT INTO "orders" ("id", "amount") VALUES (%s, %s)'
        # params → [1, 9.99]
    """
    if not row:
        raise ValueError("Cannot build INSERT for an empty row dict.")

    quoted_table = _quote_identifier(table)
    columns = list(row.keys())
    quoted_columns = ", ".join(_quote_identifier(c) for c in columns)
    placeholders = ", ".join("%s" for _ in columns)
    params = [row[c] for c in columns]

    sql = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})"
    return sql, params


def build_select(
    table: str,
    where_column: str | None = None,
    where_value: Any = None,
    limit: int = 100,
) -> Tuple[str, List[Any]]:
    """
    Build a parameterized SELECT statement.

    Args:
        table:        Target table name.
        where_column: Optional column to filter on. If omitted, no WHERE clause
                      is added and the query scans up to *limit* rows.
        where_value:  Value for the WHERE predicate (required when *where_column*
                      is provided).
        limit:        Maximum number of rows to return (default 100).

    Returns:
        (sql, params) tuple.

    Examples::

        sql, params = build_select("orders")
        # → ('SELECT * FROM "orders" LIMIT %s', [100])

        sql, params = build_select("orders", "id", 42)
        # → ('SELECT * FROM "orders" WHERE "id" = %s LIMIT %s', [42, 100])
    """
    quoted_table = _quote_identifier(table)
    params: List[Any] = []

    if where_column is not None:
        quoted_col = _quote_identifier(where_column)
        where_clause = f" WHERE {quoted_col} = %s"
        params.append(where_value)
    else:
        where_clause = ""

    params.append(limit)
    sql = f"SELECT * FROM {quoted_table}{where_clause} LIMIT %s"
    return sql, params


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _quote_identifier(name: str) -> str:
    """
    Wrap an identifier in the appropriate quote character for the adapter.

    PostgreSQL uses double-quotes; MySQL uses backticks.
    The identifier is sanitized to contain only alphanumerics and underscores
    to prevent any injection via table/column names.
    """
    sanitized = _sanitize_identifier(name)
    if config.DB_ADAPTER == "mysql":
        return f"`{sanitized}`"
    return f'"{sanitized}"'


def _sanitize_identifier(name: str) -> str:
    """
    Reject identifiers that contain characters outside [A-Za-z0-9_].

    Raises:
        ValueError: if *name* contains disallowed characters.
    """
    import re
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(
            f"Unsafe identifier {name!r}: only letters, digits, and underscores are allowed."
        )
    return name
