{{ config(materialized='table') }}

with monthly as (
    select * from {{ ref('int_customer_monthly_category_spend') }}
),

trends as (
    select
        transaction_month,
        merchant_category,
        sum(transaction_count)                                                  as total_transactions,
        cast(sum(total_spend) as numeric)                                       as total_spend,
        cast(sum(total_spend) / nullif(sum(transaction_count), 0) as numeric)   as avg_transaction_value,
        count(distinct account_id)                                              as unique_customers,
        cast(sum(total_spend) / nullif(count(distinct account_id), 0) as numeric) as spend_per_customer
    from monthly
    group by 1, 2
)

select * from trends
order by transaction_month desc, total_spend desc
