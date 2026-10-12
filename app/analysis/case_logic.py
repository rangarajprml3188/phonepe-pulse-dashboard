"""
Pure pandas logic for the PhonePe case studies (no Streamlit, no SQL).

Keeping the calculations here means they can be tested on their own and
the findings text is always computed from the data, never typed by hand.

DATA RULE
---------
Only map_transaction carries real payment value (state level).
Category and district analysis therefore uses Transaction_count.
"""

import numpy as np
import pandas as pd


# ============================================================
# SMALL HELPERS
# ============================================================

def period_key(year, quarter):
    """Single sortable number for a year-quarter (2024 Q3 -> 8099)."""
    return int(year) * 4 + int(quarter) - 1


def period_label(year, quarter):
    return f"{int(year)} Q{int(quarter)}"


def pct(value, digits=1):
    """Format a percentage safely."""
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:,.{digits}f}%"


def compact(value):
    """Readable large numbers (counts)."""
    if value is None or pd.isna(value):
        return "n/a"
    value = float(value)
    for unit, size in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= size:
            return f"{value / size:.2f} {unit}"
    return f"{value:,.0f}"


def rupees(value):
    """Indian units for rupee values."""
    if value is None or pd.isna(value):
        return "n/a"
    value = float(value)
    if abs(value) >= 1e7:
        return f"₹{value / 1e7:,.2f} Cr"
    if abs(value) >= 1e5:
        return f"₹{value / 1e5:,.2f} L"
    return f"₹{value:,.2f}"


# ============================================================
# CASE 1 - TRANSACTION DYNAMICS
# ============================================================

def classify_growth(yoy, growth_threshold=15.0):
    """
    Label a year-over-year growth figure.

        Declining : below 0 %
        Stagnant  : 0 % up to the growth threshold
        Growing   : at or above the growth threshold
    """
    if yoy is None or pd.isna(yoy):
        return "No prior-year data"
    if yoy < 0:
        return "Declining"
    if yoy < growth_threshold:
        return "Stagnant"
    return "Growing"


def state_growth_table(yoy_df, year, quarter, growth_threshold=15.0):
    """
    One row per state for the selected period, with a growth label.
    yoy_df comes from case_queries.get_state_yoy_series().
    """
    out = yoy_df[
        (yoy_df["Year"] == year) & (yoy_df["Quarter"] == quarter)
    ].copy()
    out["Growth_class"] = out["Count_YoY_pct"].apply(
        lambda v: classify_growth(v, growth_threshold)
    )
    return out.sort_values("Count_YoY_pct", ascending=False).reset_index(drop=True)


def growth_consistency(yoy_df, year, quarter, n=4):
    """
    For each state, how many of the last n quarters (up to and including
    the selected one) had positive year-over-year transaction growth.
    """
    key = period_key(year, quarter)
    df = yoy_df.copy()
    df["_key"] = df.apply(lambda r: period_key(r["Year"], r["Quarter"]), axis=1)
    df = df[df["_key"] <= key]

    recent = sorted(df["_key"].unique())[-n:]
    df = df[df["_key"].isin(recent)]

    grouped = df.groupby("State").agg(
        Quarters_positive=("Count_YoY_pct", lambda s: int((s > 0).sum())),
        Quarters_observed=("Count_YoY_pct", "count"),
        Avg_YoY_pct=("Count_YoY_pct", "mean"),
    )
    return grouped.reset_index()


def category_summary(cat_df, year, quarter):
    """
    Category share of transactions and year-over-year growth.
    cat_df: Year, Quarter, Transaction_type, Transaction_count.
    """
    cur = cat_df[(cat_df["Year"] == year) & (cat_df["Quarter"] == quarter)]
    prev = cat_df[(cat_df["Year"] == year - 1) & (cat_df["Quarter"] == quarter)]

    cur = cur.groupby("Transaction_type")["Transaction_count"].sum()
    prev = prev.groupby("Transaction_type")["Transaction_count"].sum()

    out = pd.DataFrame({"Transaction_count": cur, "Prev_count": prev}).reset_index()
    out = out.rename(columns={"index": "Transaction_type"})
    total = out["Transaction_count"].sum()
    out["Share_pct"] = out["Transaction_count"] / total * 100 if total else np.nan
    out["YoY_pct"] = np.where(
        out["Prev_count"] > 0,
        (out["Transaction_count"] - out["Prev_count"]) / out["Prev_count"] * 100,
        np.nan,
    )
    return out.sort_values("Transaction_count", ascending=False).reset_index(drop=True)


def case1_findings(national_df, state_df, consistency_df, cat_df, year, quarter):
    """Plain-English findings computed from the data."""
    lines = []
    label = period_label(year, quarter)

    row = national_df[
        (national_df["Year"] == year) & (national_df["Quarter"] == quarter)
    ]
    if not row.empty:
        r = row.iloc[0]
        lines.append(
            f"**National, {label}:** {compact(r['Transaction_count'])} transactions "
            f"worth {rupees(r['Transaction_amount'])}; "
            f"count {pct(r['Count_YoY_pct'])} and value {pct(r['Amount_YoY_pct'])} "
            f"versus the same quarter last year."
        )

    known = state_df[state_df["Growth_class"] != "No prior-year data"]
    if not known.empty:
        counts = known["Growth_class"].value_counts()
        lines.append(
            f"**State spread:** {counts.get('Growing', 0)} growing, "
            f"{counts.get('Stagnant', 0)} stagnant and "
            f"{counts.get('Declining', 0)} declining out of {len(known)} states/UTs."
        )
        top = known.head(3)
        bottom = known.tail(3).iloc[::-1]
        lines.append(
            "**Fastest growth (count YoY):** "
            + ", ".join(
                f"{s.title()} ({pct(v)})"
                for s, v in zip(top["State"], top["Count_YoY_pct"])
            )
            + "."
        )
        lines.append(
            "**Slowest growth (count YoY):** "
            + ", ".join(
                f"{s.title()} ({pct(v)})"
                for s, v in zip(bottom["State"], bottom["Count_YoY_pct"])
            )
            + "."
        )

    if not consistency_df.empty:
        n = int(consistency_df["Quarters_observed"].max())
        steady = consistency_df[
            (consistency_df["Quarters_positive"] == n)
            & (consistency_df["Quarters_observed"] == n)
        ]
        weak = consistency_df[consistency_df["Quarters_positive"] <= n // 2]
        lines.append(
            f"**Consistency (last {n} quarters):** {len(steady)} states grew "
            f"year over year in every quarter; {len(weak)} grew in half "
            f"or fewer."
        )

    if not cat_df.empty:
        lead = cat_df.iloc[0]
        fastest = cat_df.dropna(subset=["YoY_pct"]).sort_values(
            "YoY_pct", ascending=False
        )
        text = (
            f"**Categories:** {lead['Transaction_type']} is the largest "
            f"({pct(lead['Share_pct'])} of transactions)"
        )
        if not fastest.empty:
            f = fastest.iloc[0]
            text += (
                f"; {f['Transaction_type']} is growing fastest "
                f"({pct(f['YoY_pct'])} YoY)"
            )
        lines.append(text + ".")

    return lines


# ============================================================
# CASE 4 - MARKET EXPANSION
# ============================================================

def add_expansion_metrics(df):
    """
    Adds per-user and per-merchant metrics to the state table.
    Expects: State, Transaction_count, Transaction_amount,
             Registered_users, Registered_merchants.
    """
    out = df.copy()
    for col in (
        "Transaction_count",
        "Transaction_amount",
        "Registered_users",
        "Registered_merchants",
    ):
        out[col] = pd.to_numeric(out[col], errors="coerce")

    def ratio(a, b):
        return (out[a] / out[b]).replace([np.inf, -np.inf], np.nan)

    out["Avg_ticket"] = ratio("Transaction_amount", "Transaction_count")
    out["Txn_per_user"] = ratio("Transaction_count", "Registered_users")
    out["Value_per_user"] = ratio("Transaction_amount", "Registered_users")
    out["Users_per_merchant"] = ratio("Registered_users", "Registered_merchants")
    return out


def assign_segments(df):
    """
    Split states by user base size and activity (median split).

        Core stronghold          big user base, high activity
        Activation opportunity   big user base, low activity
        Acquisition opportunity  small user base, high activity
        Watchlist                small user base, low activity
    """
    out = df.dropna(subset=["Registered_users", "Txn_per_user"]).copy()
    if out.empty:
        out["Segment"] = []
        return out, np.nan, np.nan

    users_median = out["Registered_users"].median()
    activity_median = out["Txn_per_user"].median()

    big = out["Registered_users"] >= users_median
    active = out["Txn_per_user"] >= activity_median

    out["Segment"] = np.select(
        [big & active, big & ~active, ~big & active],
        ["Core stronghold", "Activation opportunity", "Acquisition opportunity"],
        default="Watchlist",
    )
    return out, users_median, activity_median


def case4_findings(seg_df, users_median, activity_median, year, quarter):
    lines = []
    label = period_label(year, quarter)
    if seg_df.empty:
        return ["No state data is available for this period."]

    counts = seg_df["Segment"].value_counts()
    lines.append(
        f"**Segments, {label}:** {counts.get('Core stronghold', 0)} core strongholds, "
        f"{counts.get('Activation opportunity', 0)} activation opportunities, "
        f"{counts.get('Acquisition opportunity', 0)} acquisition opportunities and "
        f"{counts.get('Watchlist', 0)} on the watchlist."
    )
    lines.append(
        f"**Benchmarks (median state):** {compact(users_median)} registered users "
        f"and {activity_median:,.2f} transactions per registered user in the quarter."
    )

    act = seg_df[seg_df["Segment"] == "Activation opportunity"].sort_values(
        "Registered_users", ascending=False
    )
    if not act.empty:
        top = act.head(3)
        lines.append(
            "**Largest activation gaps (many users, below-median activity):** "
            + ", ".join(
                f"{s.title()} ({compact(u)} users, {t:.1f} txns/user)"
                for s, u, t in zip(
                    top["State"], top["Registered_users"], top["Txn_per_user"]
                )
            )
            + "."
        )

    acq = seg_df[seg_df["Segment"] == "Acquisition opportunity"].sort_values(
        "Txn_per_user", ascending=False
    )
    if not acq.empty:
        top = acq.head(3)
        lines.append(
            "**Engaged but small (acquire more users):** "
            + ", ".join(
                f"{s.title()} ({t:.1f} txns/user)"
                for s, t in zip(top["State"], top["Txn_per_user"])
            )
            + "."
        )

    ticket = seg_df.dropna(subset=["Avg_ticket"]).sort_values(
        "Avg_ticket", ascending=False
    )
    if not ticket.empty:
        hi, lo = ticket.iloc[0], ticket.iloc[-1]
        lines.append(
            f"**Average ticket size:** highest in {hi['State'].title()} "
            f"({rupees(hi['Avg_ticket'])}), lowest in {lo['State'].title()} "
            f"({rupees(lo['Avg_ticket'])})."
        )
    return lines
