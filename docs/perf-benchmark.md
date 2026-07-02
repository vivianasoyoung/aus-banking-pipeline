# Load Performance: execute_values vs COPY

## Why

The original `load_transactions()` used `execute_values(page_size=500)` —
fine for the ~95K-row default dataset in the Quick Start, but batched
`INSERT`s don't scale linearly. Wanted real numbers before deciding whether
it was worth the code change, rather than assuming.

## Method

1. Generated a larger synthetic dataset than the default demo size:
   `python scripts/generate_transactions.py --months 24 --accounts 3000`
   → 2,312,145 transaction rows.
2. Loaded that CSV into `raw.transactions` (schema unchanged, matching
   `docker/init.sql`) two ways, truncating the table between runs:
   - **A — execute_values**: the original code, `page_size=500`.
   - **B — COPY**: `COPY FROM STDIN` into a `CREATE TEMP TABLE ... LIKE
     raw.transactions`, then `INSERT ... SELECT ... ON CONFLICT DO NOTHING`
     from the temp table into `raw.transactions`. The temp-table step is
     necessary because `COPY` itself has no upsert/conflict-handling — the
     idempotency guarantee (`ON CONFLICT (transaction_id) DO NOTHING`) has
     to happen in a separate statement.
3. Ran on local Postgres 16, same machine, sequential (not concurrent) runs.
   Script: [`scripts/benchmark_load.py`](../scripts/benchmark_load.py).

## Results

| Method | Time | Rows/sec |
|---|---|---|
| `execute_values(page_size=500)` | 114.06s | 20,271 |
| `COPY` via temp table | 35.03s | 66,010 |

**3.3x speedup** at 2.3M rows. `load_transactions()` now uses the COPY-based
approach.

## Caveats

- Measured on local Postgres, not RDS — real network latency to a managed
  instance would add overhead to both methods, but shouldn't change which
  one wins, since the gap comes from statement-count/round-trip overhead
  (`execute_values` still issues one round trip per `page_size` batch —
  4,625 round trips at page_size=500 for this dataset — vs `COPY`'s single
  streamed transfer), not network distance.
- At the pipeline's actual daily volume (~95K rows in the Quick Start demo),
  the two methods are close enough that this wouldn't have been worth
  changing on its own. The gap only becomes material at scale — which is
  exactly the kind of thing worth measuring before optimizing, not assuming.
- `load_accounts()` and `load_quarantined_transactions()` were left as
  `execute_values` — both operate on far smaller row counts (accounts is
  bounded by customer count, quarantine is normally a small fraction of
  daily volume), so the same rewrite wouldn't pay for its added complexity
  there.
