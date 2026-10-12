"""
Reusable SQL query functions for the PhonePe Pulse project.

Design principle:
- Streamlit UI stays in app.py
- SQL stays here
- Database connection stays in db/connection.py

TABLES (created by phonepe_master.py)
-------------------------------------
aggregated_transaction  State NULL = country total, otherwise one state
aggregated_user         State NULL = country total, otherwise one state
aggregated_merchant     State NULL = country total, otherwise one state
map_transaction         one row per state / quarter (state totals)
map_user, map_merchant  one row per state / quarter
top_transaction         State + District (State NULL = country top list)

State names are stored lowercase with spaces
(e.g. "tamil nadu", "andaman & nicobar islands"), so comparisons
use plain equality and can use indexes.

IMPORTANT DATA RULE:
Category and district analysis uses Transaction_count.
State-level amounts come from map_transaction.
We do NOT invent or estimate missing transaction amounts.
"""

import streamlit as st

from db.connection import run_query

# Cache query results for an hour so widget changes don't hit
# PostgreSQL again for the same arguments.
CACHE_TTL = 3600


# ============================================================
# FILTER OPTIONS
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_years():
    """Return available years from the map transaction data."""
    df = run_query(
        'SELECT DISTINCT "Year" '
        'FROM map_transaction '
        'ORDER BY "Year"'
    )
    return df["Year"].tolist()


def get_quarters():
    """Return standard PhonePe Pulse quarters."""
    return [1, 2, 3, 4]


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_states():
    """Return available states/UTs from map transaction data."""
    df = run_query(
        'SELECT DISTINCT "State" '
        'FROM map_transaction '
        'ORDER BY "State"'
    )
    return df["State"].tolist()


# ============================================================
# GEOGRAPHICAL INSIGHTS
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_state_transaction_totals(year, quarter):
    """
    One row per state (map_transaction): count and amount.
    Used for the India map and the state summary table.
    """
    sql = """
        SELECT
            "State",
            COALESCE(SUM("Transaction_count"), 0)  AS "Transaction_count",
            COALESCE(SUM("Transaction_amount"), 0) AS "Transaction_amount"
        FROM map_transaction
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Transaction_amount" DESC
    """
    return run_query(sql, {"year": year, "quarter": quarter})


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_district_transaction_totals(state, year, quarter):
    """
    District-level transactions for one state (top_transaction).
    Ranked by Transaction_count.
    """
    sql = """
        SELECT
            "District",
            COALESCE(SUM("Transaction_count"), 0)  AS "Transaction_count",
            COALESCE(SUM("Transaction_amount"), 0) AS "Transaction_amount"
        FROM top_transaction
        WHERE "State" = :state
          AND "District" IS NOT NULL
          AND "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "District"
        ORDER BY "Transaction_count" DESC
    """
    return run_query(
        sql, {"state": state, "year": year, "quarter": quarter}
    )


# ============================================================
# PAYMENT PERFORMANCE (national)
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_transaction_type_breakdown(year, quarter):
    """National transaction counts by category (State IS NULL = country)."""
    sql = """
        SELECT
            "Transaction_type",
            SUM("Transaction_count") AS "Transaction_count"
        FROM aggregated_transaction
        WHERE "State" IS NULL
          AND "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "Transaction_type"
        ORDER BY "Transaction_count" DESC
    """
    return run_query(sql, {"year": year, "quarter": quarter})


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_payment_instrument_breakdown(year, quarter):
    """National transaction counts by payment instrument."""
    sql = """
        SELECT
            "Payment_instrument",
            SUM("Transaction_count") AS "Transaction_count"
        FROM aggregated_transaction
        WHERE "State" IS NULL
          AND "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "Payment_instrument"
        ORDER BY "Transaction_count" DESC
    """
    return run_query(sql, {"year": year, "quarter": quarter})


# ============================================================
# TRANSACTION TREND ANALYSIS
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_national_trend():
    """
    National trend: map_transaction state totals summed per quarter.
    """
    sql = """
        SELECT
            "Year",
            "Quarter",
            SUM("Transaction_count")  AS "Transaction_count",
            SUM("Transaction_amount") AS "Transaction_amount"
        FROM map_transaction
        GROUP BY "Year", "Quarter"
        ORDER BY "Year", "Quarter"
    """
    return run_query(sql)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_state_trend(state):
    """Year + Quarter trend for a selected state (map_transaction)."""
    sql = """
        SELECT
            "Year",
            "Quarter",
            SUM("Transaction_count")  AS "Transaction_count",
            SUM("Transaction_amount") AS "Transaction_amount"
        FROM map_transaction
        WHERE "State" = :state
        GROUP BY "Year", "Quarter"
        ORDER BY "Year", "Quarter"
    """
    return run_query(sql, {"state": state})


# ============================================================
# USER ENGAGEMENT
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_user_growth_by_state(year, quarter):
    """Registered users by state for a selected quarter."""
    sql = """
        SELECT
            "State",
            SUM("Registered_users") AS "Registered_users"
        FROM map_user
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Registered_users" DESC
    """
    return run_query(sql, {"year": year, "quarter": quarter})


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_national_user_trend():
    """
    National registered-user trend.
    aggregated_user holds country AND state rows, so only the
    country rows (State IS NULL) are used to avoid duplicates.
    """
    sql = """
        SELECT
            "Year",
            "Quarter",
            "Registered_users"
        FROM aggregated_user
        WHERE "State" IS NULL
        ORDER BY "Year", "Quarter"
    """
    return run_query(sql)


# ============================================================
# STATE RANKING
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_top_states(year, quarter, limit=10):
    """Top states by transaction amount."""
    sql = """
        SELECT
            "State",
            SUM("Transaction_amount") AS "Transaction_amount",
            SUM("Transaction_count")  AS "Transaction_count"
        FROM map_transaction
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Transaction_amount" DESC
        LIMIT :limit
    """
    return run_query(
        sql, {"year": year, "quarter": quarter, "limit": limit}
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_bottom_states(year, quarter, limit=10):
    """Bottom states by transaction amount."""
    sql = """
        SELECT
            "State",
            SUM("Transaction_amount") AS "Transaction_amount",
            SUM("Transaction_count")  AS "Transaction_count"
        FROM map_transaction
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Transaction_amount" ASC
        LIMIT :limit
    """
    return run_query(
        sql, {"year": year, "quarter": quarter, "limit": limit}
    )


# ============================================================
# MERCHANT INSIGHTS
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_merchant_growth_by_state(year, quarter):
    """Registered merchants by state (map_merchant)."""
    sql = """
        SELECT
            "State",
            SUM("Registered_merchants") AS "Registered_merchants"
        FROM map_merchant
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Registered_merchants" DESC
    """
    return run_query(sql, {"year": year, "quarter": quarter})


# ============================================================
# FUTURE WORK (placeholders)
# ============================================================

def get_customer_segments(year, quarter):
    """Placeholder for customer segmentation."""
    raise NotImplementedError


def get_fraud_flags(threshold_std=3):
    """Placeholder for anomaly detection."""
    raise NotImplementedError


# ============================================================
# TRANSACTION SUMMARY (used by app.py)
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_transaction_summary(state, year, quarter):
    """
    PhonePe-style summary for one state, year and quarter.

    Returns None when map_transaction has no row for the selection.
    Keys: State, Year, Quarter, Transaction_count, Transaction_amount,
          Average_transaction_value, Categories (DataFrame),
          Top_district (DataFrame)
    """
    params = {"state": state, "year": year, "quarter": quarter}

    # 1. State total ------------------------------------------------
    state_df = run_query(
        """
        SELECT
            "State", "Year", "Quarter",
            "Transaction_count", "Transaction_amount"
        FROM map_transaction
        WHERE "State" = :state
          AND "Year" = :year
          AND "Quarter" = :quarter
        LIMIT 1
        """,
        params,
    )

    if state_df.empty:
        return None

    # 2. Category breakdown (state rows of aggregated_transaction) ---
    category_df = run_query(
        """
        SELECT
            "Transaction_type",
            SUM("Transaction_count") AS "Transaction_count"
        FROM aggregated_transaction
        WHERE "State" = :state
          AND "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "Transaction_type"
        ORDER BY "Transaction_count" DESC
        """,
        params,
    )

    # 3. Top district ----------------------------------------------
    district_df = run_query(
        """
        SELECT
            "District",
            SUM("Transaction_count") AS "Transaction_count"
        FROM top_transaction
        WHERE "State" = :state
          AND "District" IS NOT NULL
          AND "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "District"
        ORDER BY "Transaction_count" DESC
        LIMIT 1
        """,
        params,
    )

    # 4. Build summary ---------------------------------------------
    row = state_df.iloc[0]

    transaction_count = float(row["Transaction_count"] or 0)
    transaction_amount = float(row["Transaction_amount"] or 0)

    average_transaction_value = (
        transaction_amount / transaction_count
        if transaction_count > 0
        else 0
    )

    return {
        "State": row["State"],
        "Year": int(row["Year"]),
        "Quarter": int(row["Quarter"]),
        "Transaction_count": transaction_count,
        "Transaction_amount": transaction_amount,
        "Average_transaction_value": average_transaction_value,
        "Categories": category_df,
        "Top_district": district_df,
    }