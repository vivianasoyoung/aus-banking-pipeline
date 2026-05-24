# CBA Transaction Pipeline

An end-to-end batch data pipeline simulating a banking transaction ingestion system, modelled on Commonwealth Bank of Australia's transaction data structures.

## How this fits with the rest of the project

This is one of four repos that together form an end-to-end banking data platform:

| Repo | Stack | Role |
| --- | --- | --- |
| **[`cba-banking-pipeline`](https://github.com/vivianasoyoung/cba-banking-pipeline)** *(You are here)* | Airflow, Postgres, Docker | Foundation: synthetic data generation + batch ingestion |
| [`cba-dbt-analytics`](https://github.com/vivianasoyoung/cba-dbt-analytics) | dbt-postgres, dbt_utils | Staging → intermediate → marts transformations |
| [`cba-fraud-streaming`](https://github.com/vivianasoyoung/cba-fraud-streaming) | Kafka, Python, Postgres | Real-time rule-based fraud detection |
| [`cba-feature-store`](https://github.com/vivianasoyoung/cba-feature-store) | Feast, MLflow, FastAPI | ML feature store + model serving |

This repo is **ingestion-only**. Downstream transformations live in `cba-dbt-analytics` and are scheduled independently.

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
   ├── Data quality checks (NULLs, dupes, invalid types, future dates)
   ├── Load raw.accounts (upsert)
   ├── Load raw.transactions (incremental via high-water mark)
   └── Pipeline audit logging
        │
        ▼
   PostgreSQL (raw schema)
        │
        ▼
   Consumed downstream by cba-dbt-analytics
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

Generates approximately 200,000 synthetic transactions spanning six months across 500 accounts with authentic Australian Bank State Branch codes.

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set POSTGRES_PASSWORD
```

### 3. Start the stack

```bash
docker-compose up -d
```

Services:
| Service | URL | Credentials |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| pgAdmin | http://localhost:5050 | admin@admin.com / admin |

### 4. Trigger the pipeline

In Airflow UI:
1. Configure the `cba_postgres` Airflow Connection (host=`postgres`, dbname=`cba_pipeline`, schema=`raw`, user/password from `.env`)
2. Enable the `cba_transaction_pipeline` DAG
3. Trigger a manual run
4. Watch tasks execute in sequence

## Data Model

### Raw Layer (`raw` schema)
| Table | Description |
|---|---|
| `raw.transactions` | All ingested transactions (incremental, idempotent via `ON CONFLICT DO NOTHING`) |
| `raw.accounts` | Account master data (upsert) |
| `raw.pipeline_runs` | Audit log of every DAG run, including any quality issues found |

## Data Quality Checks

The DAG validates each ingestion batch for:
- NULLs in critical columns (`transaction_id`, `account_id`, `transaction_date`, `amount`, `transaction_type`)
- Duplicate `transaction_id` values
- Negative amounts
- Invalid `transaction_type` values (must be `DEBIT` or `CREDIT`)
- Future-dated transactions

Issues are logged to `raw.pipeline_runs.quality_issues` and the run is marked `SUCCESS_WITH_WARNINGS`.

## Australian Banking Context

- Bank State Branch numbers follow regional Australian conventions
- Merchant categories mirror authentic Australian retail and service patterns
- Account types: SAVINGS, TRANSACTION, OFFSET
- Transaction channels: EFTPOS, ATM, ONLINE, BPAY

## Project Structure

```
cba-banking-pipeline/
├── airflow/
│   └── dags/
│       └── transaction_pipeline_dag.py
├── docker/
│   └── init.sql
├── scripts/
│   └── generate_transactions.py
├── data/
│   └── raw/                       # gitignored — regenerated locally
├── docker-compose.yml
├── .env.example
└── README.md
```
