"""
tests/test_schema_discovery.py — Unit tests for schema_discovery.py.

Uses unittest.mock to patch the DB connection so no real database is needed.
"""

import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Config stub
# ---------------------------------------------------------------------------

def _make_config(adapter: str = "postgresql") -> types.ModuleType:
    mod = types.ModuleType("config")
    mod.DB_ADAPTER = adapter
    mod.DB_HOST = "localhost"
    mod.DB_PORT = 5432
    mod.DB_NAME = "testdb"
    mod.DB_USER = "user"
    mod.DB_PASSWORD = "pass"
    return mod


def _load_sd(adapter: str = "postgresql"):
    sys.modules["config"] = _make_config(adapter)
    if "schema_discovery" in sys.modules:
        importlib.reload(sys.modules["schema_discovery"])
    import schema_discovery as sd
    sd.discover_schema.cache_clear()  # reset lru_cache between tests
    return sd


# ---------------------------------------------------------------------------
# PostgreSQL fetch
# ---------------------------------------------------------------------------

# Rows returned by the mock cursor (matches the SELECT column order)
_PG_ROWS = [
    ("id",    "integer",           "NO",  None, 10, 0),
    ("name",  "character varying", "YES", 100,  None, None),
    ("score", "numeric",           "NO",  None, 8,   2),
    ("active","boolean",           "NO",  None, None, None),
]


class TestDiscoverSchemaPostgres(unittest.TestCase):

    def setUp(self):
        self.sd = _load_sd("postgresql")

    def tearDown(self):
        sys.modules.pop("config", None)

    def _mock_conn(self, rows):
        cursor = MagicMock()
        cursor.__enter__ = lambda s: s
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchall.return_value = rows
        conn = MagicMock()
        conn.cursor.return_value = cursor
        return conn

    @patch("schema_discovery._get_connection")
    def test_returns_correct_column_count(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_PG_ROWS)
        cols = self.sd.discover_schema("orders")
        self.assertEqual(len(cols), 4)

    @patch("schema_discovery._get_connection")
    def test_column_names(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_PG_ROWS)
        cols = self.sd.discover_schema("orders")
        self.assertEqual([c.name for c in cols], ["id", "name", "score", "active"])

    @patch("schema_discovery._get_connection")
    def test_data_types_lowercased(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_PG_ROWS)
        cols = self.sd.discover_schema("orders")
        for col in cols:
            self.assertEqual(col.data_type, col.data_type.lower())

    @patch("schema_discovery._get_connection")
    def test_nullable_parsed_correctly(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_PG_ROWS)
        cols = self.sd.discover_schema("orders")
        nullable_map = {c.name: c.is_nullable for c in cols}
        self.assertFalse(nullable_map["id"])
        self.assertTrue(nullable_map["name"])

    @patch("schema_discovery._get_connection")
    def test_char_max_length(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_PG_ROWS)
        cols = self.sd.discover_schema("orders")
        name_col = next(c for c in cols if c.name == "name")
        self.assertEqual(name_col.char_max_length, 100)

    @patch("schema_discovery._get_connection")
    def test_numeric_precision_and_scale(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_PG_ROWS)
        cols = self.sd.discover_schema("orders")
        score_col = next(c for c in cols if c.name == "score")
        self.assertEqual(score_col.numeric_precision, 8)
        self.assertEqual(score_col.numeric_scale, 2)

    @patch("schema_discovery._get_connection")
    def test_empty_result_raises_value_error(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn([])
        with self.assertRaises(ValueError):
            self.sd.discover_schema("nonexistent_table")

    @patch("schema_discovery._get_connection")
    def test_result_is_cached(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_PG_ROWS)
        self.sd.discover_schema("orders")
        self.sd.discover_schema("orders")
        # _get_connection should only be called once due to lru_cache
        self.assertEqual(mock_get_conn.call_count, 1)


# ---------------------------------------------------------------------------
# MySQL fetch
# ---------------------------------------------------------------------------

_MYSQL_ROWS = [
    {"column_name": "id",    "data_type": "int",     "is_nullable": "NO",  "character_maximum_length": None, "numeric_precision": 10, "numeric_scale": 0},
    {"column_name": "label", "data_type": "varchar", "is_nullable": "YES", "character_maximum_length": 255,  "numeric_precision": None, "numeric_scale": None},
]


class TestDiscoverSchemaMySQL(unittest.TestCase):

    def setUp(self):
        self.sd = _load_sd("mysql")

    def tearDown(self):
        sys.modules.pop("config", None)

    def _mock_conn(self, rows):
        cursor = MagicMock()
        cursor.__enter__ = lambda s: s
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchall.return_value = rows
        conn = MagicMock()
        conn.cursor.return_value = cursor
        return conn

    @patch("schema_discovery._get_connection")
    def test_mysql_column_names(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_MYSQL_ROWS)
        cols = self.sd.discover_schema("items")
        self.assertEqual([c.name for c in cols], ["id", "label"])

    @patch("schema_discovery._get_connection")
    def test_mysql_nullable(self, mock_get_conn):
        mock_get_conn.return_value = self._mock_conn(_MYSQL_ROWS)
        cols = self.sd.discover_schema("items")
        self.assertFalse(cols[0].is_nullable)
        self.assertTrue(cols[1].is_nullable)


# ---------------------------------------------------------------------------
# invalidate_cache
# ---------------------------------------------------------------------------

class TestInvalidateCache(unittest.TestCase):

    def setUp(self):
        self.sd = _load_sd("postgresql")

    def tearDown(self):
        sys.modules.pop("config", None)

    @patch("schema_discovery._get_connection")
    def test_cache_cleared_after_invalidate(self, mock_get_conn):
        cursor = MagicMock()
        cursor.__enter__ = lambda s: s
        cursor.__exit__ = MagicMock(return_value=False)
        cursor.fetchall.return_value = _PG_ROWS
        mock_get_conn.return_value = MagicMock(cursor=MagicMock(return_value=cursor))

        self.sd.discover_schema("orders")
        self.sd.invalidate_cache()
        self.sd.discover_schema("orders")
        # After cache clear, connection is opened again
        self.assertGreaterEqual(mock_get_conn.call_count, 2)


if __name__ == "__main__":
    unittest.main()
