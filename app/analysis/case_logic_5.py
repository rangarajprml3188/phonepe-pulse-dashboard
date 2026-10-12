"""
Pure pandas logic for case study 5 (no Streamlit, no SQL).

Engagement = transactions per registered user (the data has no app opens).
Registered users is cumulative, so the ratio is best read as a relative
comparison between states and over time, not an absolute usage rate.
"""

import numpy as np
import pandas as pd

from analysis import case_logic as cl

SEGMENTS = [
    "Scaling and deepening",
    "Growing without depth",
    "Deepening on a mature base",
    "Lagging",
]


def _name(value):
    return str(value).title()


def _growth(cur, prev):
    """Percent change; NaN when the previous value is missing or zero."""
    prev = prev.replace(0, np.nan)
    return (cur - prev) / prev * 100


def add_engagement(df):
    """Adds Txn_per_user to a State/Year/Quarter table."""
    out = df.copy()
    out["Txn_per_user"] = (
        out["Transaction_count"] / out["Registered_users"]
    ).replace([np.inf, -np.inf], np.nan)
    return out


def add_yoy(df):
    """
    Year-over-year change in registered users and in engagement,
    matched on the same quarter of the previous year.
    Expects State, Year, Quarter, Registered_users, Txn_per_user.
    """
    prev = df[
        ["State", "Year", "Quarter", "Registered_users", "Txn_per_user"]
    ].copy()
    prev["Year"] = prev["Year"] + 1
    prev = prev.rename(
        columns={
            "Registered_users": "Prev_users",
            "Txn_per_user": "Prev_txn_per_user",
        }
    )
    out = df.merge(prev, on=["State", "Year", "Quarter"], how="left")
    out["User_growth_pct"] = _growth(out["Registered_users"], out["Prev_users"])
    out["Engagement_change_pct"] = _growth(
        out["Txn_per_user"], out["Prev_txn_per_user"]
    )
    return out


def national_series(state_df):
    """Country-level series built from the state rows."""
    nat = (
        state_df.groupby(["Year", "Quarter"], as_index=False)[
            ["Transaction_count", "Registered_users"]
        ]
        .sum()
        .sort_values(["Year", "Quarter"])
    )
    nat["State"] = "india"
    nat = add_engagement(nat)
    return add_yoy(nat)


def classify_states(period_df, national_row):
    """
    Compare each state with the national year-over-year figures.

        Scaling and deepening       users AND engagement growing faster than India
        Growing without depth       users faster, engagement slower
        Deepening on a mature base  users slower, engagement faster
        Lagging                     both slower than India
    """
    out = period_df.dropna(
        subset=["User_growth_pct", "Engagement_change_pct"]
    ).copy()
    if (
        out.empty
        or national_row is None
        or pd.isna(national_row["User_growth_pct"])
        or pd.isna(national_row["Engagement_change_pct"])
    ):
        out = out.iloc[0:0].copy()
        out["Segment"] = []
        return out

    users_fast = out["User_growth_pct"] >= national_row["User_growth_pct"]
    engage_fast = out["Engagement_change_pct"] >= national_row["Engagement_change_pct"]

    out["Segment"] = np.select(
        [users_fast & engage_fast, users_fast & ~engage_fast, ~users_fast & engage_fast],
        [SEGMENTS[0], SEGMENTS[1], SEGMENTS[2]],
        default=SEGMENTS[3],
    )
    return out


def add_district_engagement(df):
    out = df.copy()
    out["Txn_per_user"] = (
        out["Transaction_count"] / out["Registered_users"]
    ).replace([np.inf, -np.inf], np.nan)
    return out


# ============================================================
# FINDINGS
# ============================================================

def case5_findings(national_row, classified, period_df, district_df, year, quarter):
    lines = []
    label = cl.period_label(year, quarter)

    if national_row is not None:
        text = (
            f"**National engagement, {label}:** "
            f"{national_row['Txn_per_user']:.2f} transactions per registered user "
            f"in the quarter"
        )
        if pd.notna(national_row["Engagement_change_pct"]):
            text += (
                f" ({cl.pct(national_row['Engagement_change_pct'])} versus the same "
                f"quarter last year, while registered users grew "
                f"{cl.pct(national_row['User_growth_pct'])})"
            )
        lines.append(text + ".")

    ranked = period_df.dropna(subset=["Txn_per_user"]).sort_values(
        "Txn_per_user", ascending=False
    )
    if len(ranked) >= 6:
        top = ranked.head(3)
        bottom = ranked.tail(3).iloc[::-1]
        lines.append(
            "**Most engaged states:** "
            + ", ".join(
                f"{_name(s)} ({v:.2f})" for s, v in zip(top["State"], top["Txn_per_user"])
            )
            + "."
        )
        lines.append(
            "**Least engaged states:** "
            + ", ".join(
                f"{_name(s)} ({v:.2f})"
                for s, v in zip(bottom["State"], bottom["Txn_per_user"])
            )
            + "."
        )

    if not classified.empty:
        counts = classified["Segment"].value_counts()
        lines.append(
            "**Segments versus India:** "
            + ", ".join(f"{counts.get(s, 0)} {s.lower()}" for s in SEGMENTS)
            + "."
        )
        gwd = classified[classified["Segment"] == SEGMENTS[1]].sort_values(
            "Registered_users", ascending=False
        )
        if not gwd.empty:
            top = gwd.head(3)
            lines.append(
                "**Growing without depth (priority to activate):** "
                + ", ".join(
                    f"{_name(s)} (users {cl.pct(u)}, engagement {cl.pct(e)})"
                    for s, u, e in zip(
                        top["State"], top["User_growth_pct"], top["Engagement_change_pct"]
                    )
                )
                + "."
            )
        deep = classified[classified["Segment"] == SEGMENTS[2]].sort_values(
            "Engagement_change_pct", ascending=False
        )
        if not deep.empty:
            top = deep.head(3)
            lines.append(
                "**Deepening on a mature base (acquisition headroom):** "
                + ", ".join(
                    f"{_name(s)} (engagement {cl.pct(e)}, users {cl.pct(u)})"
                    for s, e, u in zip(
                        top["State"], top["Engagement_change_pct"], top["User_growth_pct"]
                    )
                )
                + "."
            )

    if district_df is not None and len(district_df) >= 4:
        d = district_df.dropna(subset=["Txn_per_user"]).sort_values(
            "Txn_per_user", ascending=False
        )
        hi, lo = d.iloc[0], d.iloc[-1]
        lines.append(
            f"**Districts:** among districts in both published top lists, "
            f"{_name(hi['District'])} ({_name(hi['State'])}) is the most engaged "
            f"({hi['Txn_per_user']:.2f} transactions per user) and "
            f"{_name(lo['District'])} ({_name(lo['State'])}) the least "
            f"({lo['Txn_per_user']:.2f})."
        )
    return lines
