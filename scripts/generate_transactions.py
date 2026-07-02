"""
generate_transactions.py
------------------------
Generates realistic Australian banking transaction data
modelled on Australian retail banking account and transaction structures.

Usage:
    python scripts/generate_transactions.py --months 6 --accounts 500
"""

import argparse
import csv
import os
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker

fake = Faker('en_AU')
random.seed(42)

# ── Australian merchant categories and realistic names ──────────────────────
MERCHANT_PROFILES = {
    "Supermarkets": {
        "merchants": ["Woolworths", "Coles", "ALDI", "IGA", "Harris Farm Markets"],
        "avg_amount": 85,
        "std_dev": 45,
        "frequency": 0.18,
        "channels": ["EFTPOS"],
    },
    "Restaurants & Cafes": {
        "merchants": ["The Coffee Club", "Guzman y Gomez", "Nando's", "Boost Juice",
                      "Local Café", "McDonald's", "KFC", "Subway", "Zambrero"],
        "avg_amount": 28,
        "std_dev": 18,
        "frequency": 0.14,
        "channels": ["EFTPOS", "ONLINE"],
    },
    "Fuel": {
        "merchants": ["BP", "Shell", "Caltex", "7-Eleven", "Ampol"],
        "avg_amount": 95,
        "std_dev": 30,
        "frequency": 0.07,
        "channels": ["EFTPOS"],
    },
    "Online Shopping": {
        "merchants": ["Amazon AU", "eBay", "The Iconic", "Catch.com.au",
                      "Kogan", "JB Hi-Fi Online", "Bunnings Online"],
        "avg_amount": 75,
        "std_dev": 60,
        "frequency": 0.10,
        "channels": ["ONLINE"],
    },
    "Transport": {
        "merchants": ["Opal Card", "Myki", "Uber", "DiDi", "13Cabs", "Translink"],
        "avg_amount": 18,
        "std_dev": 12,
        "frequency": 0.09,
        "channels": ["ONLINE", "EFTPOS"],
    },
    "Utilities": {
        "merchants": ["AGL Energy", "Origin Energy", "Sydney Water",
                      "Optus", "Telstra", "Vodafone", "iiNet"],
        "avg_amount": 140,
        "std_dev": 60,
        "frequency": 0.05,
        "channels": ["BPAY", "ONLINE"],
    },
    "Healthcare": {
        "merchants": ["Chemist Warehouse", "Priceline Pharmacy",
                      "Bulk Billing Medical", "Capital Pathology", "Medicare"],
        "avg_amount": 35,
        "std_dev": 25,
        "frequency": 0.06,
        "channels": ["EFTPOS", "ONLINE"],
    },
    "Entertainment": {
        "merchants": ["Netflix", "Spotify", "Disney+", "Event Cinemas",
                      "Hoyts", "Stan", "Apple iTunes"],
        "avg_amount": 20,
        "std_dev": 10,
        "frequency": 0.07,
        "channels": ["ONLINE"],
    },
    "Retail": {
        "merchants": ["Kmart", "Target", "Big W", "Myer", "David Jones",
                      "Cotton On", "Uniqlo", "H&M"],
        "avg_amount": 65,
        "std_dev": 50,
        "frequency": 0.08,
        "channels": ["EFTPOS", "ONLINE"],
    },
    "ATM Withdrawal": {
        "merchants": ["Big 4 ATM", "Westpac ATM", "NAB ATM", "ANZ ATM"],
        "avg_amount": 200,
        "std_dev": 100,
        "frequency": 0.06,
        "channels": ["ATM"],
    },
    "Insurance": {
        "merchants": ["CommInsure", "NRMA Insurance", "AAMI", "Bupa", "Medibank"],
        "avg_amount": 180,
        "std_dev": 80,
        "frequency": 0.03,
        "channels": ["BPAY", "ONLINE"],
    },
    "Education": {
        "merchants": ["University of Sydney", "UNSW", "Monash University",
                      "RMIT", "Coursera", "Udemy"],
        "avg_amount": 250,
        "std_dev": 200,
        "frequency": 0.02,
        "channels": ["BPAY", "ONLINE"],
    },
    "Salary": {
        "merchants": ["Employer Payroll"],
        "avg_amount": 4200,
        "std_dev": 1500,
        "frequency": 0.05,
        "channels": ["ONLINE"],
    },
}

AU_STATES = ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "ACT", "NT"]
AU_BSBS = {
    "NSW": ["062-000", "062-100", "062-200", "033-000", "032-000"],
    "VIC": ["063-000", "063-100", "013-000", "083-000"],
    "QLD": ["064-000", "064-100", "014-000", "124-000"],
    "WA":  ["066-000", "016-000", "036-000"],
    "SA":  ["065-000", "015-000", "105-000"],
    "TAS": ["067-000", "017-000"],
    "ACT": ["062-900", "032-900"],
    "NT":  ["065-900"],
}
ACCOUNT_TYPES = ["SAVINGS", "TRANSACTION", "OFFSET"]


def generate_accounts(n: int) -> list[dict]:
    accounts = []
    for _ in range(n):
        state = random.choice(AU_STATES)
        bsb = random.choice(AU_BSBS[state])
        acc_type = random.choices(
            ACCOUNT_TYPES, weights=[0.4, 0.5, 0.1]
        )[0]
        balance = round(random.uniform(500, 80000), 2)
        accounts.append({
            "account_id":    f"ACC{fake.numerify(text='#######')}",
            "customer_id":   f"CUS{fake.numerify(text='########')}",
            "bsb":           bsb,
            "account_number": fake.numerify(text="##########"),
            "account_type":  acc_type,
            "open_date":     fake.date_between(start_date="-5y", end_date="-6m"),
            "balance":       balance,
            "credit_limit":  round(random.uniform(2000, 20000), 2) if acc_type == "TRANSACTION" else None,
        })
    return accounts


def pick_category() -> str:
    categories = list(MERCHANT_PROFILES.keys())
    weights = [MERCHANT_PROFILES[c]["frequency"] for c in categories]
    return random.choices(categories, weights=weights)[0]


def generate_transactions(accounts: list[dict], months: int) -> list[dict]:
    transactions = []
    end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_date = end_date - timedelta(days=30 * months)

    for account in accounts:
        current_balance = account["balance"]
        # Each account gets between 3–12 transactions per week
        txn_count = int((months * 4.3) * random.randint(3, 12))

        for _ in range(txn_count):
            category = pick_category()
            profile = MERCHANT_PROFILES[category]
            merchant = random.choice(profile["merchants"])
            channel = random.choice(profile["channels"])

            # Generate realistic amount — clamp to avoid negatives
            raw_amount = abs(
                random.gauss(profile["avg_amount"], profile["std_dev"])
            )
            amount = round(max(0.50, raw_amount), 2)

            is_credit = category == "Salary"
            txn_type = "CREDIT" if is_credit else "DEBIT"
            signed_amount = amount if is_credit else -amount
            current_balance = round(current_balance + signed_amount, 2)

            # Random timestamp within date range, weighted toward business hours
            txn_date = start_date + timedelta(
                seconds=random.randint(0, int((end_date - start_date).total_seconds()))
            )

            # ~2% of transactions are pending, ~1% declined
            status = random.choices(
                ["SETTLED", "PENDING", "DECLINED"],
                weights=[0.97, 0.02, 0.01]
            )[0]

            transactions.append({
                "transaction_id":   str(uuid.uuid4()),
                "account_id":       account["account_id"],
                "bsb":              account["bsb"],
                "account_number":   account["account_number"],
                "transaction_date": txn_date.strftime("%Y-%m-%d %H:%M:%S"),
                "amount":           amount,
                "transaction_type": txn_type,
                "merchant_name":    merchant,
                "merchant_category": category,
                "merchant_state":   random.choice(AU_STATES),
                "description":      f"{merchant} - {channel}",
                "balance_after":    current_balance,
                "channel":          channel,
                "status":           status,
            })

    # Sort by date ascending
    transactions.sort(key=lambda x: x["transaction_date"])
    return transactions


def write_csv(data: list[dict], filepath: str):
    if not data:
        return
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"  Written {len(data):,} rows → {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic Australian retail banking data")
    parser.add_argument("--months",   type=int, default=6,   help="Months of history to generate")
    parser.add_argument("--accounts", type=int, default=500,  help="Number of accounts")
    parser.add_argument("--out",      type=str, default="data/raw", help="Output directory")
    args = parser.parse_args()

    print(f"\nGenerating {args.accounts} accounts across {args.months} months of history...\n")

    accounts = generate_accounts(args.accounts)
    write_csv(accounts, os.path.join(args.out, "accounts.csv"))

    transactions = generate_transactions(accounts, args.months)
    write_csv(transactions, os.path.join(args.out, "transactions.csv"))

    print(f"\nDone. {len(transactions):,} transactions generated.")
    print(f"Avg transactions per account: {len(transactions) // args.accounts:,}")


if __name__ == "__main__":
    main()
