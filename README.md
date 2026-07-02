# Australian Banking Transaction Pipeline

An end-to-end batch data pipeline simulating a retail banking transaction ingestion system, modelled on Australian banking transaction data structures.

> **Disclaimer:** Personal learning project built with entirely synthetic, programmatically generated data. Not affiliated with, endorsed by, or using systems, schemas, or data from any financial institution. "Australian banking" refers to generic retail-banking data structures (e.g. BSB formats, common merchant categories), not any specific bank.

## How this fits with the rest of the project

This is one of four repos that together form an end-to-end banking data platform:

| Repo | Stack | Role |
| --- | --- | --- |
| **[`aus-banking-pipeline`](https://github.com/vivianasoyoung/aus-banking-pipeline)** *(You are here)* | Airflow, Postgres, Docker | Foundation: synthetic data generation + batch ingestion |
| [`aus-dbt-analytics`](https://github.com/vivianasoyoung/aus-dbt-analytics) | dbt-postgres, dbt_utils | Staging → intermediate → marts transformations (also runnable against AWS RDS) |
| [`aus-fraud-streaming`](https://github.com/vivianasoyoung/aus-fraud-streaming) | Kafka, Python, Postgres | Real-time rule-based fraud detection |
| [`aus-feature-store`](https://github.com/vivianasoyoung/aus-feature-store) | Feast, MLflow, FastAPI | ML feature store + model serving |

This repo is **ingestion-only**. Downstream transformations live in `aus-dbt-analytics` and are scheduled independently.

---

## Architecture

```
Synthetic Data Generator
        │
        ▼
   Raw CSV Files
        │
        ▼
  Apache Airflow DAG (daily @ 6am)
   ├── Source file validation
   ├── Row-level validation + split
   │      ├── Good rows ──► raw.transactions       (idempotent load)
   │      └── Bad rows  ──► raw.transactions_quarantine  (with failure_reasons)
   ├── Load raw.accounts                          (upsert)
   └── Pipeline audit log                          (SUCCESS / SUCCESS_WITH_QUARANTINE / FAILED)
        │
        ▼
   PostgreSQL (raw schema)
        │
        ▼
   Consumed downstream by aus-dbt-analytics
```

## Tech Stack

| Layer | Tool |
|---|---|
| Orchestration | Apache Airflow 2.8 |
| Storage | PostgreSQL 15 |
| Containerisation | Docker + Docker Compose |
| Data Generation | Python (Faker, pandas) |

## Quick Start

### Prerequisites
- Docker Desktop
- Python 3.10+

### 1. Generate synthetic data

```bash
pip install faker pandas
python scripts/generate_transactions.py --months 6 --accounts 500
```

Generates ~95,000 synthetic transactions across 500 accounts over six months, using Australian Bank State Branch (BSB) code formats.

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in POSTGRES_PASSWORD, AIRFLOW_SECRET_KEY, AIRFLOW_FERNET_KEY
# Generation commands are in the comments inside .env.example
```

### 3. Start the stack

```bash
docker-compose up -d
```

| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| pgAdmin | http://localhost:5050 | admin@admin.com / admin |

### 4. Trigger the pipeline

The Postgres connection (`aus_postgres`) is provisioned automatically via the
`AIRFLOW_CONN_AUS_POSTGRES` environment variable. In the Airflow UI just
unpause the `aus_transaction_pipeline` DAG and trigger a run.

## Data Model

| Table | Description |
|---|---|
| `raw.transactions` | Validated transactions (incremental, idempotent via `ON CONFLICT DO NOTHING`) |
| `raw.transactions_quarantine` | Rejected rows with a `failure_reasons` array — kept for audit and replay |
| `raw.accounts` | Account master data (upsert) |
| `raw.pipeline_runs` | Audit log of every DAG run: status, rows loaded, rows quarantined, duration |

## Data Quality: partial-load with quarantine

Rather than failing the whole batch on a single bad row (which would block hours
of downstream work for one corrupt record), this pipeline **validates each row
and routes failures to a quarantine table** so good rows always load.

Each row is checked for:

- **Schema validation** — required fields present, parseable dates, valid types
- **Business rules** — amount within `[0, 1,000,000]`, transaction date within
  the last 5 years, valid `transaction_type` (`DEBIT` / `CREDIT`)
- **Referential integrity** — `account_id` exists in `raw.accounts`

Bad rows are inserted into `raw.transactions_quarantine` with a
`failure_reasons` array describing every check they failed. The audit row in
`raw.pipeline_runs` records the split with status `SUCCESS_WITH_QUARANTINE`,
or `SUCCESS` if every row passed, or `FAILED` if the load itself errored.

This pattern reflects production tradeoffs in real DE work: **fail-fast loses
data; partial-load with quarantine preserves it and surfaces the problem**.

## Performance: measured, not assumed

The default Quick Start demo is ~95K rows, where load strategy barely
matters. To find out whether it would matter at real scale, `load_transactions()`
was benchmarked against a synthetic 2,312,145-row dataset comparing the
original `execute_values(page_size=500)` approach against a `COPY`-based
bulk load:

| Method | Time | Rows/sec |
|---|---|---|
| `execute_values(page_size=500)` (original) | 114.06s | 20,271 |
| `COPY` via temp table (current) | 35.03s | 66,010 |

**3.3x speedup.** `load_transactions()` now uses the COPY-based approach —
`COPY` can't express an upsert directly, so it loads into a temp table first,
then does `INSERT ... SELECT ... ON CONFLICT DO NOTHING` from there to
preserve idempotency. Full methodology, caveats, and the reproducible
benchmark script: [`docs/perf-benchmark.md`](docs/perf-benchmark.md).

## Australian Banking Context

- BSB numbers follow regional Australian formatting conventions
- Merchant categories mirror common Australian retail/service patterns
- Account types: SAVINGS, TRANSACTION, OFFSET
- Channels: EFTPOS, ATM, ONLINE, BPAY

## Project Structure

```
aus-banking-pipeline/
├── airflow/dags/transaction_pipeline_dag.py
├── docker/init.sql
├── scripts/generate_transactions.py
├── scripts/benchmark_load.py
├── docs/perf-benchmark.md
├── data/raw/                    # gitignored — regenerated locally
├── docker-compose.yml
├── .env.example
└── README.md
```
