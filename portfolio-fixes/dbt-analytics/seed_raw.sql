DROP SCHEMA IF EXISTS raw CASCADE;
CREATE SCHEMA raw;

CREATE TABLE raw.accounts (
    account_id text, customer_id text, bsb text, account_number text,
    account_type text, open_date date, balance numeric, credit_limit numeric, loaded_at timestamp
);
INSERT INTO raw.accounts
SELECT
    'ACC'||lpad(g::text,7,'0'),
    'CUS'||lpad(g::text,8,'0'),
    '062-000', lpad(g::text,10,'0'),
    (array['SAVINGS','TRANSACTION','OFFSET'])[1 + (g % 3)],
    date '2020-01-01' + (g*7),
    round((random()*50000)::numeric,2),
    case when g % 3 = 1 then round((random()*15000)::numeric,2) else null end,
    now()
FROM generate_series(1,20) g;

CREATE TABLE raw.transactions (
    transaction_id text, account_id text, bsb text, account_number text,
    transaction_date timestamp, amount numeric, transaction_type text,
    merchant_name text, merchant_category text, merchant_state text,
    description text, balance_after numeric, channel text, status text, loaded_at timestamp
);
INSERT INTO raw.transactions
SELECT
    gen_random_uuid()::text,
    'ACC'||lpad((1 + (s % 20))::text,7,'0'),
    '062-000', lpad((1 + (s % 20))::text,10,'0'),
    timestamp '2024-01-01' + (s % 360) * interval '1 day' + (s % 24) * interval '1 hour',
    round((10 + random()*900)::numeric,2),
    case when s % 20 = 0 then 'CREDIT' else 'DEBIT' end,
    (array['Woolworths','BP','Netflix','Amazon AU','Uber','AGL'])[1 + (s % 6)],
    (array['Supermarkets','Fuel','Entertainment','Online Shopping','Transport','Utilities'])[1 + (s % 6)],
    (array['NSW','VIC','QLD','WA'])[1 + (s % 4)],
    'desc', round((random()*20000)::numeric,2),
    (array['EFTPOS','ONLINE','ATM','BPAY'])[1 + (s % 4)],
    case when s % 50 = 0 then 'DECLINED' else 'SETTLED' end,
    now()
FROM generate_series(1,4000) s;
