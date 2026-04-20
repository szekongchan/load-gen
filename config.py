"""
config.py — centralised configuration for the load generator.

All settings can be overridden via environment variables so that no
credentials are hard-coded when running in CI or production environments.
"""

import os

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# Supported adapters: "postgresql" | "mysql"
DB_ADAPTER: str = os.getenv("DB_ADAPTER", "postgresql")

DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: int = int(os.getenv("DB_PORT", "5432"))  # 5432 for PG, 3306 for MySQL
DB_NAME: str = os.getenv("DB_NAME", "mydb")
DB_USER: str = os.getenv("DB_USER", "postgres")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

# Table to target for INSERT / SELECT load
TARGET_TABLE: str = os.getenv("TARGET_TABLE", "my_table")

# ---------------------------------------------------------------------------
# Load shape
# ---------------------------------------------------------------------------

# Ratio of insert vs. query tasks (weights passed to Locust @task decorators)
INSERT_WEIGHT: int = int(os.getenv("INSERT_WEIGHT", "3"))
QUERY_WEIGHT: int = int(os.getenv("QUERY_WEIGHT", "1"))

# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

# Probability (0.0–1.0) that a nullable column emits NULL instead of a value
NULLABLE_NULL_PROBABILITY: float = float(os.getenv("NULLABLE_NULL_PROBABILITY", "0.1"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db_url() -> str:
    """Return a SQLAlchemy-style URL for the configured adapter."""
    if DB_ADAPTER == "postgresql":
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    elif DB_ADAPTER == "mysql":
        return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        raise ValueError(f"Unsupported DB_ADAPTER: {DB_ADAPTER!r}. Use 'postgresql' or 'mysql'.")
