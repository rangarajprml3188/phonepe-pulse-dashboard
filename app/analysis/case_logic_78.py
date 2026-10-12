"""
Pure pandas logic for case studies 7 and 8 (no Streamlit, no SQL).
Findings text is computed from the data, never typed by hand.
"""

import numpy as np
import pandas as pd

from analysis import case_logic as cl


def prev_period(year, quarter):
    """Quarter immediately before (year, quarter)."""
    year, quarter = int(year), int(quarter)
    if quarter == 1:
        return year - 1, 4
    return year, quarter - 1


def _name(value):
    return str(value).title()


# ============================================================
# CASE 7 - TRANSACTIONS
# ============================================================

def add_state_shares(states_df):
    """Share of national count and value, plus average ticket size."""
    out = states_df.copy()
    total_count = out["Transaction_count"].sum()
    total_amount = out["Transaction_amount"].sum()
    out["Count_share_pct"] = (
        out["Transaction_count"] / total_count * 100 if total_count else np.nan
    )
    out["Amount_share_pct"] = (
        out["Transaction_amount"] / total_amount * 100 if total_amount else np.nan
    )
    out["Avg_ticket"] = (
        out["Transaction_amount"] / out["Transaction_count"]
    ).replace([np.inf, -np.inf], np.nan)
    return out


def case7_findings(states_df, districts_df, year, quarter, top_n=5):
    lines = []
    label = cl.period_label(year, quarter)
    if states_df.empty:
        return ["No state data is available for this period."]

    s = add_state_shares(states_df)
    total_count = s["Transaction_count"].sum()
    total_amount = s["Transaction_amount"].sum()
    lines.append(
        f"**National, {label}:** {cl.compact(total_count)} transactions worth "
        f"{cl.rupees(total_amount)} across {len(s)} states/UTs."
    )

    by_count = s.sort_values("Transaction_count", ascending=False)
    by_value = s.sort_values("Transaction_amount", ascending=False)
    lines.append(
        f"**Top {top_n} states by volume:** "
        + ", ".join(
            f"{_name(a)} ({cl.pct(b)})"
            for a, b in zip(
                by_count["State"].head(top_n), by_count["Count_share_pct"].head(top_n)
            )
        )
        + f" - together {cl.pct(by_count['Count_share_pct'].head(top_n).sum())} "
        "of all transactions."
    )
    lines.append(
        f"**Top {top_n} states by value:** "
        + ", ".join(
            f"{_name(a)} ({cl.pct(b)})"
            for a, b in zip(
                by_value["State"].head(top_n), by_value["Amount_share_pct"].head(top_n)
            )
        )
        + f" - together {cl.pct(by_value['Amount_share_pct'].head(top_n).sum())} "
        "of payment value."
    )

    # Where volume rank and value rank disagree.
    s["Count_rank"] = s["Transaction_count"].rank(ascending=False, method="min")
    s["Amount_rank"] = s["Transaction_amount"].rank(ascending=False, method="min")
    s["Rank_gap"] = s["Count_rank"] - s["Amount_rank"]
    if s["Rank_gap"].notna().any():
        up = s.sort_values("Rank_gap", ascending=False).iloc[0]
        down = s.sort_values("Rank_gap", ascending=True).iloc[0]
        if up["Rank_gap"] > 0:
            lines.append(
                f"**Value outranks volume:** {_name(up['State'])} is #{int(up['Amount_rank'])} "
                f"by value but #{int(up['Count_rank'])} by count (higher average ticket, "
                f"{cl.rupees(up['Avg_ticket'])})."
            )
        if down["Rank_gap"] < 0:
            lines.append(
                f"**Volume outranks value:** {_name(down['State'])} is #{int(down['Count_rank'])} "
                f"by count but #{int(down['Amount_rank'])} by value (smaller tickets, "
                f"{cl.rupees(down['Avg_ticket'])})."
            )

    if not districts_df.empty and total_count:
        top = districts_df.sort_values("Transaction_count", ascending=False).head(3)
        lines.append(
            "**Top districts by volume:** "
            + ", ".join(
                f"{_name(d)} ({_name(st)}, {cl.compact(c)})"
                for d, st, c in zip(
                    top["District"], top["State"], top["Transaction_count"]
                )
            )
            + "."
        )
    return lines


# ============================================================
# CASE 8 - REGISTRATIONS
# ============================================================

def case8_findings(reg_df, districts_df, year, quarter):
    lines = []
    label = cl.period_label(year, quarter)
    if reg_df.empty:
        return ["No registration data is available for this period."]

    total = reg_df["Registered_users"].sum()
    net = reg_df["Net_new_users"].sum(min_count=1)
    text = (
        f"**National, {label}:** {cl.compact(total)} registered users across "
        f"{len(reg_df)} states/UTs"
    )
    if pd.notna(net):
        text += f"; {cl.compact(net)} net new users versus the previous quarter"
    lines.append(text + ".")

    top = reg_df.sort_values("Registered_users", ascending=False).head(3)
    lines.append(
        "**Largest user bases:** "
        + ", ".join(
            f"{_name(s)} ({cl.compact(u)}, {cl.pct(u / total * 100)})"
            for s, u in zip(top["State"], top["Registered_users"])
        )
        + "."
    )

    gain = reg_df.dropna(subset=["Net_new_users"]).sort_values(
        "Net_new_users", ascending=False
    )
    if not gain.empty:
        top = gain.head(3)
        lines.append(
            "**Most new users this quarter:** "
            + ", ".join(
                f"{_name(s)} (+{cl.compact(n)})"
                for s, n in zip(top["State"], top["Net_new_users"])
            )
            + "."
        )

    # Fastest growth, among states with an above-median base so tiny
    # territories don't dominate the ranking.
    median_users = reg_df["Registered_users"].median()
    big = reg_df[reg_df["Registered_users"] >= median_users].dropna(
        subset=["QoQ_growth_pct"]
    )
    if not big.empty:
        top = big.sort_values("QoQ_growth_pct", ascending=False).head(3)
        lines.append(
            "**Fastest growth (states with above-median user base):** "
            + ", ".join(
                f"{_name(s)} ({cl.pct(g)})"
                for s, g in zip(top["State"], top["QoQ_growth_pct"])
            )
            + "."
        )

    if not districts_df.empty:
        top = districts_df.sort_values("Registered_users", ascending=False).head(3)
        lines.append(
            "**Top districts by registered users:** "
            + ", ".join(
                f"{_name(d)} ({_name(st)}, {cl.compact(u)})"
                for d, st, u in zip(
                    top["District"], top["State"], top["Registered_users"]
                )
            )
            + "."
        )
    return lines
