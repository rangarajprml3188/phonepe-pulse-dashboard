"""
Reusable SQL query functions for the PhonePe Pulse project.

Design principle:
- Streamlit UI stays in app.py
- SQL stays here
- Database connection stays in db/connection.py

IMPORTANT DATA RULE:
The local PhonePe aggregated transaction JSON files contain
transaction counts but, in this project dataset, transaction
amounts are NULL.

Therefore:
- Category analysis uses Transaction_count
- State-level total amount comes from map_transaction
- District-level analysis uses Transaction_count
- National transaction amount trend comes from map_transaction

We do NOT invent or estimate missing transaction amounts.
"""

from db.connection import run_query


# ============================================================
# FILTER OPTIONS
# ============================================================

def get_years():
    """
    Return available years from the PhonePe map transaction data.
    """
    df = run_query(
        'SELECT DISTINCT "Year" '
        'FROM map_transaction '
        'ORDER BY "Year"'
    )
    return df["Year"].tolist()


def get_quarters():
    """
    Return standard PhonePe Pulse quarters.
    """
    return [1, 2, 3, 4]


def get_states():
    """
    Return available states/UTs from map transaction data.
    """
    df = run_query(
        'SELECT DISTINCT "State" '
        'FROM map_transaction '
        'ORDER BY "State"'
    )
    return df["State"].tolist()


# ============================================================
# GEOGRAPHICAL INSIGHTS
# ============================================================

def get_state_transaction_totals(year, quarter):
    """
    One row per state.

    Source:
        map_transaction

    Provides:
        - Transaction count
        - Transaction amount

    This is the correct source for the state-level map because
    PhonePe's Map transaction data contains total count and value.
    """

    sql = """
        SELECT
            "State",
            SUM("Transaction_count") AS "Transaction_count",
            SUM("Transaction_amount") AS "Transaction_amount"
        FROM map_transaction
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Transaction_amount" DESC
    """

    return run_query(
        sql,
        {
            "year": year,
            "quarter": quarter,
        },
    )


def get_district_transaction_totals(state, year, quarter):
    """
    District-level transaction analysis.

    IMPORTANT:
    The local aggregated/top transaction JSON data has NULL
    transaction amounts.

    Therefore this query ranks districts by Transaction_count,
    not Transaction_amount.
    """

    sql = """
        SELECT
            "District",
            SUM("Transaction_count") AS "Transaction_count",
            SUM("Transaction_amount") AS "Transaction_amount"
        FROM top_transaction
        WHERE "State" = :state
          AND "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "District"
        ORDER BY "Transaction_count" DESC
    """

    return run_query(
        sql,
        {
            "state": state,
            "year": year,
            "quarter": quarter,
        },
    )


# ============================================================
# PAYMENT PERFORMANCE
# ============================================================

def get_transaction_type_breakdown(year, quarter):
    query = """
        SELECT
            "Transaction_type",
            SUM("Transaction_count") AS "Transaction_count"
        FROM aggregated_transaction_country
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "Transaction_type"
        ORDER BY "Transaction_count" DESC
    """

    return run_query(
        query,
        {
            "year": year,
            "quarter": quarter
        }
    )

def get_payment_instrument_breakdown(year, quarter):
    query = """
        SELECT
            "Payment_instrument",
            SUM("Transaction_count") AS "Transaction_count"
        FROM aggregated_transaction_country
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "Payment_instrument"
        ORDER BY "Transaction_count" DESC
    """

    return run_query(
        query,
        {
            "year": year,
            "quarter": quarter
        }
    )


# ============================================================
# TRANSACTION TREND ANALYSIS
# ============================================================

def get_national_trend():
    """
    National transaction trend.

    IMPORTANT:
    Do NOT use aggregated_transaction_country for amount because
    the local aggregated transaction amounts are NULL.

    Instead:
        map_transaction
        -> state totals
        -> summed to national level

    This gives us the real national transaction amount.
    """

    sql = """
        SELECT
            "Year",
            "Quarter",
            SUM("Transaction_count") AS "Transaction_count",
            SUM("Transaction_amount") AS "Transaction_amount"
        FROM map_transaction
        GROUP BY
            "Year",
            "Quarter"
        ORDER BY
            "Year",
            "Quarter"
    """

    return run_query(sql)


def get_state_trend(state):
    """
    Year + Quarter trend for a selected state.

    Source:
        map_transaction

    Provides real state-level transaction amount.
    """

    sql = """
        SELECT
            "Year",
            "Quarter",
            SUM("Transaction_count") AS "Transaction_count",
            SUM("Transaction_amount") AS "Transaction_amount"
        FROM map_transaction
        WHERE "State" = :state
        GROUP BY
            "Year",
            "Quarter"
        ORDER BY
            "Year",
            "Quarter"
    """

    return run_query(
        sql,
        {
            "state": state,
        },
    )


# ============================================================
# USER ENGAGEMENT
# ============================================================

def get_user_growth_by_state(year, quarter):
    """
    Registered users by state for a selected quarter.
    """

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

    return run_query(
        sql,
        {
            "year": year,
            "quarter": quarter,
        },
    )


def get_national_user_trend():
    """
    National registered-user trend.
    """

    sql = """
        SELECT
            "Year",
            "Quarter",
            "Registered_users"
        FROM aggregated_user
        ORDER BY
            "Year",
            "Quarter"
    """

    return run_query(sql)


# ============================================================
# STATE RANKING
# ============================================================

def get_top_states(year, quarter, limit=10):
    """
    Top states by transaction amount.
    """

    sql = """
        SELECT
            "State",
            SUM("Transaction_amount") AS "Transaction_amount",
            SUM("Transaction_count") AS "Transaction_count"
        FROM map_transaction
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Transaction_amount" DESC
        LIMIT :limit
    """

    return run_query(
        sql,
        {
            "year": year,
            "quarter": quarter,
            "limit": limit,
        },
    )


def get_bottom_states(year, quarter, limit=10):
    """
    Bottom states by transaction amount.
    """

    sql = """
        SELECT
            "State",
            SUM("Transaction_amount") AS "Transaction_amount",
            SUM("Transaction_count") AS "Transaction_count"
        FROM map_transaction
        WHERE "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Transaction_amount" ASC
        LIMIT :limit
    """

    return run_query(
        sql,
        {
            "year": year,
            "quarter": quarter,
            "limit": limit,
        },
    )


# ============================================================
# MERCHANT INSIGHTS
# ============================================================

def get_merchant_growth_by_state(year, quarter):
    """
    Registered merchants by state.

    Uses map_merchant.
    """

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

    return run_query(
        sql,
        {
            "year": year,
            "quarter": quarter,
        },
    )


# ============================================================
# CUSTOMER SEGMENTATION
# ============================================================

def get_customer_segments(year, quarter):
    """
    Placeholder for future customer segmentation work.

    We will implement this after the core dashboard is stable.
    """

    raise NotImplementedError


# ============================================================
# FRAUD / ANOMALY ANALYSIS
# ============================================================

def get_fraud_flags(threshold_std=3):
    """
    Placeholder for future anomaly detection.

    We will implement this after the core dashboard is stable.
    """

    raise NotImplementedError
def get_transaction_summary(state, year, quarter):
    """
    Returns the PhonePe-style transaction summary
    for a selected state, year and quarter.
    """

    # ---------------------------------------------------------
    # 1. STATE TOTAL
    # ---------------------------------------------------------
    state_query = """
        SELECT
            "State",
            "Year",
            "Quarter",
            "Transaction_count",
            "Transaction_amount"
        FROM map_transaction
        WHERE LOWER("State") = LOWER(:state)
          AND "Year" = :year
          AND "Quarter" = :quarter
        LIMIT 1
    """

    state_df = run_query(
        state_query,
        {
            "state": state,
            "year": year,
            "quarter": quarter
        }
    )

    if state_df.empty:
        return None

    # ---------------------------------------------------------
    # 2. CATEGORY BREAKDOWN
    # ---------------------------------------------------------
    category_query = """
        SELECT
            "Transaction_type",
            SUM("Transaction_count") AS "Transaction_count"
        FROM aggregated_transaction_state
        WHERE LOWER("State") = LOWER(:state)
          AND "Year" = :year
          AND "Quarter" = :quarter
        GROUP BY "Transaction_type"
        ORDER BY "Transaction_count" DESC
    """

    category_df = run_query(
        category_query,
        {
            "state": state,
            "year": year,
            "quarter": quarter
        }
    )

    # ---------------------------------------------------------
    # 3. TOP DISTRICT
    # ---------------------------------------------------------
    district_query = """
        SELECT
            "District",
            SUM("Transaction_count") AS "Transaction_count"
        FROM top_transaction
        WHERE LOWER("State") = LOWER(:state)
          AND "Year" = :year
          AND "Quarter" = :quarter
          AND "District" IS NOT NULL
        GROUP BY "District"
        ORDER BY "Transaction_count" DESC
        LIMIT 1
    """

    district_df = run_query(
        district_query,
        {
            "state": state,
            "year": year,
            "quarter": quarter
        }
    )

    # ---------------------------------------------------------
    # 4. BUILD SUMMARY
    # ---------------------------------------------------------
    row = state_df.iloc[0]

    transaction_count = float(row["Transaction_count"])
    transaction_amount = float(row["Transaction_amount"])

    if transaction_count > 0:
        average_transaction_value = (
            transaction_amount / transaction_count
        )
    else:
        average_transaction_value = 0

    summary = {
        "State": row["State"],
        "Year": int(row["Year"]),
        "Quarter": int(row["Quarter"]),
        "Transaction_count": transaction_count,
        "Transaction_amount": transaction_amount,
        "Average_transaction_value": average_transaction_value,
        "Categories": category_df,
        "Top_district": district_df
    }

    return summary