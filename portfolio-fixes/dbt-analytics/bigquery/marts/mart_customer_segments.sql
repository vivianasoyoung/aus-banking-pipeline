{{ config(materialized='table') }}

with monthly as (
    select * from {{ ref('int_customer_monthly_spend') }}
),

bounds as (
    select
        date_trunc(max(transaction_month), MONTH)                          as latest_month,
        date_sub(date_trunc(max(transaction_month), MONTH), interval 11 month) as earliest_month
    from monthly
),

per_account as (
    select
        m.account_id,
        m.customer_id,
        m.account_type,
        cast(sum(m.total_spend) as numeric)                                  as lifetime_spend,
        cast(sum(case when m.transaction_month >= b.earliest_month
                      then m.total_spend else 0 end) as numeric)             as spend_12m,
        count(distinct case when m.transaction_month >= b.earliest_month
                            then m.transaction_month end)                    as active_months_12m,
        cast(max(m.total_spend) as numeric)                                  as best_month_spend,
        max(m.categories_used)                                               as max_categories_in_month
    from monthly m
    cross join bounds b
    group by 1, 2, 3
),

with_avg as (
    select
        *,
        cast(spend_12m / 12.0 as numeric) as avg_monthly_spend
    from per_account
),

segmented as (
    select
        *,
        case
            when avg_monthly_spend >= 5000 then 'Premium'
            when avg_monthly_spend >= 2000 then 'High Value'
            when avg_monthly_spend >= 500  then 'Regular'
            else 'Low Activity'
        end as customer_segment
    from with_avg
)

select * from segmented
