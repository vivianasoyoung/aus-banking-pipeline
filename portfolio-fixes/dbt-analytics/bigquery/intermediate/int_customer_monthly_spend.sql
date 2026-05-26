with category_spend as (
    select * from {{ ref('int_customer_monthly_category_spend') }}
),

rolled_up as (
    select
        account_id,
        customer_id,
        account_type,
        transaction_month,
        sum(transaction_count)              as transaction_count,
        cast(sum(total_spend) as numeric)   as total_spend,
        count(distinct merchant_category)   as categories_used
    from category_spend
    group by 1, 2, 3, 4
)

select * from rolled_up
