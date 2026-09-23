"""
PhonePe Pulse ETL Pipeline
==========================

Purpose
-------
Extract PhonePe Pulse JSON data, validate the extracted datasets, and load
the validated data into PostgreSQL.

Project structure
-----------------
phonepe_project/
│
├── phonepe_master.py
├── pulse/
│   └── data/
│       ├── aggregated/
│       ├── map/
│       └── top/
│
├── app/
│   ├── app.py
│   └── analysis/
│       └── queries.py
│
└── archive/

Database
--------
PostgreSQL
Database : phonepe_db
User     : postgres

Security
--------
PostgreSQL password is NOT stored in this file.
The password is requested manually when PostgreSQL loading starts
(or read from the PGPASSWORD environment variable if it is set).

Usage
-----
python phonepe_master.py           extract + validate + load PostgreSQL
python phonepe_master.py --test    extract + validate only (DB untouched)

Current validated dataset
-------------------------
9 tables
42,042 total rows

Source period
-------------
2018 Q1 through 2026 Q2
"""

import getpass
import json
import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

# ---------------------------------------------------------------- config
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "pulse" / "data"

DB = dict(host="localhost", port=5432, database="phonepe_db", username="postgres")
TEST_MODE = "--test" in sys.argv

EXPECTED = {
    "aggregated_merchant": 1212,
    "aggregated_transaction": 3773,
    "aggregated_user": 1258,
    "map_merchant": 1178,
    "map_transaction": 1224,
    "map_user": 1224,
    "top_merchant": 10413,
    "top_transaction": 10880,
    "top_user": 10880,
}
TABLES = list(EXPECTED)

LAYOUT = {
    "aggregated": ("aggregated", "{c}", "country", "india"),
    "map": ("map", "{c}", "hover", "country", "india"),
    "top": ("top", "{c}", "country", "india"),
}


# ---------------------------------------------------------------- database
def get_engine():
    """Ask for the password (hidden), build the engine and test the login."""
    password = os.getenv("PGPASSWORD") or getpass.getpass(
        f"PostgreSQL password for '{DB['username']}': "
    )
    engine = create_engine(URL.create("postgresql+psycopg2", password=password, **DB))
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        print(f"\nCould not connect to PostgreSQL:\n{str(exc).splitlines()[0]}")
        sys.exit(1)
    print("PostgreSQL connection OK")
    return engine


# ---------------------------------------------------------------- helpers
def norm(value):
    return None if value is None else str(value).strip().lower()


def files(kind, category):
    parts = [p.format(c=category) for p in LAYOUT[kind]]
    return sorted(DATA_DIR.joinpath(*parts).rglob("*.json"))


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("data") or {}


def meta(path):
    """Return (state or None, year, quarter) from the file path.

    State folders are hyphenated ("andaman-&-nicobar-islands") while JSON
    names use spaces, so hyphens become spaces to keep one spelling everywhere.
    """
    rel = path.relative_to(DATA_DIR).parts
    state = norm(path.parent.parent.name).replace("-", " ") if "state" in rel else None
    return state, int(path.parent.name), int(path.stem)


# ---------------------------------------------------------------- aggregated
# Folders hold country AND state files: State is kept (NULL = country total)
# so totals are never double counted.
def aggregated_merchant():
    rows = []
    for p in files("aggregated", "merchant"):
        state, y, q = meta(p)
        agg = read(p).get("aggregated") or {}
        rows.append([state, agg.get("registeredCount", 0), y, q])
    return pd.DataFrame(rows, columns=["State", "Registered_merchants", "Year", "Quarter"])


def aggregated_transaction():
    rows = []
    for p in files("aggregated", "transaction"):
        state, y, q = meta(p)
        for item in read(p).get("transactionData") or []:
            for inst in item.get("paymentInstruments") or []:
                rows.append([state, item.get("name"), inst.get("type"),
                             inst.get("count", 0), inst.get("amount", 0), y, q])
    return pd.DataFrame(rows, columns=[
        "State", "Transaction_type", "Payment_instrument",
        "Transaction_count", "Transaction_amount", "Year", "Quarter"])


def aggregated_user():
    rows = []
    for p in files("aggregated", "user"):
        state, y, q = meta(p)
        agg = read(p).get("aggregated") or {}
        rows.append([state, agg.get("registeredCount", 0), y, q])
    return pd.DataFrame(rows, columns=["State", "Registered_users", "Year", "Quarter"])


# ---------------------------------------------------------------- map
def map_merchant():
    rows = []
    for p in files("map", "merchant"):
        state, y, q = meta(p)
        if state:
            continue
        for name, m in (read(p).get("hoverData") or {}).items():
            m = m or {}
            rows.append([norm(name), m.get("registeredUsers", 0),
                         m.get("registeredMerchants", 0), y, q])
    return pd.DataFrame(rows, columns=[
        "State", "Registered_users", "Registered_merchants", "Year", "Quarter"])


def map_transaction():
    rows = []
    for p in files("map", "transaction"):
        state, y, q = meta(p)
        if state:
            continue
        for item in read(p).get("hoverDataList") or []:
            metrics = item.get("metric") or []
            if metrics:
                m = metrics[0]
                rows.append([norm(item.get("name")), m.get("count", 0),
                             m.get("amount", 0), y, q])
    return pd.DataFrame(rows, columns=[
        "State", "Transaction_count", "Transaction_amount", "Year", "Quarter"])


def map_user():
    rows = []
    for p in files("map", "user"):
        state, y, q = meta(p)
        if state:
            continue
        for name, m in (read(p).get("hoverData") or {}).items():
            rows.append([norm(name), (m or {}).get("registeredCount", 0), y, q])
    return pd.DataFrame(rows, columns=["State", "Registered_users", "Year", "Quarter"])


# ---------------------------------------------------------------- top
def top_table(category, type_col, count_col, amount_col=None):
    """Shared extractor for top_merchant / top_transaction / top_user.

    Country files -> top states (State set) + top districts (State NULL).
    State files   -> districts with their parent state.
    """
    rows = []
    for p in files("top", category):
        state, y, q = meta(p)
        data = read(p)
        groups = ("districts",) if state else ("states", "districts")
        for group in groups:
            for item in data.get(group) or []:
                name = norm(item.get("entityName"))
                m = item.get("metric") or {}
                if state:
                    s, d = state, name
                elif group == "states":
                    s, d = name, None
                else:
                    s, d = None, name
                row = [s, d, y, q, m.get("type", "TOTAL"), m.get("count", 0)]
                if amount_col:
                    row.append(m.get("amount", 0))
                rows.append(row)
    cols = ["State", "District", "Year", "Quarter", type_col, count_col]
    return pd.DataFrame(rows, columns=cols + ([amount_col] if amount_col else []))


def extract_all():
    print("\nExtracting...")
    return {
        "aggregated_merchant": aggregated_merchant(),
        "aggregated_transaction": aggregated_transaction(),
        "aggregated_user": aggregated_user(),
        "map_merchant": map_merchant(),
        "map_transaction": map_transaction(),
        "map_user": map_user(),
        "top_merchant": top_table("merchant", "Transaction_type", "Transaction_count", "Transaction_amount"),
        "top_transaction": top_table("transaction", "Transaction_type", "Transaction_count", "Transaction_amount"),
        "top_user": top_table("user", "User_type", "Registered_users"),
    }


# ---------------------------------------------------------------- validation
def check(label, actual, expected):
    ok = actual == expected
    print(f"{label:<34}{actual:>7} / {expected:<7}{'PASS' if ok else 'CHECK'}")
    return ok


def validate(data):
    print("\n" + "=" * 60 + "\nEXTRACTION VALIDATION\n" + "=" * 60)
    results = [check(t, len(data[t]), EXPECTED[t]) for t in TABLES]

    df = data["top_transaction"]
    has_d, has_s = df["District"].notna(), df["State"].notna()
    results += [
        check("top_transaction districts", has_d.sum(), 10540),
        check("State-linked districts", (has_d & has_s).sum(), 10200),
        check("Country top districts", (has_d & ~has_s).sum(), 340),
        check("Country state records", (has_s & ~has_d).sum(), 340),
        check("Duplicate top_transaction keys",
              df.duplicated(["State", "District", "Year", "Quarter"]).sum(), 0),
        check("Coimbatore records (34 quarters)",
              df["District"].str.contains("coimbatore district", na=False).sum(), 34),
    ]

    # State spelling must match between top and map tables (dashboard filters).
    mismatch = set(df["State"].dropna()) ^ set(data["map_transaction"]["State"])
    results.append(check("State names differ (top vs map)", len(mismatch), 0))
    if mismatch:
        print("  mismatched:", sorted(mismatch))

    # Informational: zero-filled columns usually mean a wrong JSON key.
    print("\nZero-value warnings (should be far below the row count):")
    for t, col in [("top_transaction", "Transaction_amount"),
                   ("top_merchant", "Transaction_amount"),
                   ("top_user", "Registered_users"),
                   ("map_transaction", "Transaction_amount"),
                   ("map_merchant", "Registered_merchants")]:
        print(f"  {t}.{col:<22}{(data[t][col] == 0).sum():>6} / {len(data[t])} rows are 0")
    return all(results)


def validate_database(engine, data):
    print("\n" + "=" * 60 + "\nPOSTGRESQL VALIDATION\n" + "=" * 60)
    with engine.connect() as conn:
        return all(
            check(t, conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar(), len(data[t]))
            for t in TABLES
        )


# ---------------------------------------------------------------- load
def load_database(data, engine):
    print("\nLoading PostgreSQL (single transaction)...")
    with engine.begin() as conn:
        for t in TABLES:
            data[t].to_sql(t, conn, if_exists="replace", index=False,
                           method="multi", chunksize=2000)
            print(f"  {t:<25}{len(data[t]):>7} rows")


# ---------------------------------------------------------------- main
def main():
    print("=" * 60 + f"\nPHONEPE PULSE ETL  |  {'TEST (no DB load)' if TEST_MODE else 'FULL LOAD'}\n" + "=" * 60)
    print(f"Data folder: {DATA_DIR}")
    if not DATA_DIR.exists():
        sys.exit(f"ERROR: data folder not found: {DATA_DIR}")

    data = extract_all()
    ok = validate(data)
    print("\nRESULT:", "ALL CHECKS PASSED" if ok else "SOME CHECKS DIFFER FROM EXPECTED")

    if TEST_MODE:
        print("Test mode: PostgreSQL was not modified.")
        return
    if not ok and input("Validation differs. Load anyway? (y/N): ").strip().lower() != "y":
        sys.exit("Load cancelled.")

    engine = get_engine()  # password requested here
    load_database(data, engine)
    db_ok = validate_database(engine, data)
    engine.dispose()
    print("\nETL COMPLETE" if db_ok else "\nLOAD FINISHED BUT ROW COUNTS DIFFER - CHECK")


if __name__ == "__main__":
    main()