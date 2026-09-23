import sys
import json
from pathlib import Path
from getpass import getpass

import pandas as pd
from sqlalchemy import create_engine, text

# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "pulse" / "data"

DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "phonepe_db"
DB_USER = "postgres"

TABLES = [
    "aggregated_merchant",
    "aggregated_transaction",
    "aggregated_user",
    "map_merchant",
    "map_transaction",
    "map_user",
    "top_merchant",
    "top_transaction",
    "top_user",
]

# ------------------------------------------------------------
# IMPORTANT: the map_* counts below are PLACEHOLDERS.
#
# Fix applied in this version: extract_map_merchant/transaction/user
# now skip nested per-state district files (the same fix
# extract_top_* already had), so map_* tables will now contain far
# FEWER rows than before -- roughly (num_states x num_year_quarters)
# instead of (num_states x num_year_quarters) + (num_districts x
# num_year_quarters).
#
# Run:   python phonepe_master.py --test
# first. It will print the ACTUAL new counts for map_merchant,
# map_transaction, map_user. Copy those three numbers into the dict
# below (replacing the "None" placeholders), then run the test again
# to confirm PASS, before running the full load.
# ------------------------------------------------------------
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

# ============================================================
# HELPERS
# ============================================================

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def year_quarter(path):
    return int(path.parent.name), int(path.stem)


def normalize_state(value):
    if value is None:
        return None
    return str(value).strip().lower()


def country_files(category):
    base = DATA_DIR / "aggregated" / category / "country" / "india"
    return sorted(base.rglob("*.json"))


def map_files(category):
    base = DATA_DIR / "map" / category / "hover" / "country" / "india"
    return sorted(base.rglob("*.json"))


def top_files(category):
    base = DATA_DIR / "top" / category / "country" / "india"
    return sorted(base.rglob("*.json"))


# ============================================================
# AGGREGATED / MERCHANT
# ============================================================

def extract_aggregated_merchant():
    rows = []

    for path in country_files("merchant"):
        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})
        aggregated = data.get("aggregated", {})

        rows.append([
            "India",
            year,
            quarter,
            aggregated.get("registeredCount", 0),
        ])

    return pd.DataFrame(
        rows,
        columns=[
            "Country",
            "Year",
            "Quarter",
            "Registered_merchants",
        ],
    )


# ============================================================
# AGGREGATED / TRANSACTION
# ============================================================

def extract_aggregated_transaction():
    rows = []

    for path in country_files("transaction"):
        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})

        for item in data.get("transactionData", []):
            transaction_type = item.get("name")

            for instrument in item.get(
                "paymentInstruments", []
            ):
                rows.append([
                    "India",
                    year,
                    quarter,
                    transaction_type,
                    instrument.get("type"),
                    instrument.get("count", 0),
                    instrument.get("amount", 0),
                ])

    return pd.DataFrame(
        rows,
        columns=[
            "Country",
            "Year",
            "Quarter",
            "Transaction_type",
            "Payment_instrument",
            "Transaction_count",
            "Transaction_amount",
        ],
    )


# ============================================================
# AGGREGATED / USER
# ============================================================

def extract_aggregated_user():
    rows = []

    for path in country_files("user"):
        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})
        aggregated = data.get("aggregated", {})

        rows.append([
            "India",
            year,
            quarter,
            aggregated.get("registeredUsers", 0),
        ])

    return pd.DataFrame(
        rows,
        columns=[
            "Country",
            "Year",
            "Quarter",
            "Registered_users",
        ],
    )


# ============================================================
# MAP / MERCHANT
# ============================================================

def extract_map_merchant():
    rows = []

    for path in map_files("merchant"):
        # FIX: skip nested per-state district-level files. Only the
        # top-level country/india/<year>/<quarter>.json files hold
        # true state-level hover data; anything under a "state"
        # folder is district-level and belongs to top_merchant, not
        # here.
        if "state" in path.parts:
            continue

        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})
        hover = data.get("hoverData", {})

        for state, values in hover.items():
            rows.append([
                normalize_state(state),
                year,
                quarter,
                values.get("registeredCount", 0),
            ])

    return pd.DataFrame(
        rows,
        columns=[
            "State",
            "Year",
            "Quarter",
            "Registered_merchants",
        ],
    )


# ============================================================
# MAP / TRANSACTION
# ============================================================

def extract_map_transaction():
    rows = []

    for path in map_files("transaction"):
        # FIX: same as extract_map_merchant() above -- skip nested
        # per-state district-level files.
        if "state" in path.parts:
            continue

        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})
        hover = data.get("hoverDataList", [])

        for item in hover:
            state = normalize_state(item.get("name"))

            for metric in item.get("metric", []):
                rows.append([
                    state,
                    year,
                    quarter,
                    metric.get("count", 0),
                    metric.get("amount", 0),
                ])

    return pd.DataFrame(
        rows,
        columns=[
            "State",
            "Year",
            "Quarter",
            "Transaction_count",
            "Transaction_amount",
        ],
    )


# ============================================================
# MAP / USER
# ============================================================

def extract_map_user():
    rows = []

    for path in map_files("user"):
        # FIX: same as extract_map_merchant() above -- skip nested
        # per-state district-level files.
        if "state" in path.parts:
            continue

        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})
        hover = data.get("hoverData", {})

        for state, values in hover.items():
            rows.append([
                normalize_state(state),
                year,
                quarter,
                values.get("registeredCount", 0),
            ])

    return pd.DataFrame(
        rows,
        columns=[
            "State",
            "Year",
            "Quarter",
            "Registered_users",
        ],
    )


# ============================================================
# TOP / MERCHANT
# ============================================================

def extract_top_merchant():
    rows = []

    for path in top_files("merchant"):
        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})

        is_state_file = "state" in path.parts

        # Country-level file contains state records.
        if not is_state_file:
            for item in data.get("states", []):
                rows.append([
                    normalize_state(item.get("name")),
                    None,
                    year,
                    quarter,
                    item.get("registeredCount", 0),
                ])

        # State-level file contains district records.
        parent_state = None

        if is_state_file:
            parent_state = normalize_state(
                path.parent.parent.name
            )

        for item in data.get("districts", []):
            rows.append([
                parent_state,
                item.get("name"),
                year,
                quarter,
                item.get("registeredCount", 0),
            ])

    return pd.DataFrame(
        rows,
        columns=[
            "State",
            "District",
            "Year",
            "Quarter",
            "Registered_merchants",
        ],
    )


# ============================================================
# TOP / TRANSACTION
# ============================================================

def extract_top_transaction():
    rows = []

    for path in top_files("transaction"):
        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})

        is_state_file = "state" in path.parts

        # Country-level state records.
        if not is_state_file:
            for item in data.get("states", []):
                metric = item.get("metric", {})

                rows.append([
                    normalize_state(
                        item.get("entityName")
                    ),
                    None,
                    year,
                    quarter,
                    metric.get("type"),
                    metric.get("count", 0),
                    metric.get("amount", 0),
                ])

        # State-level district records.
        parent_state = None

        if is_state_file:
            parent_state = normalize_state(
                path.parent.parent.name
            )

        for item in data.get("districts", []):
            metric = item.get("metric", {})

            rows.append([
                parent_state,
                item.get("entityName"),
                year,
                quarter,
                metric.get("type"),
                metric.get("count", 0),
                metric.get("amount", 0),
            ])

    return pd.DataFrame(
        rows,
        columns=[
            "State",
            "District",
            "Year",
            "Quarter",
            "Transaction_type",
            "Transaction_count",
            "Transaction_amount",
        ],
    )


# ============================================================
# TOP / USER
# ============================================================

def extract_top_user():
    rows = []

    for path in top_files("user"):
        year, quarter = year_quarter(path)
        data = load_json(path).get("data", {})

        is_state_file = "state" in path.parts

        # Country-level state records.
        if not is_state_file:
            for item in data.get("states", []):
                rows.append([
                    normalize_state(item.get("name")),
                    None,
                    year,
                    quarter,
                    item.get("registeredCount", 0),
                ])

        # State-level district records.
        parent_state = None

        if is_state_file:
            parent_state = normalize_state(
                path.parent.parent.name
            )

        for item in data.get("districts", []):
            rows.append([
                parent_state,
                item.get("name"),
                year,
                quarter,
                item.get("registeredCount", 0),
            ])

    return pd.DataFrame(
        rows,
        columns=[
            "State",
            "District",
            "Year",
            "Quarter",
            "Registered_users",
        ],
    )


# ============================================================
# EXTRACT ALL
# ============================================================

def extract_all():
    return {
        "aggregated_merchant":
            extract_aggregated_merchant(),

        "aggregated_transaction":
            extract_aggregated_transaction(),

        "aggregated_user":
            extract_aggregated_user(),

        "map_merchant":
            extract_map_merchant(),

        "map_transaction":
            extract_map_transaction(),

        "map_user":
            extract_map_user(),

        "top_merchant":
            extract_top_merchant(),

        "top_transaction":
            extract_top_transaction(),

        "top_user":
            extract_top_user(),
    }


# ============================================================
# EXTRACTION VALIDATION
# ============================================================

def validate_extraction(data):
    print("\nEXTRACTION VALIDATION")
    print("-" * 70)

    passed = True
    total = 0

    for table in TABLES:
        actual = len(data[table])
        expected = EXPECTED[table]
        total += actual

        if expected is None:
            status = "NO BASELINE YET"
        else:
            status = "PASS" if actual == expected else "FAIL"
            if actual != expected:
                passed = False

        expected_display = expected if expected is not None else "?"

        print(
            f"{table:<25}"
            f"{actual:>8} / {str(expected_display):<8}"
            f"{status}"
        )

    print("-" * 70)
    print(f"{'TOTAL':<25}{total:>8}")

    # If any EXPECTED value is still None, we can't fully validate yet --
    # that's expected on the first run after the map_* fix. Tell the
    # user explicitly instead of silently passing or failing.
    if any(v is None for v in EXPECTED.values()):
        print(
            "\nNOTE: Some EXPECTED counts are still 'None' (placeholders "
            "after the map_* fix). Copy the 'actual' numbers above for "
            "map_merchant, map_transaction, map_user into the EXPECTED "
            "dict at the top of this file, then re-run to get a real "
            "PASS/FAIL."
        )
        return False

    return passed


# ============================================================
# POSTGRESQL CONNECTION
# ============================================================

def create_db_engine():
    password = getpass("PostgreSQL password: ")

    url = (
        f"postgresql+psycopg2://"
        f"{DB_USER}:{password}@"
        f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )

    engine = create_engine(
        url,
        pool_pre_ping=True,
    )

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    return engine


# ============================================================
# DATABASE LOAD
# ============================================================

def load_database(engine, data):
    print("\nPOSTGRESQL LOAD")
    print("-" * 70)

    for table in TABLES:
        df = data[table]

        print(
            f"{table:<25}"
            f"{len(df):>8} records ... ",
            end="",
            flush=True,
        )

        df.to_sql(
            table,
            engine,
            if_exists="replace",
            index=False,
            chunksize=5000,
            method="multi",
        )

        print("DONE")


# ============================================================
# DATABASE VALIDATION
# ============================================================

def validate_database(engine, data):
    print("\nDATABASE VALIDATION")
    print("-" * 70)

    passed = True

    with engine.connect() as conn:
        for table in TABLES:
            actual = conn.execute(
                text(
                    f'SELECT COUNT(*) '
                    f'FROM "{table}"'
                )
            ).scalar()

            expected = len(data[table])

            status = (
                "PASS"
                if actual == expected
                else "FAIL"
            )

            if actual != expected:
                passed = False

            print(
                f"{table:<25}"
                f"{actual:>8} / {expected:<8}"
                f"{status}"
            )

    return passed


# ============================================================
# TEST MODE
# ============================================================

def test_mode():
    print("\nPHONEPE MASTER ETL - TEST MODE")
    print("=" * 70)
    print("PostgreSQL will NOT be modified.")

    data = extract_all()

    if validate_extraction(data):
        print("\nTEST RESULT : PASSED")
    else:
        print("\nTEST RESULT : see notes above.")
        print("PostgreSQL was NOT modified.")
        sys.exit(1)


# ============================================================
# FULL ETL
# ============================================================

def main():
    print("\nPHONEPE MASTER ETL")
    print("=" * 70)
    print(f"Source: {DATA_DIR}")

    if not DATA_DIR.exists():
        print("\nERROR: Source directory not found.")
        sys.exit(1)

    print("\nExtracting data...")
    data = extract_all()

    if not validate_extraction(data):
        print("\nETL STOPPED.")
        print("PostgreSQL was NOT modified.")
        sys.exit(1)

    print("\nExtraction successful.")
    print("Connecting to PostgreSQL...")

    try:
        engine = create_db_engine()
    except Exception as error:
        print("\nERROR: PostgreSQL connection failed.")
        print(error)
        sys.exit(1)

    try:
        load_database(engine, data)

        if not validate_database(engine, data):
            print("\nDATABASE VALIDATION : FAILED")
            sys.exit(1)

        print("\n" + "=" * 70)
        print("MASTER ETL STATUS : SUCCESS")
        print("=" * 70)

    except Exception as error:
        print("\nERROR:", error)
        sys.exit(1)

    finally:
        engine.dispose()


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":
    if "--test" in sys.argv:
        test_mode()
    else:
        main()