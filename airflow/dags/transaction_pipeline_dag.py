"""
transaction_pipeline_dag.py
---------------------------
Daily DAG (ingestion only):
  1. Verifies raw CSV data exists
  2. Validates and splits data into good (load) and bad (quarantine) subsets
       - Technical checks: NULLs, duplicates, invalid types, negatives, future dates
       - Business rules: amounts > $1M, transactions older than 5 years
  3. Loads accounts (upsert) and good transactions (incremental via high-water mark)
  4. Routes quarantined rows to raw.transactions_quarantine with failure reasons
  5. Logs the run outcome to raw.pipeline_runs
       Status: SUCCESS if nothing quarantined, SUCCESS_WITH_QUARANTINE otherwise

Designed for partial loads: bad rows never halt the pipeline; they are quarantined
for investigation while good rows continue to land downstream.

Downstream transformations live in the aus-dbt-analytics repo and are
scheduled independently. Credentials come from the Airflow Connection
`aus_postgres` — no secrets in code.
"""

from datetime import datetime, timedelta
import logging
import os

import pandas as pd
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import execute_values

log = logging.getLogger(__name__)

POSTGRES_CONN_ID       = "aus_postgres"
RAW_TRANSACTIONS_PATH  = "/opt/airflow/data/raw/transactions.csv"
RAW_ACCOUNTS_PATH      = "/opt/airflow/data/raw/accounts.csv"
GOOD_TRANSACTIONS_PATH = "/tmp/good_transactions.csv"
BAD_TRANSACTIONS_PATH  = "/tmp/bad_transactions.csv"

# Business-rule thresholds
AMOUNT_SUSPICIOUS_THRESHOLD = 1_000_000   # > $1M is implausible for retail banking
MAX_TRANSACTION_AGE_YEARS   = 5           # older than this is suspicious

default_args = {
    "owner":            "data-engineering",
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
}


def _get_conn():
    return PostgresHook(postgres_conn_id=POSTGRES_CONN_ID).get_conn()


def check_source_files(**_):
    for path in (RAW_TRANSACTIONS_PATH, RAW_ACCOUNTS_PATH):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Source file not found: {path}. "
                "Run: python scripts/generate_transactions.py --months 6 --accounts 500"
            )
        log.info("Found %s (%.1f MB)", path, os.path.getsize(path) / 1_000_000)


def validate_and_split(**context):
    """
    Validate each row, then split into good (load) and bad (quarantine) subsets.

    Technical checks (data integrity): NULLs, duplicates, invalid types,
    negatives, future dates.
    Business rules (plausibility): implausibly large amounts, transactions
    older than the configured age threshold.

    Writes two files:
      - GOOD_TRANSACTIONS_PATH: rows that passed all checks
      - BAD_TRANSACTIONS_PATH: rows that failed at least one check, plus a
        ';'-delimited `failure_reasons` column listing all checks that fired
    """
    df = pd.read_csv(RAW_TRANSACTIONS_PATH, parse_dates=["transaction_date"])
    df["failure_reasons"] = ""

    # --- Technical validation -------------------------------------------------
    null_mask = df[["transaction_id", "account_id", "transaction_date",
                    "amount", "transaction_type"]].isna().any(axis=1)
    df.loc[null_mask, "failure_reasons"] += "null_critical_field;"

    dup_mask = df["transaction_id"].duplicated(keep="first")
    df.loc[dup_mask, "failure_reasons"] += "duplicate_transaction_id;"

    invalid_type_mask = ~df["transaction_type"].isin({"DEBIT", "CREDIT"})
    df.loc[invalid_type_mask, "failure_reasons"] += "invalid_transaction_type;"

    neg_mask = df["amount"] < 0
    df.loc[neg_mask, "failure_reasons"] += "negative_amount;"

    future_mask = df["transaction_date"] > datetime.now()
    df.loc[future_mask, "failure_reasons"] += "future_dated;"

    # --- Business-rule validation --------------------------------------------
    big_amount_mask = df["amount"].abs() > AMOUNT_SUSPICIOUS_THRESHOLD
    df.loc[big_amount_mask, "failure_reasons"] += (
        f"amount_over_{AMOUNT_SUSPICIOUS_THRESHOLD}_threshold;"
    )

    cutoff_date = datetime.now() - timedelta(days=365 * MAX_TRANSACTION_AGE_YEARS)
    too_old_mask = df["transaction_date"] < cutoff_date
    df.loc[too_old_mask, "failure_reasons"] += (
        f"transaction_older_than_{MAX_TRANSACTION_AGE_YEARS}_years;"
    )

    # --- Split ----------------------------------------------------------------
    bad = df[df["failure_reasons"] != ""].copy()
    good = df[df["failure_reasons"] == ""].drop(columns=["failure_reasons"]).copy()

    good.to_csv(GOOD_TRANSACTIONS_PATH, index=False)
    bad.to_csv(BAD_TRANSACTIONS_PATH, index=False)

    log.info(
        "Validated %s rows: %s good, %s quarantined",
        f"{len(df):,}", f"{len(good):,}", f"{len(bad):,}",
    )

    context["ti"].xcom_push(key="total_count", value=int(len(df)))
    context["ti"].xcom_push(key="good_count",  value=int(len(good)))
    context["ti"].xcom_push(key="bad_count",   value=int(len(bad)))


def load_accounts(**_):
    df = pd.read_csv(RAW_ACCOUNTS_PATH)
    df["loaded_at"] = datetime.now()
    records = list(df.itertuples(index=False, name=None))

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO raw.accounts (
                    account_id, customer_id, bsb, account_number,
                    account_type, open_date, balance, credit_limit, loaded_at
                ) VALUES %s
                ON CONFLICT (account_id) DO UPDATE SET
                    balance   = EXCLUDED.balance,
                    loaded_at = EXCLUDED.loaded_at
                """,
                records,
                page_size=1000,
            )
            inserted_or_updated = cur.rowcount
        conn.commit()
    finally:
        conn.close()

    log.info("Upserted %s accounts.", f"{inserted_or_updated:,}")


def load_transactions(**context):
    """Load validated (good) transactions incrementally via high-water mark."""
    if not os.path.exists(GOOD_TRANSACTIONS_PATH):
        log.info("No good_transactions.csv found; skipping load.")
        context["ti"].xcom_push(key="rows_loaded", value=0)
        return

    df = pd.read_csv(GOOD_TRANSACTIONS_PATH, parse_dates=["transaction_date"])
    if df.empty:
        log.info("Good transactions file is empty; nothing to load.")
        context["ti"].xcom_push(key="rows_loaded", value=0)
        return

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(transaction_date), '1970-01-01'::timestamp) "
                "FROM raw.transactions"
            )
            high_water = cur.fetchone()[0]
        log.info("High-water mark: %s", high_water)

        new_df = df[df["transaction_date"] > high_water].copy()
        if new_df.empty:
            log.info("No new transactions since high-water mark; nothing to load.")
            context["ti"].xcom_push(key="rows_loaded", value=0)
            return

        new_df["loaded_at"] = datetime.now()
        records = list(new_df.itertuples(index=False, name=None))

        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO raw.transactions (
                    transaction_id, account_id, bsb, account_number,
                    transaction_date, amount, transaction_type,
                    merchant_name, merchant_category, merchant_state,
                    description, balance_after, channel, status, loaded_at
                ) VALUES %s
                ON CONFLICT (transaction_id) DO NOTHING
                """,
                records,
                page_size=500,
            )
            rows_loaded = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    log.info("Loaded %s transactions.", f"{rows_loaded:,}")
    context["ti"].xcom_push(key="rows_loaded", value=int(rows_loaded))


def load_quarantined_transactions(**context):
    """Route quarantined rows to raw.transactions_quarantine with failure reasons."""
    if not os.path.exists(BAD_TRANSACTIONS_PATH):
        log.info("No bad_transactions.csv found; nothing to quarantine.")
        context["ti"].xcom_push(key="rows_quarantined", value=0)
        return

    df = pd.read_csv(BAD_TRANSACTIONS_PATH, parse_dates=["transaction_date"])
    if df.empty:
        log.info("No rows to quarantine.")
        context["ti"].xcom_push(key="rows_quarantined", value=0)
        return

    df["quarantined_at"] = datetime.now()
    df["dag_run_id"] = context["dag_run"].run_id

    # Convert ';'-delimited string into a Python list for PostgreSQL TEXT[]
    df["failure_reasons"] = df["failure_reasons"].apply(
        lambda s: [r for r in str(s).rstrip(";").split(";") if r]
    )

    cols = [
        "transaction_id", "account_id", "bsb", "account_number",
        "transaction_date", "amount", "transaction_type",
        "merchant_name", "merchant_category", "merchant_state",
        "description", "balance_after", "channel", "status",
        "failure_reasons", "quarantined_at", "dag_run_id",
    ]
    records = list(df[cols].itertuples(index=False, name=None))

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            execute_values(
                cur,
                """
                INSERT INTO raw.transactions_quarantine (
                    transaction_id, account_id, bsb, account_number,
                    transaction_date, amount, transaction_type,
                    merchant_name, merchant_category, merchant_state,
                    description, balance_after, channel, status,
                    failure_reasons, quarantined_at, dag_run_id
                ) VALUES %s
                """,
                records,
                page_size=500,
            )
            rows_quarantined = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    log.info("Quarantined %s rows.", f"{rows_quarantined:,}")
    context["ti"].xcom_push(key="rows_quarantined", value=int(rows_quarantined))


def log_pipeline_run(**context):
    """Write an audit row with loaded + quarantined counts and overall status."""
    ti = context["ti"]
    rows_loaded      = ti.xcom_pull(task_ids="load_transactions",
                                    key="rows_loaded") or 0
    rows_quarantined = ti.xcom_pull(task_ids="load_quarantined_transactions",
                                    key="rows_quarantined") or 0

    if rows_quarantined > 0:
        status  = "SUCCESS_WITH_QUARANTINE"
        summary = f"{rows_quarantined} row(s) routed to raw.transactions_quarantine"
    else:
        status  = "SUCCESS"
        summary = None

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO raw.pipeline_runs
                    (dag_id, run_date, rows_ingested, rows_rejected,
                     status, quality_issues, started_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    context["dag"].dag_id,
                    context["ds"],
                    rows_loaded,
                    rows_quarantined,
                    status,
                    summary,
                    context["dag_run"].start_date,
                    datetime.now(),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    log.info(
        "Audit logged: status=%s loaded=%s quarantined=%s",
        status, rows_loaded, rows_quarantined,
    )


with DAG(
    dag_id="aus_transaction_pipeline",
    description="Daily ingestion of Australian retail banking transactions with partial-load quarantine",
    schedule="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["banking", "ingestion", "daily", "quarantine"],
) as dag:

    t1_check_files  = PythonOperator(task_id="check_source_files",
                                     python_callable=check_source_files)
    t2_validate     = PythonOperator(task_id="validate_and_split",
                                     python_callable=validate_and_split)
    t3_accounts     = PythonOperator(task_id="load_accounts",
                                     python_callable=load_accounts)
    t4_transactions = PythonOperator(task_id="load_transactions",
                                     python_callable=load_transactions)
    t5_quarantine   = PythonOperator(task_id="load_quarantined_transactions",
                                     python_callable=load_quarantined_transactions)
    t6_audit        = PythonOperator(task_id="log_pipeline_run",
                                     python_callable=log_pipeline_run,
                                     trigger_rule="all_done")

    # Flow:
    #   check_source_files
    #         ├──► validate_and_split ──► load_transactions
    #         │                       └──► load_quarantined_transactions
    #         └──► load_accounts
    # All converge at log_pipeline_run (trigger_rule="all_done")
    t1_check_files >> [t2_validate, t3_accounts]
    t2_validate >> [t4_transactions, t5_quarantine]
    [t3_accounts, t4_transactions, t5_quarantine] >> t6_audit
