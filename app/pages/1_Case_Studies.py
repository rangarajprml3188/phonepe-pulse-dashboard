"""
PhonePe Pulse - Business Case Studies

Case 1: Decoding Transaction Dynamics
Case 4: Transaction Analysis for Market Expansion

Place this file in app/pages/ (next to app.py). Streamlit adds it to the
sidebar automatically.

DATA RULE
---------
Payment VALUE exists only at state level (map_transaction).
Category and district analysis uses transaction COUNT.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import case_logic as cl
from analysis import case_queries as cq

st.set_page_config(
    page_title="PhonePe Pulse | Case Studies",
    page_icon="📊",
    layout="wide",
)


def clean_name(value):
    if pd.isna(value):
        return "Unknown"
    return str(value).replace("-", " ").replace("_", " ").title()


# ============================================================
# HEADER + PERIOD FILTER
# ============================================================

st.title("Business Case Studies")
st.caption(
    "Findings are computed from the PostgreSQL data. Payment value is "
    "state-level only; category and district views use transaction counts."
)

periods = cq.get_periods()
if not periods:
    st.error("No transaction data found. Run phonepe_master.py first.")
    st.stop()

years = sorted({y for y, _ in periods})

col_y, col_q, _ = st.columns([1, 1, 4])
with col_y:
    year = st.selectbox("Year", years, index=len(years) - 1)
with col_q:
    quarters = sorted({q for y, q in periods if y == year})
    quarter = st.selectbox(
        "Quarter",
        quarters,
        index=len(quarters) - 1,
        format_func=lambda q: f"Q{q}",
    )

label = cl.period_label(year, quarter)

tab1, tab4 = st.tabs(
    [
        "Case 1 - Transaction Dynamics",
        "Case 4 - Market Expansion",
    ]
)


# ============================================================
# CASE 1 - TRANSACTION DYNAMICS
# ============================================================

with tab1:
    st.header("Decoding Transaction Dynamics")
    st.write(
        "Where is transaction behaviour growing, stagnating or declining "
        "across states, quarters and payment categories?"
    )

    national = cq.get_national_trend_yoy()
    state_yoy = cq.get_state_yoy_series()

    # ---------------- national headline ----------------
    now = national[
        (national["Year"] == year) & (national["Quarter"] == quarter)
    ]
    if now.empty:
        st.warning(f"No national data for {label}.")
        st.stop()
    now = now.iloc[0]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Transactions", cl.compact(now["Transaction_count"]))
    m2.metric(
        "Count growth (YoY)",
        cl.pct(now["Count_YoY_pct"]),
    )
    m3.metric("Payment value", cl.rupees(now["Transaction_amount"]))
    m4.metric(
        "Value growth (YoY)",
        cl.pct(now["Amount_YoY_pct"]),
    )

    # ---------------- national trend ----------------
    trend = national.copy()
    trend["Period"] = [
        cl.period_label(y, q) for y, q in zip(trend["Year"], trend["Quarter"])
    ]

    left, right = st.columns(2)
    with left:
        fig = px.line(
            trend,
            x="Period",
            y="Transaction_count",
            markers=True,
            title="National transactions per quarter",
        )
        fig.update_layout(xaxis_title="", yaxis_title="Transactions")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        yoy_long = trend.melt(
            id_vars="Period",
            value_vars=["Count_YoY_pct", "Amount_YoY_pct"],
            var_name="Metric",
            value_name="YoY_pct",
        ).dropna()
        yoy_long["Metric"] = yoy_long["Metric"].map(
            {"Count_YoY_pct": "Transaction count", "Amount_YoY_pct": "Payment value"}
        )
        fig = px.line(
            yoy_long,
            x="Period",
            y="YoY_pct",
            color="Metric",
            markers=True,
            title="Year-over-year growth (%)",
        )
        fig.add_hline(y=0, line_dash="dot")
        fig.update_layout(xaxis_title="", yaxis_title="YoY growth (%)")
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ---------------- categories ----------------
    st.subheader("Payment categories")

    scope_state = st.selectbox(
        "Category scope",
        ["India (all states)"] + sorted(state_yoy["State"].unique()),
        format_func=lambda s: s if s.startswith("India") else clean_name(s),
    )
    cat_state = None if scope_state.startswith("India") else scope_state
    cat_trend = cq.get_category_trend(cat_state)

    if cat_trend.empty:
        st.info("No category data available for this scope.")
        cat_summary = pd.DataFrame()
    else:
        cat_plot = cat_trend.copy()
        cat_plot["Period"] = [
            cl.period_label(y, q) for y, q in zip(cat_plot["Year"], cat_plot["Quarter"])
        ]
        c_left, c_right = st.columns([3, 2])
        with c_left:
            fig = px.area(
                cat_plot,
                x="Period",
                y="Transaction_count",
                color="Transaction_type",
                title="Transactions by category (count)",
            )
            fig.update_layout(xaxis_title="", yaxis_title="Transactions")
            st.plotly_chart(fig, use_container_width=True)

        cat_summary = cl.category_summary(cat_trend, year, quarter)
        with c_right:
            st.markdown(f"**Category mix, {label}**")
            show = cat_summary.rename(
                columns={
                    "Transaction_type": "Category",
                    "Transaction_count": "Transactions",
                    "Share_pct": "Share %",
                    "YoY_pct": "YoY %",
                }
            )[["Category", "Transactions", "Share %", "YoY %"]]
            st.dataframe(
                show.round({"Share %": 1, "YoY %": 1}),
                hide_index=True,
                use_container_width=True,
            )

    st.divider()

    # ---------------- state growth ----------------
    st.subheader("State growth patterns")

    growth_threshold = st.slider(
        "Growing = year-over-year count growth of at least (%)",
        min_value=5,
        max_value=50,
        value=15,
        step=1,
        help="Declining is below 0%. Stagnant is between 0% and this value.",
    )

    state_table = cl.state_growth_table(state_yoy, year, quarter, growth_threshold)
    consistency = cl.growth_consistency(state_yoy, year, quarter, n=4)

    if state_table.empty:
        st.info(
            f"No year-over-year comparison is available for {label} "
            "(the previous year's quarter is missing)."
        )
    else:
        plot_df = state_table.copy()
        plot_df["State_name"] = plot_df["State"].apply(clean_name)

        fig = px.bar(
            plot_df.sort_values("Count_YoY_pct"),
            x="Count_YoY_pct",
            y="State_name",
            color="Growth_class",
            orientation="h",
            color_discrete_map={
                "Growing": "#2e9e5b",
                "Stagnant": "#e0a526",
                "Declining": "#d64545",
            },
            title=f"Transaction count growth by state, {label} vs {year - 1} Q{quarter}",
            height=max(500, 22 * len(plot_df)),
        )
        fig.update_layout(xaxis_title="YoY growth (%)", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

        # Heatmap of the last 8 quarters.
        hm = state_yoy.copy()
        hm["_key"] = [cl.period_key(y, q) for y, q in zip(hm["Year"], hm["Quarter"])]
        upto = hm[hm["_key"] <= cl.period_key(year, quarter)]
        recent_keys = sorted(upto["_key"].unique())[-8:]
        hm = upto[upto["_key"].isin(recent_keys)].copy()
        hm["Period"] = [cl.period_label(y, q) for y, q in zip(hm["Year"], hm["Quarter"])]
        order = [
            cl.period_label(y, q)
            for y, q in sorted(
                {(int(y), int(q)) for y, q in zip(hm["Year"], hm["Quarter"])}
            )
        ]
        pivot = hm.pivot_table(
            index="State", columns="Period", values="Count_YoY_pct"
        ).reindex(columns=order)
        pivot.index = [clean_name(s) for s in pivot.index]
        pivot = pivot.clip(lower=-50, upper=100)

        fig = px.imshow(
            pivot,
            aspect="auto",
            color_continuous_scale="RdYlGn",
            color_continuous_midpoint=0,
            title="Year-over-year count growth, last 8 quarters (capped at -50% / +100%)",
            height=max(500, 22 * len(pivot)),
        )
        fig.update_layout(xaxis_title="", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Findings")
    for line in cl.case1_findings(
        national, state_table, consistency, cat_summary, year, quarter
    ):
        st.markdown(f"- {line}")


# ============================================================
# CASE 4 - MARKET EXPANSION
# ============================================================

with tab4:
    st.header("Transaction Analysis for Market Expansion")
    st.write(
        "Which states combine a large registered base with low activity "
        "(activate them), or high activity with a small base (acquire users)?"
    )

    raw = cq.get_expansion_table(year, quarter)
    if raw.empty:
        st.warning(f"No state data for {label}.")
        st.stop()

    metrics_df = cl.add_expansion_metrics(raw)
    seg_df, users_median, activity_median = cl.assign_segments(metrics_df)

    if seg_df.empty:
        st.warning(
            "Registered-user data is missing for this period, so segments "
            "cannot be built."
        )
        st.stop()

    seg_df["State_name"] = seg_df["State"].apply(clean_name)

    seg_colors = {
        "Core stronghold": "#2e9e5b",
        "Activation opportunity": "#e0a526",
        "Acquisition opportunity": "#3b7dd8",
        "Watchlist": "#9aa0a6",
    }

    plot_df = seg_df.dropna(subset=["Transaction_amount"]).copy()
    plot_df = plot_df[plot_df["Transaction_amount"] > 0]

    fig = px.scatter(
        plot_df,
        x="Registered_users",
        y="Txn_per_user",
        size="Transaction_amount",
        color="Segment",
        color_discrete_map=seg_colors,
        hover_name="State_name",
        hover_data={
            "Registered_users": ":,.0f",
            "Txn_per_user": ":.1f",
            "Transaction_amount": ":,.0f",
            "State_name": False,
        },
        log_x=True,
        size_max=45,
        title=f"Registered users vs transactions per user, {label}",
        height=600,
    )
    fig.add_vline(x=users_median, line_dash="dot", annotation_text="median users")
    fig.add_hline(y=activity_median, line_dash="dot", annotation_text="median activity")
    fig.update_layout(
        xaxis_title="Registered users (log scale)",
        yaxis_title="Transactions per registered user (quarter)",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Bubble size = payment value (state level, map_transaction).")

    b_left, b_right = st.columns(2)
    with b_left:
        act = seg_df[seg_df["Segment"] == "Activation opportunity"].sort_values(
            "Registered_users", ascending=False
        ).head(10)
        if not act.empty:
            fig = px.bar(
                act.sort_values("Registered_users"),
                x="Registered_users",
                y="State_name",
                orientation="h",
                title="Activation opportunities (largest user bases)",
            )
            fig.update_layout(xaxis_title="Registered users", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
    with b_right:
        acq = seg_df[seg_df["Segment"] == "Acquisition opportunity"].sort_values(
            "Txn_per_user", ascending=False
        ).head(10)
        if not acq.empty:
            fig = px.bar(
                acq.sort_values("Txn_per_user"),
                x="Txn_per_user",
                y="State_name",
                orientation="h",
                title="Acquisition opportunities (most active small bases)",
            )
            fig.update_layout(xaxis_title="Transactions per user", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**State scorecard**")
    table = seg_df[
        [
            "State_name",
            "Segment",
            "Registered_users",
            "Registered_merchants",
            "Transaction_count",
            "Transaction_amount",
            "Txn_per_user",
            "Avg_ticket",
            "Users_per_merchant",
        ]
    ].rename(columns={"State_name": "State"})
    st.dataframe(
        table.sort_values("Registered_users", ascending=False).round(
            {"Txn_per_user": 2, "Avg_ticket": 2, "Users_per_merchant": 1}
        ),
        hide_index=True,
        use_container_width=True,
    )

    st.subheader("Findings")
    for line in cl.case4_findings(seg_df, users_median, activity_median, year, quarter):
        st.markdown(f"- {line}")

    with st.expander("How the segments are defined"):
        st.write(
            "States are split at the median registered-user count and the "
            "median transactions per registered user for the selected "
            "quarter. Registered users are a cumulative total while "
            "transactions are for the quarter, so transactions per user is "
            "a relative comparison between states, not an absolute rate."
        )
