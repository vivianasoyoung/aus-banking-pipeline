"""
benchmark_load.py
------------------
Compares two ways of loading transactions.csv into raw.transactions:

  A. execute_values(page_size=500) — the original approach in
     load_transactions() before this benchmark.
  B. COPY FROM STDIN into a temp table, then INSERT ... SELECT with
     ON CONFLICT DO NOTHING — the approach load_transactions() now uses.

Results from a 2,312,145-row synthetic dataset (generate_transactions.py
--months 24 --accounts 3000), measured on local Postgres 16:

    execute_values : 114.06s  (20,271 rows/sec)
    COPY           : 35.03s   (66,010 rows/sec)
    Speedup        : 3.3x

See docs/perf-benchmark.md for full methodology and caveats.

Usage:
    createdb perf_bench
    psql perf_bench -f docker/init.sql   # or just the raw.transactions DDL
    python scripts/generate_transactions.py --months 24 --accounts 3000
    python scripts/benchmark_load.py
"""

import io
import os
import time

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DSN = (
    f"host={os.getenv('PG_HOST', '127.0.0.1')} "
    f"dbname={os.getenv('PG_DB', 'perf_bench')} "
    f"user={os.getenv('PG_USER', 'postgres')} "
    f"password={os.environ['PG_PASSWORD']}"
)

COLS = [
    "transaction_id", "account_id", "bsb", "account_number",
    "transaction_date", "amount", "transaction_type",
    "merchant_name", "merchant_category", "merchant_state",
    "description", "balance_after", "channel", "status",
]


def load_execute_values(df: pd.DataFrame) -> float:
    """The original load method — execute_values, page_size=500."""
    records = list(df[COLS].itertuples(index=False, name=None))
    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            execute_values(
                cur,
                f"INSERT INTO raw.transactions ({', '.join(COLS)}) "
                "VALUES %s ON CONFLICT (transaction_id) DO NOTHING",
                records,
                page_size=500,
            )
            conn.commit()
            elapsed = time.perf_counter() - t0
    finally:
        conn.close()
    return elapsed


def load_copy(df: pd.DataFrame) -> float:
    """The current load method — COPY into a temp table, then upsert-safe INSERT SELECT."""
    buf = io.StringIO()
    df[COLS].to_csv(buf, index=False, header=False, sep="\t", na_rep="\\N")
    buf.seek(0)

    conn = psycopg2.connect(DSN)
    try:
        with conn.cursor() as cur:
            t0 = time.perf_counter()
            cur.execute(
                "CREATE TEMP TABLE tmp_transactions "
                "(LIKE raw.transactions INCLUDING DEFAULTS) ON COMMIT DROP"
            )
            cur.copy_expert(
                f"COPY tmp_transactions ({', '.join(COLS)}) "
                "FROM STDIN WITH (FORMAT csv, DELIMITER E'\\t', NULL '\\N')",
                buf,
            )
            cur.execute(
                f"INSERT INTO raw.transactions ({', '.join(COLS)}) "
                f"SELECT {', '.join(COLS)} FROM tmp_transactions "
                "ON CONFLICT (transaction_id) DO NOTHING"
            )
            conn.commit()
            elapsed = time.perf_counter() - t0
    finally:
        conn.close()
    return elapsed


def truncate():
    conn = psycopg2.connect(DSN)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE raw.transactions")
    conn.commit()
    conn.close()


def main():
    print("Loading CSV...")
    df = pd.read_csv("data/raw/transactions.csv", parse_dates=["transaction_date"])
    n = len(df)
    print(f"{n:,} rows loaded from CSV\n")

    print("=== Method A: execute_values(page_size=500) ===")
    truncate()
    t_a = load_execute_values(df)
    print(f"  {n:,} rows in {t_a:.2f}s  ({n / t_a:,.0f} rows/sec)\n")

    print("=== Method B: COPY FROM STDIN via temp table ===")
    truncate()
    t_b = load_copy(df)
    print(f"  {n:,} rows in {t_b:.2f}s  ({n / t_b:,.0f} rows/sec)\n")

    print("=== Summary ===")
    print(f"execute_values : {t_a:.2f}s")
    print(f"COPY           : {t_b:.2f}s")
    print(f"Speedup        : {t_a / t_b:.1f}x")


if __name__ == "__main__":
    if "PG_PASSWORD" not in os.environ:
        raise SystemExit("PG_PASSWORD env var required")
    main()
