"""
tests/test_data_generator.py — Unit tests for data_generator.py.

Uses mock ColumnInfo objects — no database connection required.
"""

import importlib
import sys
import types
import unittest

from schema_discovery import ColumnInfo


def _make_col(
    name: str,
    data_type: str,
    is_nullable: bool = False,
    char_max_length=None,
    numeric_precision=None,
    numeric_scale=None,
) -> ColumnInfo:
    return ColumnInfo(
        name=name,
        data_type=data_type,
        is_nullable=is_nullable,
        char_max_length=char_max_length,
        numeric_precision=numeric_precision,
        numeric_scale=numeric_scale,
    )


def _load_generator(nullable_null_probability: float = 0.0):
    """Return data_generator module with a config stub."""
    cfg = types.ModuleType("config")
    cfg.NULLABLE_NULL_PROBABILITY = nullable_null_probability
    sys.modules["config"] = cfg
    if "data_generator" in sys.modules:
        importlib.reload(sys.modules["data_generator"])
    import data_generator as dg
    return dg


class TestGenerateRowTypes(unittest.TestCase):

    def setUp(self):
        self.dg = _load_generator(nullable_null_probability=0.0)

    def tearDown(self):
        sys.modules.pop("config", None)

    def _generate(self, data_type, **kwargs):
        col = _make_col("col", data_type, **kwargs)
        row = self.dg.generate_row([col])
        return row["col"]

    # Integers
    def test_integer(self):
        val = self._generate("integer")
        self.assertIsInstance(val, int)

    def test_bigint(self):
        val = self._generate("bigint")
        self.assertIsInstance(val, int)

    def test_smallint(self):
        val = self._generate("smallint")
        self.assertIsInstance(val, int)
        self.assertGreaterEqual(val, -32768)
        self.assertLessEqual(val, 32767)

    # Floats
    def test_float(self):
        val = self._generate("float")
        self.assertIsInstance(val, float)

    def test_double_precision(self):
        val = self._generate("double precision")
        self.assertIsInstance(val, float)

    # Numeric
    def test_numeric(self):
        val = self._generate("numeric", numeric_precision=10, numeric_scale=2)
        self.assertIsInstance(val, float)

    def test_decimal(self):
        val = self._generate("decimal", numeric_precision=8, numeric_scale=3)
        self.assertIsInstance(val, float)

    # Boolean
    def test_boolean(self):
        val = self._generate("boolean")
        self.assertIsInstance(val, bool)

    # UUID
    def test_uuid(self):
        import uuid
        val = self._generate("uuid")
        self.assertIsInstance(val, str)
        uuid.UUID(val)  # raises if invalid

    # Text types
    def test_text(self):
        val = self._generate("text")
        self.assertIsInstance(val, str)

    def test_varchar_respects_max_length(self):
        val = self._generate("character varying", char_max_length=10)
        self.assertIsInstance(val, str)
        self.assertLessEqual(len(val), 10)

    def test_char(self):
        val = self._generate("char", char_max_length=5)
        self.assertIsInstance(val, str)

    # Date / time
    def test_date(self):
        import datetime
        val = self._generate("date")
        self.assertIsInstance(val, datetime.date)

    def test_datetime(self):
        import datetime
        val = self._generate("datetime")
        self.assertIsInstance(val, datetime.datetime)

    def test_timestamp(self):
        import datetime
        val = self._generate("timestamp")
        self.assertIsInstance(val, datetime.datetime)

    # JSON
    def test_json(self):
        val = self._generate("json")
        self.assertIsInstance(val, dict)

    def test_jsonb(self):
        val = self._generate("jsonb")
        self.assertIsInstance(val, dict)

    # Binary
    def test_bytea(self):
        val = self._generate("bytea")
        self.assertIsInstance(val, bytes)

    # Unknown type fallback
    def test_unknown_type_returns_string(self):
        val = self._generate("some_exotic_type")
        self.assertIsInstance(val, str)


class TestNullability(unittest.TestCase):

    def setUp(self):
        # Always null for nullable columns
        self.dg = _load_generator(nullable_null_probability=1.0)

    def tearDown(self):
        sys.modules.pop("config", None)

    def test_nullable_col_emits_none(self):
        col = _make_col("col", "integer", is_nullable=True)
        row = self.dg.generate_row([col])
        self.assertIsNone(row["col"])

    def test_non_nullable_col_never_none(self):
        # Even with probability=1.0, non-nullable columns must have a value
        col = _make_col("col", "integer", is_nullable=False)
        row = self.dg.generate_row([col])
        self.assertIsNotNone(row["col"])


class TestGenerateRowKeys(unittest.TestCase):

    def setUp(self):
        self.dg = _load_generator()

    def tearDown(self):
        sys.modules.pop("config", None)

    def test_all_columns_present(self):
        cols = [
            _make_col("id", "integer"),
            _make_col("name", "text"),
            _make_col("score", "numeric", numeric_precision=5, numeric_scale=2),
        ]
        row = self.dg.generate_row(cols)
        self.assertEqual(set(row.keys()), {"id", "name", "score"})


if __name__ == "__main__":
    unittest.main()
