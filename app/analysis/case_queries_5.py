"""
SQL for case study 5 - User Engagement and Growth Strategy.

The source data has NO app-open counts (checked: no appOpens field in any
aggregated/map/top user file), so engagement is measured as
transactions per registered user.

Sources
-------
map_transaction   state transaction counts per quarter
map_user          registered users per state (cumulative at quarter end)
top_transaction   top districts per state (count)
top_user          top districts per state (registered users)
"""

import pandas as pd
import streamlit as st

from db.connection import run_query

CACHE_TTL = 3600


def _numeric(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_engagement_series():
    """State x quarter: transaction count and registered users."""
    sql = """
        WITH t AS (
            SELECT "State", "Year", "Quarter",
                   SUM("Transaction_count") AS cnt
            FROM map_transaction
            GROUP BY "State", "Year", "Quarter"
        ),
        u AS (
            SELECT "State", "Year", "Quarter",
                   SUM("Registered_users") AS users
            FROM map_user
            GROUP BY "State", "Year", "Quarter"
        )
        SELECT
            t."State",
            t."Year",
            t."Quarter",
            t.cnt   AS "Transaction_count",
            u.users AS "Registered_users"
        FROM t
        JOIN u
          ON u."State"   = t."State"
         AND u."Year"    = t."Year"
         AND u."Quarter" = t."Quarter"
        ORDER BY t."State", t."Year", t."Quarter"
    """
    df = run_query(sql)
    return _numeric(df, ["Transaction_count", "Registered_users"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_district_engagement(year, quarter):
    """
    Districts that appear in BOTH the published top-transaction and
    top-user lists for the quarter, with count and registered users.
    """
    sql = """
        WITH t AS (
            SELECT "State", "District",
                   SUM("Transaction_count") AS cnt
            FROM top_transaction
            WHERE "State" IS NOT NULL AND "District" IS NOT NULL
              AND "Year" = :year AND "Quarter" = :quarter
            GROUP BY "State", "District"
        ),
        u AS (
            SELECT "State", "District",
                   SUM("Registered_users") AS users
            FROM top_user
            WHERE "State" IS NOT NULL AND "District" IS NOT NULL
              AND "Year" = :year AND "Quarter" = :quarter
            GROUP BY "State", "District"
        )
        SELECT
            t."State",
            t."District",
            t.cnt   AS "Transaction_count",
            u.users AS "Registered_users"
        FROM t
        JOIN u
          ON u."State"    = t."State"
         AND u."District" = t."District"
    """
    df = run_query(sql, {"year": year, "quarter": quarter})
    return _numeric(df, ["Transaction_count", "Registered_users"])
