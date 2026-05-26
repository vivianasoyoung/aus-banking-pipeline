# Australian Banking dbt Analytics Layer

Analytics engineering project on synthetic Australian banking transaction data. Implements a three-layer dbt architecture — staging, intermediate, marts — with column-level documentation, tests, and snapshots. Runs on PostgreSQL (local) and BigQuery (cloud).

> **Disclaimer:** Personal learning project built with entirely synthetic, programmatically generated data. Not affiliated with, endorsed by, or using systems, schemas, or data from any financial institution.

## How this fits with the rest of the project

| Repo | Stack | Role |
| --- | --- | --- |
| [`aus-banking-pipeline`](https://github.com/vivianasoyoung/aus-banking-pipeline) | Airflow, Postgres, Docker | Foundation: synthetic data generation + batch ingestion |
| **[`aus-dbt-analytics`](https://github.com/vivianasoyoung/aus-dbt-analytics)** *(You are here)* | dbt-postgres, dbt_utils | Staging → intermediate → marts transformations |
| [`aus-fraud-streaming`](https://github.com/vivianasoyoung/aus-fraud-streaming) | Kafka, Python, Postgres | Real-time rule-based fraud detection |
| [`aus-feature-store`](https://github.com/vivianasoyoung/aus-feature-store) | Feast, MLflow, FastAPI | ML feature store + model serving |

Reads from the raw schema populated by `aus-banking-pipeline`.

---

## Architecture

```
raw.transactions / raw.accounts (PostgreSQL)
        │
        ▼
Staging (views)        stg_transactions, stg_accounts
        │
        ▼
Intermediate (views)   int_customer_monthly_category_spend, int_customer_monthly_spend
        │
        ▼
Marts (tables)         mart_customer_segments, mart_category_trends,
                       mart_monthly_summary, mart_daily_category_spend
```

## Tech Stack

| Layer | Tool |
|---|---|
| Transformation | dbt 1.x (postgres + bigquery adapters) |
| Packages | dbt_utils, dbt_expectations |
| Warehouses | PostgreSQL 15 (local), BigQuery (cloud) |

## Quick Start

### Prerequisites
- Python 3.10+
- PostgreSQL with the raw schema populated (see [aus-banking-pipeline](https://github.com/vivianasoyoung/aus-banking-pipeline))

```bash
pip install dbt-postgres
cd <project dir>
dbt deps
cp profiles.example.yml ~/.dbt/profiles.yml   # set credentials via env vars
dbt build          # runs models + 40+ data tests
dbt docs generate && dbt docs serve --port 8081
```

## Models

| Layer | Model | Description |
|---|---|---|
| staging | stg_transactions / stg_accounts | Cleaned, typed source data |
| intermediate | int_customer_monthly_category_spend | Monthly spend per account × category |
| intermediate | int_customer_monthly_spend | Monthly spend per account (rolled up) |
| marts | mart_customer_segments | Accounts segmented by 12-month avg spend |
| marts | mart_category_trends | Monthly spend trends by category (weighted avgs) |
| marts | mart_monthly_summary | Portfolio-level monthly KPIs |
| marts | mart_daily_category_spend | Daily category spend with rankings + cumulative totals |

## Testing

Every model has column-level tests in `_*_models.yml`: `unique`, `not_null`, `accepted_values`, `relationships`, plus `dbt_utils` expression and combination tests. Run with `dbt test` (also runs as part of `dbt build` in CI).

## Cloud (BigQuery)

The same models run on BigQuery via a second dbt target — demonstrating warehouse portability. See the BigQuery setup notes for configuration.
