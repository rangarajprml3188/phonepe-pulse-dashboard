"""
SQL for the PhonePe case studies (cases 1 and 4).

Sources
-------
map_transaction         state totals: count AND amount (the only real value)
map_user                registered users by state
map_merchant            registered merchants by state
aggregated_transaction  category counts (State NULL = country total)

Category rows carry counts only (the source JSON has no amount field).
"""

import streamlit as st

from db.connection import run_query

CACHE_TTL = 3600


# ============================================================
# FILTER OPTIONS
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_periods():
    """Every (Year, Quarter) available, oldest first."""
    df = run_query(
        'SELECT DISTINCT "Year", "Quarter" '
        "FROM map_transaction "
        'ORDER BY "Year", "Quarter"'
    )
    return [(int(y), int(q)) for y, q in zip(df["Year"], df["Quarter"])]


# ============================================================
# CASE 1 - TRANSACTION DYNAMICS
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_national_trend_yoy():
    """
    National count and value per quarter with year-over-year growth.
    The self join matches the same quarter of the previous year.
    """
    sql = """
        WITH nat AS (
            SELECT
                "Year",
                "Quarter",
                SUM("Transaction_count")  AS cnt,
                SUM("Transaction_amount") AS amt
            FROM map_transaction
            GROUP BY "Year", "Quarter"
        )
        SELECT
            c."Year",
            c."Quarter",
            c.cnt AS "Transaction_count",
            c.amt AS "Transaction_amount",
            100.0 * (c.cnt - p.cnt) / NULLIF(p.cnt, 0) AS "Count_YoY_pct",
            100.0 * (c.amt - p.amt) / NULLIF(p.amt, 0) AS "Amount_YoY_pct"
        FROM nat c
        LEFT JOIN nat p
               ON p."Year"    = c."Year" - 1
              AND p."Quarter" = c."Quarter"
        ORDER BY c."Year", c."Quarter"
    """
    return run_query(sql)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_state_yoy_series():
    """
    Every state, every quarter that has a prior-year quarter,
    with year-over-year growth in count and value.
    """
    sql = """
        WITH s AS (
            SELECT
                "State",
                "Year",
                "Quarter",
                SUM("Transaction_count")  AS cnt,
                SUM("Transaction_amount") AS amt
            FROM map_transaction
            GROUP BY "State", "Year", "Quarter"
        )
        SELECT
            c."State",
            c."Year",
            c."Quarter",
            c.cnt AS "Transaction_count",
            c.amt AS "Transaction_amount",
            100.0 * (c.cnt - p.cnt) / NULLIF(p.cnt, 0) AS "Count_YoY_pct",
            100.0 * (c.amt - p.amt) / NULLIF(p.amt, 0) AS "Amount_YoY_pct"
        FROM s c
        JOIN s p
          ON p."State"   = c."State"
         AND p."Year"    = c."Year" - 1
         AND p."Quarter" = c."Quarter"
        ORDER BY c."State", c."Year", c."Quarter"
    """
    return run_query(sql)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_category_trend(state=None):
    """
    Transaction counts by category per quarter.
    state=None -> national (State IS NULL), otherwise that state.
    """
    if state is None:
        sql = """
            SELECT "Year", "Quarter", "Transaction_type",
                   SUM("Transaction_count") AS "Transaction_count"
            FROM aggregated_transaction
            WHERE "State" IS NULL
            GROUP BY "Year", "Quarter", "Transaction_type"
            ORDER BY "Year", "Quarter", "Transaction_type"
        """
        return run_query(sql)

    sql = """
        SELECT "Year", "Quarter", "Transaction_type",
               SUM("Transaction_count") AS "Transaction_count"
        FROM aggregated_transaction
        WHERE "State" = :state
        GROUP BY "Year", "Quarter", "Transaction_type"
        ORDER BY "Year", "Quarter", "Transaction_type"
    """
    return run_query(sql, {"state": state})


# ============================================================
# CASE 4 - MARKET EXPANSION
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_expansion_table(year, quarter):
    """
    One row per state: transactions, value, registered users and
    registered merchants for the selected quarter.
    """
    sql = """
        WITH t AS (
            SELECT "State",
                   SUM("Transaction_count")  AS cnt,
                   SUM("Transaction_amount") AS amt
            FROM map_transaction
            WHERE "Year" = :year AND "Quarter" = :quarter
            GROUP BY "State"
        ),
        u AS (
            SELECT "State", SUM("Registered_users") AS users
            FROM map_user
            WHERE "Year" = :year AND "Quarter" = :quarter
            GROUP BY "State"
        ),
        m AS (
            SELECT "State", SUM("Registered_merchants") AS merchants
            FROM map_merchant
            WHERE "Year" = :year AND "Quarter" = :quarter
            GROUP BY "State"
        )
        SELECT
            t."State",
            t.cnt       AS "Transaction_count",
            t.amt       AS "Transaction_amount",
            u.users     AS "Registered_users",
            m.merchants AS "Registered_merchants"
        FROM t
        LEFT JOIN u ON u."State" = t."State"
        LEFT JOIN m ON m."State" = t."State"
        ORDER BY t."State"
    """
    return run_query(sql, {"year": year, "quarter": quarter})
