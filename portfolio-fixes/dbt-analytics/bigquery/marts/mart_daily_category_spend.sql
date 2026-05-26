{{ config(materialized='table') }}

with debits as (
    select *
    from {{ ref('stg_transactions') }}
    where transaction_type = 'DEBIT'
),

daily as (
    select
        transaction_date,
        merchant_category,
        channel,
        merchant_state,
        count(*)                            as transaction_count,
        cast(sum(amount) as numeric)        as total_spend,
        cast(avg(amount) as numeric)        as avg_transaction_value,
        count(distinct account_id)          as unique_accounts
    from debits
    group by 1, 2, 3, 4
),

ranked as (
    select
        *,
        rank() over (
            partition by transaction_date
            order by total_spend desc
        ) as spend_rank_for_day,
        cast(sum(total_spend) over (
            partition by date_trunc(transaction_date, MONTH), merchant_category
            order by transaction_date
            rows between unbounded preceding and current row
        ) as numeric) as cumulative_monthly_spend
    from daily
)

select * from ranked
