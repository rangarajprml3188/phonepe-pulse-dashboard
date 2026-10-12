"""
SQL for case studies 7 and 8.

Case 7 - transactions across states and districts
Case 8 - user registrations across states and districts

Sources
-------
map_transaction   state totals: count AND value (only real value in the data)
map_user          registered users by state (cumulative total at quarter end)
top_transaction   top districts per state (count only; amounts are absent)
top_user          top districts per state (registered users)

Pin codes are not loaded by phonepe_master.py, so analysis stops at
district level.
"""

import pandas as pd
import streamlit as st

from db.connection import run_query

CACHE_TTL = 3600


def _numeric(df, columns):
    """PostgreSQL SUMs can arrive as Decimal; convert to float."""
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ============================================================
# CASE 7 - TRANSACTIONS
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_state_transactions(year, quarter):
    """One row per state: transaction count and value."""
    sql = """
        SELECT
            "State",
            SUM("Transaction_count")  AS "Transaction_count",
            SUM("Transaction_amount") AS "Transaction_amount"
        FROM map_transaction
        WHERE "Year" = :year AND "Quarter" = :quarter
        GROUP BY "State"
        ORDER BY "Transaction_count" DESC
    """
    df = run_query(sql, {"year": year, "quarter": quarter})
    return _numeric(df, ["Transaction_count", "Transaction_amount"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_top_districts_transactions(year, quarter, limit=50):
    """
    Top districts nationwide by transaction count.

    Built from the state-level top lists (top 10 districts per state),
    so every district in the national top 10 is guaranteed to be present
    and each row carries its state.
    """
    sql = """
        SELECT
            "State",
            "District",
            SUM("Transaction_count") AS "Transaction_count"
        FROM top_transaction
        WHERE "State" IS NOT NULL
          AND "District" IS NOT NULL
          AND "Year" = :year AND "Quarter" = :quarter
        GROUP BY "State", "District"
        ORDER BY "Transaction_count" DESC
        LIMIT :limit
    """
    df = run_query(sql, {"year": year, "quarter": quarter, "limit": limit})
    return _numeric(df, ["Transaction_count"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_state_districts_transactions(state, year, quarter):
    """Published top districts (up to 10) inside one state."""
    sql = """
        SELECT
            "District",
            SUM("Transaction_count") AS "Transaction_count"
        FROM top_transaction
        WHERE "State" = :state
          AND "District" IS NOT NULL
          AND "Year" = :year AND "Quarter" = :quarter
        GROUP BY "District"
        ORDER BY "Transaction_count" DESC
    """
    df = run_query(sql, {"state": state, "year": year, "quarter": quarter})
    return _numeric(df, ["Transaction_count"])


# ============================================================
# CASE 8 - USER REGISTRATIONS
# ============================================================

@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_state_registrations(year, quarter, prev_year, prev_quarter):
    """
    Registered users per state at the end of the selected quarter, plus
    net new users versus the previous quarter.

    Registered users is a cumulative total, so new registrations in a
    quarter = this quarter's total minus last quarter's total.
    """
    sql = """
        WITH cur AS (
            SELECT "State", SUM("Registered_users") AS users
            FROM map_user
            WHERE "Year" = :year AND "Quarter" = :quarter
            GROUP BY "State"
        ),
        prev AS (
            SELECT "State", SUM("Registered_users") AS users
            FROM map_user
            WHERE "Year" = :prev_year AND "Quarter" = :prev_quarter
            GROUP BY "State"
        )
        SELECT
            cur."State",
            cur.users  AS "Registered_users",
            prev.users AS "Prev_users",
            cur.users - prev.users AS "Net_new_users",
            100.0 * (cur.users - prev.users) / NULLIF(prev.users, 0)
                AS "QoQ_growth_pct"
        FROM cur
        LEFT JOIN prev ON prev."State" = cur."State"
        ORDER BY "Registered_users" DESC
    """
    df = run_query(
        sql,
        {
            "year": year,
            "quarter": quarter,
            "prev_year": prev_year,
            "prev_quarter": prev_quarter,
        },
    )
    return _numeric(
        df,
        ["Registered_users", "Prev_users", "Net_new_users", "QoQ_growth_pct"],
    )


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_top_districts_users(year, quarter, limit=50):
    """Top districts nationwide by registered users (via state lists)."""
    sql = """
        SELECT
            "State",
            "District",
            SUM("Registered_users") AS "Registered_users"
        FROM top_user
        WHERE "State" IS NOT NULL
          AND "District" IS NOT NULL
          AND "Year" = :year AND "Quarter" = :quarter
        GROUP BY "State", "District"
        ORDER BY "Registered_users" DESC
        LIMIT :limit
    """
    df = run_query(sql, {"year": year, "quarter": quarter, "limit": limit})
    return _numeric(df, ["Registered_users"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_state_districts_users(state, year, quarter):
    """Published top districts (up to 10) inside one state."""
    sql = """
        SELECT
            "District",
            SUM("Registered_users") AS "Registered_users"
        FROM top_user
        WHERE "State" = :state
          AND "District" IS NOT NULL
          AND "Year" = :year AND "Quarter" = :quarter
        GROUP BY "District"
        ORDER BY "Registered_users" DESC
    """
    df = run_query(sql, {"state": state, "year": year, "quarter": quarter})
    return _numeric(df, ["Registered_users"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_top_user_health():
    """
    Sanity check on top_user: are district names and user counts present?
    If the ETL read the wrong JSON keys these come back as 0.
    """
    sql = """
        SELECT
            COUNT(*)                                  AS total_rows,
            COUNT("District")                         AS named_districts,
            COALESCE(SUM(("Registered_users" > 0)::int), 0) AS nonzero_users
        FROM top_user
    """
    df = run_query(sql)
    return _numeric(df, ["total_rows", "named_districts", "nonzero_users"]).iloc[0]
