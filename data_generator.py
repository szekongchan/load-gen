"""
data_generator.py — Generate a random row dict for a given table schema.

Maps SQL data types returned by information_schema to appropriate Python
values using the Faker library and the standard random / uuid modules.
"""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional

from faker import Faker

import config
from schema_discovery import ColumnInfo

_faker = Faker()

# ---------------------------------------------------------------------------
# Type → generator mapping
# ---------------------------------------------------------------------------

# Keywords that appear in information_schema data_type strings, checked in
# order so more specific prefixes are matched before shorter ones.
_TYPE_MAP: list[tuple[str, Any]] = [
    # UUID
    ("uuid",            lambda col: str(uuid.uuid4())),
    # Boolean
    ("bool",            lambda col: random.choice([True, False])),
    # Integers — unsigned-aware helpers used at call time
    ("bigint",          lambda col: _random_int(col, signed_max=2**62, unsigned_max=2**64 - 1)),
    ("smallint",        lambda col: _random_int(col, signed_max=32767, unsigned_max=65535)),
    ("tinyint",         lambda col: _random_int(col, signed_max=127, unsigned_max=255)),
    ("integer",         lambda col: _random_int(col, signed_max=2**30, unsigned_max=2**32 - 1)),
    ("int",             lambda col: _random_int(col, signed_max=2**30, unsigned_max=2**32 - 1)),
    ("serial",          lambda col: random.randint(1, 2**30)),
    # Floating point
    ("double precision",lambda col: random.uniform(-1e9, 1e9)),
    ("float",           lambda col: random.uniform(-1e9, 1e9)),
    ("real",            lambda col: round(random.uniform(-1e6, 1e6), 6)),
    # Fixed precision
    ("numeric",         lambda col: _random_numeric(col)),
    ("decimal",         lambda col: _random_numeric(col)),
    # Date / time  — order matters: more specific keys before shorter ones
    ("timestamp",       lambda col: _faker.date_time()),
    ("datetime",        lambda col: _faker.date_time()),   # MariaDB/MySQL type
    ("year",            lambda col: random.randint(1901, 2155)),  # MySQL YEAR type
    ("date",            lambda col: _faker.date_object()),
    ("time",            lambda col: _faker.time_object()),
    ("interval",        lambda col: f"{random.randint(0, 365)} days"),
    # JSON
    ("jsonb",           lambda col: _random_json()),
    ("json",            lambda col: _random_json()),
    # Text / character
    ("character varying", lambda col: _random_string(col)),
    ("varchar",         lambda col: _random_string(col)),
    ("char",            lambda col: _random_string(col)),
    ("text",            lambda col: _faker.paragraph(nb_sentences=1)),
    # Binary
    ("bytea",           lambda col: random.randbytes(random.randint(4, 64))),
    ("blob",            lambda col: random.randbytes(random.randint(4, 64))),
    # MySQL ENUM / SET — pick a valid value from the allowed list
    ("enum",            lambda col: random.choice(col.enum_values) if col.enum_values else _faker.word()),
    ("set",             lambda col: random.choice(col.enum_values) if col.enum_values else _faker.word()),
    # Network / misc PostgreSQL types
    ("inet",            lambda col: _faker.ipv4()),
    ("macaddr",         lambda col: _faker.mac_address()),
    ("cidr",            lambda col: f"{_faker.ipv4()}/24"),
]


# ---------------------------------------------------------------------------
# Helper generators
# ---------------------------------------------------------------------------

def _random_int(col: ColumnInfo, signed_max: int, unsigned_max: int) -> int:
    if col.is_unsigned:
        return random.randint(0, unsigned_max)
    return random.randint(-signed_max, signed_max)


def _random_string(col: ColumnInfo) -> str:
    max_len = col.char_max_length or 255
    # Keep generated strings well within the column limit
    target = min(max_len, random.randint(3, max(3, max_len)))
    return _faker.lexify("?" * target)


def _random_numeric(col: ColumnInfo) -> float:
    precision = col.numeric_precision or 10
    scale = col.numeric_scale or 2
    max_val = 10 ** (precision - scale) - 1
    value = random.uniform(-max_val, max_val)
    return round(value, scale)


def _random_json() -> dict:
    return {
        _faker.word(): _faker.word(),
        _faker.word(): random.randint(0, 1000),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _resolve_generator(col: ColumnInfo):
    """Return the generator callable for the given column's data type."""
    dt = col.data_type.lower()
    for key, gen in _TYPE_MAP:
        if key in dt:
            return gen
    # Fallback: treat as unbounded text
    return lambda col: _faker.word()


def generate_row(columns: List[ColumnInfo], partition_values: dict | None = None) -> Dict[str, Any]:
    """
    Generate a random row as a {column_name: value} dict.

    Nullable columns emit ``None`` with probability
    ``config.NULLABLE_NULL_PROBABILITY``.

    *partition_values* maps column names to lists of allowed values (used to
    constrain partition key columns so inserts land in a valid partition).
    """
    if partition_values is None:
        partition_values = {}
    row: Dict[str, Any] = {}
    for col in columns:
        # Skip columns the DB generates itself — no value should be supplied
        if col.is_auto_increment or col.is_generated:
            continue
        # Partition key columns must use a known-valid value
        if col.name in partition_values:
            row[col.name] = random.choice(partition_values[col.name])
            continue
        if col.is_nullable and random.random() < config.NULLABLE_NULL_PROBABILITY:
            row[col.name] = None
        else:
            gen = _resolve_generator(col)
            row[col.name] = gen(col)
    return row
