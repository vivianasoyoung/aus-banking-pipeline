# BigQuery extension — what to do

Adds BigQuery as a SECOND dbt target alongside Postgres. Your local Postgres
setup + green CI stay exactly as they are. This just proves the same models
run on a cloud warehouse — the one gap reviewers notice.

## A. One-time BigQuery setup (~30 min, mostly clicking)

1. console.cloud.google.com → sign in → create project `cba-portfolio`.
2. Search "BigQuery" → it's already enabled.
3. Create a dataset named `raw` (location: US).
4. IAM & Admin → Service Accounts → Create:
   - name: `dbt-runner`
   - role: **BigQuery Admin**
   - After creating, open it → Keys → Add Key → JSON → download. Keep this file safe;
     NEVER commit it.
5. Load your data into the `raw` dataset:
   - In BigQuery console: dataset `raw` → Create table → Upload `accounts.csv` →
     table name `accounts`, check "Auto detect" schema. Repeat for `transactions.csv`
     → table `transactions`.

## B. Add the BigQuery target to your dbt profile

Edit `~/.dbt/profiles.yml` (NOT the repo's profiles.example.yml — that has no secrets).
Add a `bigquery` output under the existing `cba_dbt_analytics:`:

```yaml
    bigquery:
      type: bigquery
      method: service-account
      keyfile: /absolute/path/to/dbt-runner-key.json
      project: cba-portfolio          # your GCP project id
      dataset: analytics              # where marts/staging land
      threads: 4
      location: US
```

Also commit a sanitised example so reviewers see how it's wired — add this block to the
repo's `profiles.example.yml` (placeholders only, no real key path):

```yaml
    bigquery:
      type: bigquery
      method: service-account
      keyfile: "{{ env_var('DBT_BQ_KEYFILE') }}"
      project: "{{ env_var('DBT_BQ_PROJECT') }}"
      dataset: analytics
      threads: 4
      location: US
```

## C. Swap in the BigQuery-compatible models

BigQuery's SQL dialect differs from Postgres in a few spots (date_trunc argument
order, casts, dayofweek). The files in this folder are the adapted versions —
same logic, BigQuery syntax. Two ways to use them:

**Option 1 (simplest for a portfolio): a separate BigQuery branch/folder.**
Keep your `main` models as-is for Postgres. Copy these files over only when running
`--target bigquery`. Document the dialect differences in the README.

**Option 2 (cleaner, more advanced): make the models dialect-agnostic** using dbt's
cross-database macros (`dbt.date_trunc()`, `dbt.safe_cast()`). More work; optional.

For your portfolio, Option 1 is fine and faster. The adapted files here are drop-in
replacements when targeting BigQuery.

## D. Run it

```bash
cd cba_dbt_analytics
dbt deps
dbt build --target bigquery
```

Watch the marts get created in your BigQuery `analytics` dataset.

## E. Document + screenshot (the payoff)

1. README section:
   > **Runs on PostgreSQL (local) and BigQuery (cloud).** The same dbt models target
   > either warehouse via dbt profiles, demonstrating warehouse portability and cloud
   > data-warehouse experience.
2. Screenshot the BigQuery console showing the `analytics` dataset with your mart tables.
   Embed in the README.

## Dialect changes made (for your understanding + the blog post)

| Postgres | BigQuery |
| --- | --- |
| `date_trunc('month', col)` | `date_trunc(col, MONTH)` |
| `col::numeric(18,2)` | `cast(col as numeric)` |
| `extract(dow from col)` | `extract(dayofweek from col)` |
| `extract(hour from col)` | `extract(hour from col)` (same) |
| `abs / upper / trim / nullif / window fns` | identical |

## Heads-up: verify the timestamp column type

These models were dialect-adapted but NOT run against a live BigQuery (unlike the
Postgres versions, which were verified end-to-end). The most likely thing to need a
tweak is how `transaction_date` loads from CSV:

- If BigQuery auto-detect loads it as **TIMESTAMP/DATETIME** → everything works.
- If it loads as **STRING** (can happen with the `YYYY-MM-DD HH:MM:SS` format) →
  `extract(...)` and `cast(... as date)` will error. Fix by either:
  - Defining the schema explicitly on load (set `transaction_date` to TIMESTAMP), or
  - Wrapping with a parse in stg_transactions:
    `parse_timestamp('%Y-%m-%d %H:%M:%S', transaction_date)` before the date_trunc/extract.

When you run `dbt build --target bigquery`, if you hit an error, paste it and it's a
quick fix — almost certainly this column-type issue or a trivial syntax difference.

## Files in this folder
- `staging/stg_transactions.sql`, `staging/stg_accounts.sql`
- `intermediate/int_customer_monthly_category_spend.sql`, `int_customer_monthly_spend.sql`
- `marts/mart_customer_segments.sql`, `mart_category_trends.sql`,
  `marts/mart_monthly_summary.sql`, `marts/mart_daily_category_spend.sql`

(sources.yml and the _models.yml test files work unchanged on BigQuery — no edits needed.)
