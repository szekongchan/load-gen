"""
tests/test_sql_builder.py — Unit tests for sql_builder.py.

No database connection required. All assertions are on the generated
SQL strings and parameter lists.
"""

import importlib
import sys
import types
import unittest


# ---------------------------------------------------------------------------
# Minimal config stub so sql_builder can be imported without a real config
# ---------------------------------------------------------------------------

def _make_config_stub(adapter: str) -> types.ModuleType:
    mod = types.ModuleType("config")
    mod.DB_ADAPTER = adapter
    return mod


class _BuilderTestBase(unittest.TestCase):
    """Base class that patches config.DB_ADAPTER before each test."""

    adapter = "postgresql"  # override in subclasses

    def setUp(self):
        sys.modules["config"] = _make_config_stub(self.adapter)
        # Force reload so sql_builder picks up the stubbed config
        if "sql_builder" in sys.modules:
            importlib.reload(sys.modules["sql_builder"])
        import sql_builder as sb
        self.sb = sb

    def tearDown(self):
        sys.modules.pop("config", None)


# ---------------------------------------------------------------------------
# build_insert
# ---------------------------------------------------------------------------

class TestBuildInsertPostgres(_BuilderTestBase):
    adapter = "postgresql"

    def test_basic_insert_structure(self):
        sql, params = self.sb.build_insert("orders", {"id": 1, "amount": 9.99})
        self.assertIn("INSERT INTO", sql)
        self.assertIn('"orders"', sql)
        self.assertIn('"id"', sql)
        self.assertIn('"amount"', sql)
        self.assertEqual(sql.count("%s"), 2)
        self.assertEqual(params, [1, 9.99])

    def test_column_order_matches_params(self):
        row = {"a": 1, "b": 2, "c": 3}
        sql, params = self.sb.build_insert("t", row)
        self.assertEqual(len(params), 3)
        self.assertEqual(sql.count("%s"), 3)

    def test_none_value_allowed(self):
        sql, params = self.sb.build_insert("t", {"col": None})
        self.assertIn(None, params)

    def test_empty_row_raises(self):
        with self.assertRaises(ValueError):
            self.sb.build_insert("t", {})

    def test_unsafe_table_name_raises(self):
        with self.assertRaises(ValueError):
            self.sb.build_insert("bad; DROP TABLE orders--", {"col": 1})

    def test_unsafe_column_name_raises(self):
        with self.assertRaises(ValueError):
            self.sb.build_insert("t", {"bad col": 1})


class TestBuildInsertMySQL(_BuilderTestBase):
    adapter = "mysql"

    def test_backtick_quoting(self):
        sql, _ = self.sb.build_insert("orders", {"id": 1})
        self.assertIn("`orders`", sql)
        self.assertIn("`id`", sql)


# ---------------------------------------------------------------------------
# build_select
# ---------------------------------------------------------------------------

class TestBuildSelectPostgres(_BuilderTestBase):
    adapter = "postgresql"

    def test_select_no_where(self):
        sql, params = self.sb.build_select("orders")
        self.assertIn("SELECT *", sql)
        self.assertIn('"orders"', sql)
        self.assertNotIn("WHERE", sql)
        self.assertIn("LIMIT %s", sql)
        self.assertEqual(params, [100])

    def test_select_with_where(self):
        sql, params = self.sb.build_select("orders", "id", 42)
        self.assertIn("WHERE", sql)
        self.assertIn('"id"', sql)
        self.assertEqual(params, [42, 100])

    def test_custom_limit(self):
        sql, params = self.sb.build_select("orders", limit=10)
        self.assertEqual(params[-1], 10)

    def test_unsafe_table_raises(self):
        with self.assertRaises(ValueError):
            self.sb.build_select("orders; DROP TABLE orders--")

    def test_unsafe_where_column_raises(self):
        with self.assertRaises(ValueError):
            self.sb.build_select("orders", "id; --", 1)


class TestBuildSelectMySQL(_BuilderTestBase):
    adapter = "mysql"

    def test_backtick_quoting(self):
        sql, _ = self.sb.build_select("orders", "id", 1)
        self.assertIn("`orders`", sql)
        self.assertIn("`id`", sql)


# ---------------------------------------------------------------------------
# _sanitize_identifier
# ---------------------------------------------------------------------------

class TestSanitizeIdentifier(_BuilderTestBase):
    adapter = "postgresql"

    def test_valid_identifiers(self):
        for name in ("foo", "foo_bar", "Foo123", "_private", "A"):
            self.sb._sanitize_identifier(name)  # should not raise

    def test_invalid_identifiers(self):
        bad = ["1starts_with_digit", "has space", "semi;colon", "dash-name", ""]
        for name in bad:
            with self.assertRaises(ValueError, msg=f"{name!r} should be rejected"):
                self.sb._sanitize_identifier(name)


if __name__ == "__main__":
    unittest.main()
