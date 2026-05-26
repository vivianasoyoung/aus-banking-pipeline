{{ config(materialized='table') }}

with monthly as (
    select * from {{ ref('int_customer_monthly_spend') }}
),

summary as (
    select
        transaction_month,
        count(distinct account_id)                                              as active_accounts,
        count(distinct customer_id)                                             as active_customers,
        sum(transaction_count)                                                  as total_transactions,
        cast(sum(total_spend) as numeric)                                       as total_spend,
        cast(sum(total_spend) / nullif(sum(transaction_count), 0) as numeric)   as avg_transaction_value
    from monthly
    group by 1
)

select * from summary
order by transaction_month desc
