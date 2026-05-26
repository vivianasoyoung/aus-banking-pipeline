with transactions as (
    select *
    from {{ ref('stg_transactions') }}
    where transaction_type = 'DEBIT'
),

accounts as (
    select * from {{ ref('stg_accounts') }}
),

aggregated as (
    select
        t.account_id,
        a.customer_id,
        a.account_type,
        t.transaction_month,
        t.merchant_category,
        count(*)                                as transaction_count,
        cast(sum(t.amount) as numeric)          as total_spend,
        cast(avg(t.amount) as numeric)          as avg_spend,
        cast(max(t.amount) as numeric)          as max_spend
    from transactions t
    left join accounts a using (account_id)
    group by 1, 2, 3, 4, 5
)

select * from aggregated
