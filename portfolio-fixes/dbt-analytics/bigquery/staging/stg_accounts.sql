with source as (
    select * from {{ source('raw', 'accounts') }}
),

cleaned as (
    select
        account_id,
        customer_id,
        bsb,
        account_number,
        upper(trim(account_type))       as account_type,
        cast(open_date as date)         as open_date,
        balance,
        credit_limit,
        loaded_at
    from source
    where account_id is not null
)

select * from cleaned
