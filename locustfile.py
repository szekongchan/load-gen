"""
locustfile.py — Locust entry point for SQL INSERT / SELECT load testing.

Run (headless example):
    locust -f locustfile.py --headless -u 10 -r 2 -t 60s

All connection and load settings are read from config.py / environment variables.
"""

from __future__ import annotations

import time
from typing import Optional

from locust import User, between, events, task

import config
from data_generator import generate_row
from schema_discovery import discover_schema
from sql_builder import build_insert, build_select


# ---------------------------------------------------------------------------
# DB connection helper (one connection per Locust User)
# ---------------------------------------------------------------------------

def _open_connection():
    """Open and return a raw DB-API 2.0 connection for the configured adapter."""
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
            autocommit=True,
        )
    else:
        raise ValueError(f"Unsupported DB_ADAPTER: {config.DB_ADAPTER!r}")


# ---------------------------------------------------------------------------
# Locust User
# ---------------------------------------------------------------------------

class SQLUser(User):
    """
    A Locust User that executes parameterized INSERT and SELECT statements
    against the configured database table.

    Each user instance maintains its own DB connection for isolation.
    """

    # Think-time between tasks: 0.5 – 2 seconds
    wait_time = between(0.5, 2)

    def on_start(self) -> None:
        """Called once per User when it starts. Discovers schema and opens connection."""
        self._conn = _open_connection()
        self._schema = discover_schema(config.TARGET_TABLE)

    def on_stop(self) -> None:
        """Called once per User when it stops. Closes the DB connection."""
        try:
            self._conn.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @task(config.INSERT_WEIGHT)
    def insert_row(self) -> None:
        """Generate a random row and INSERT it into the target table."""
        row = generate_row(self._schema)
        sql, params = build_insert(config.TARGET_TABLE, row)
        self._execute(sql, params, name=f"INSERT {config.TARGET_TABLE}")

    @task(config.QUERY_WEIGHT)
    def query_row(self) -> None:
        """SELECT a sample of rows from the target table."""
        sql, params = build_select(config.TARGET_TABLE, limit=100)
        self._execute(sql, params, name=f"SELECT {config.TARGET_TABLE}")

    # ------------------------------------------------------------------
    # Internal execution helper
    # ------------------------------------------------------------------

    def _execute(self, sql: str, params: list, name: str) -> None:
        """
        Execute *sql* with *params*, measure elapsed time, and fire the
        appropriate Locust request event so results appear in the report.
        """
        start = time.perf_counter()
        exception: Optional[Exception] = None
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                # Commit for INSERT/UPDATE/DELETE; harmless for SELECT
                self._conn.commit()
        except Exception as exc:
            exception = exc
            # Attempt to recover the connection for the next task
            try:
                self._conn.rollback()
            except Exception:
                pass
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1_000
            events.request.fire(
                request_type="SQL",
                name=name,
                response_time=elapsed_ms,
                response_length=0,
                exception=exception,
                context={},
            )
            if exception:
                raise exception
