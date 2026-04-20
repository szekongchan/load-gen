# Load Generator for SQL Insert & Query

## Requirements

- A load generator for SQL `INSERT` and `SELECT` operations
- Given a table name, **self-discover the schema** from the database metadata
- Based on the schema, **generate INSERT statements with random values** matched to column types
- Execute generated SQL statements under configurable load

---

## Tool Decision: Locust (over JMeter)

**Chosen: [Locust](https://locust.io/)**

| Criteria | Locust | JMeter |
|---|---|---|
| Language | Python — easy custom SQL logic | Java/XML — harder to extend |
| Schema discovery | Native DB drivers (`psycopg2`, `pymysql`) | Requires JDBC plugin |
| Random data gen | `Faker`, `random` — straightforward | Scripted via BeanShell/Groovy |
| Scripting flexibility | High | Medium |
| CI/CD integration | Easy (headless, pip installable) | Heavier setup |

Locust enables clean Python modules for schema discovery and data generation, then wraps them in a Locust `User` class for load execution.

---

## Architecture

```
load-gen/
├── README.md
├── requirements.txt
├── config.py                  # DB connection config, target table, load params
├── schema_discovery.py        # Module: connect to DB, query information_schema
├── data_generator.py          # Module: generate random values per column type
├── sql_builder.py             # Module: build INSERT / SELECT SQL strings
├── locustfile.py              # Locust entry point: User tasks for insert & query
└── tests/
    ├── test_schema_discovery.py
    ├── test_data_generator.py
    └── test_sql_builder.py
```

---

## Implementation Plan

### Stage 1 — Project Scaffold
- [ ] Create `requirements.txt` (`locust`, `psycopg2-binary` or `pymysql`, `faker`)
- [ ] Create `config.py` with DB URL, target table name, and Locust settings

### Stage 2 — Schema Discovery (`schema_discovery.py`)
- [ ] Connect to the target database using the configured driver
- [ ] Query `information_schema.columns` for the given table name
- [ ] Return a structured list of `{column_name, data_type, is_nullable, character_maximum_length, ...}`
- [ ] Cache schema to avoid repeated metadata queries during load

### Stage 3 — Random Data Generator (`data_generator.py`)
- [ ] Map SQL data types to generators:
  - `VARCHAR` / `TEXT` → `Faker.word()` / random string up to `max_length`
  - `INTEGER` / `BIGINT` / `SMALLINT` → `random.randint()`
  - `NUMERIC` / `DECIMAL` / `FLOAT` → `random.uniform()`
  - `BOOLEAN` → `random.choice([True, False])`
  - `DATE` → `Faker.date()`
  - `TIMESTAMP` → `Faker.date_time()`
  - `UUID` → `uuid.uuid4()`
  - `JSON` / `JSONB` → minimal valid JSON object
- [ ] Respect `is_nullable` (occasionally emit `NULL` for nullable columns)
- [ ] Produce a `{column: value}` dict for a full row

### Stage 4 — SQL Builder (`sql_builder.py`)
- [ ] `build_insert(table, row_dict)` → parameterized `INSERT INTO … VALUES (…)` with placeholders
- [ ] `build_select(table, where_column, value)` → simple `SELECT * FROM … WHERE … = …`
- [ ] Use parameterized queries (no string interpolation) to prevent SQL injection

### Stage 5 — Locust Load Test (`locustfile.py`)
- [ ] Define a `SQLUser` class inheriting `locust.User`
- [ ] On start: run schema discovery, cache schema
- [ ] Task `insert_row` (weight configurable): generate row → build INSERT → execute
- [ ] Task `query_row` (weight configurable): build SELECT → execute
- [ ] Record response time and success/failure via Locust events

### Stage 6 — Testing
- [ ] Unit test schema discovery against a real or mock DB connection
- [ ] Unit test data generator covers all mapped types and respects nullability
- [ ] Unit test SQL builder produces valid parameterized SQL strings
- [ ] Integration smoke test: run Locust in headless mode for 10 s against a local test DB

---

## Supported Databases

Initially targeting:
- **PostgreSQL** (via `psycopg2`)
- **MySQL / MariaDB** (via `pymysql`) — adapter selectable via config

---

## Usage (planned)

```bash
# Install dependencies
pip install -r requirements.txt

# Run load test (headless, 10 users, 60 seconds)
locust -f locustfile.py --headless -u 10 -r 2 -t 60s \
  --host postgresql://user:pass@localhost:5432/mydb \
  --table my_table
```
