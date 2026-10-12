"""
PhonePe Pulse - Business Case Study 5

User Engagement and Growth Strategy

DATA RULE
---------
The source data has no app-open counts, so engagement is measured as
transactions per registered user. Registered users is cumulative, so the
ratio is a relative comparison, not an absolute usage rate.

Place this file in app/pages/.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import case_logic as cl
from analysis import case_logic_5 as cl5
from analysis import case_queries as cq
from analysis import case_queries_5 as q5

st.set_page_config(
    page_title="PhonePe Pulse | Case 5",
    page_icon="📊",
    layout="wide",
)


def clean_name(value):
    if pd.isna(value):
        return "Unknown"
    return str(value).replace("-", " ").replace("_", " ").title()


st.title("Case 5: User Engagement and Growth Strategy")
st.caption(
    "Engagement = transactions per registered user. The source data has no "
    "app-open counts, so this is the closest available measure."
)

periods = cq.get_periods()
if not periods:
    st.error("No data found. Run phonepe_master.py first.")
    st.stop()

years = sorted({y for y, _ in periods})
c1, c2, c3, _ = st.columns([1, 1, 2, 3])
with c1:
    year = st.selectbox("Year", years, index=len(years) - 1)
with c2:
    quarters = sorted({q for y, q in periods if y == year})
    quarter = st.selectbox(
        "Quarter", quarters, index=len(quarters) - 1, format_func=lambda q: f"Q{q}"
    )
with c3:
    top_n = st.slider("Show top N", min_value=5, max_value=20, value=10)

label = cl.period_label(year, quarter)

# ------------------------------------------------------------
# Data
# ------------------------------------------------------------
raw = q5.get_engagement_series()
if raw.empty:
    st.error("No engagement data found.")
    st.stop()

state_all = cl5.add_yoy(cl5.add_engagement(raw))
nat_all = cl5.national_series(raw)

period_df = state_all[
    (state_all["Year"] == year) & (state_all["Quarter"] == quarter)
].copy()
nat_row_df = nat_all[(nat_all["Year"] == year) & (nat_all["Quarter"] == quarter)]
national_row = nat_row_df.iloc[0] if not nat_row_df.empty else None

if period_df.empty or national_row is None:
    st.warning(f"No data for {label}.")
    st.stop()

period_df["State_name"] = period_df["State"].apply(clean_name)

# ------------------------------------------------------------
# National view
# ------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Registered users", cl.compact(national_row["Registered_users"]))
k2.metric("User growth (YoY)", cl.pct(national_row["User_growth_pct"]))
k3.metric("Transactions per user", f"{national_row['Txn_per_user']:.2f}")
k4.metric("Engagement change (YoY)", cl.pct(national_row["Engagement_change_pct"]))

trend = nat_all.copy()
trend["Period"] = [
    cl.period_label(y, q) for y, q in zip(trend["Year"], trend["Quarter"])
]
fig = px.line(
    trend,
    x="Period",
    y="Txn_per_user",
    markers=True,
    title="National engagement: transactions per registered user, by quarter",
)
fig.update_layout(xaxis_title="", yaxis_title="Transactions per user")
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ------------------------------------------------------------
# State engagement
# ------------------------------------------------------------
st.subheader("State engagement")

ranked = period_df.dropna(subset=["Txn_per_user"]).sort_values(
    "Txn_per_user", ascending=False
)
left, right = st.columns(2)
with left:
    d = ranked.head(top_n)
    fig = px.bar(
        d.sort_values("Txn_per_user"),
        x="Txn_per_user",
        y="State_name",
        orientation="h",
        title=f"Most engaged states, {label}",
    )
    fig.update_layout(xaxis_title="Transactions per user", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)
with right:
    d = ranked.tail(top_n)
    fig = px.bar(
        d.sort_values("Txn_per_user", ascending=False),
        x="Txn_per_user",
        y="State_name",
        orientation="h",
        title=f"Least engaged states, {label}",
    )
    fig.update_layout(xaxis_title="Transactions per user", yaxis_title="")
    st.plotly_chart(fig, use_container_width=True)

# Heatmap of the last 8 quarters.
hm = state_all.copy()
hm["_key"] = [cl.period_key(y, q) for y, q in zip(hm["Year"], hm["Quarter"])]
upto = hm[hm["_key"] <= cl.period_key(year, quarter)]
recent = sorted(upto["_key"].unique())[-8:]
hm = upto[upto["_key"].isin(recent)].copy()
hm["Period"] = [cl.period_label(y, q) for y, q in zip(hm["Year"], hm["Quarter"])]
order = [
    cl.period_label(y, q)
    for y, q in sorted({(int(y), int(q)) for y, q in zip(hm["Year"], hm["Quarter"])})
]
pivot = hm.pivot_table(
    index="State", columns="Period", values="Txn_per_user"
).reindex(columns=order)
pivot.index = [clean_name(s) for s in pivot.index]
fig = px.imshow(
    pivot,
    aspect="auto",
    color_continuous_scale="Blues",
    title="Transactions per registered user, last 8 quarters",
    height=max(500, 22 * len(pivot)),
)
fig.update_layout(xaxis_title="", yaxis_title="")
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ------------------------------------------------------------
# Growth strategy quadrant
# ------------------------------------------------------------
st.subheader("Growth strategy: user growth vs engagement change")

classified = cl5.classify_states(period_df, national_row)
if classified.empty:
    st.info(
        f"Year-over-year comparison needs {year - 1} Q{quarter}, which is "
        "not available for this period."
    )
else:
    classified["State_name"] = classified["State"].apply(clean_name)
    seg_colors = {
        "Scaling and deepening": "#2e9e5b",
        "Growing without depth": "#e0a526",
        "Deepening on a mature base": "#3b7dd8",
        "Lagging": "#d64545",
    }
    fig = px.scatter(
        classified,
        x="User_growth_pct",
        y="Engagement_change_pct",
        size="Registered_users",
        color="Segment",
        color_discrete_map=seg_colors,
        hover_name="State_name",
        hover_data={
            "User_growth_pct": ":.1f",
            "Engagement_change_pct": ":.1f",
            "Registered_users": ":,.0f",
            "State_name": False,
        },
        size_max=45,
        title=f"Each state versus India, {label} vs {year - 1} Q{quarter}",
        height=600,
    )
    fig.add_vline(
        x=national_row["User_growth_pct"],
        line_dash="dot",
        annotation_text="India user growth",
    )
    fig.add_hline(
        y=national_row["Engagement_change_pct"],
        line_dash="dot",
        annotation_text="India engagement change",
    )
    fig.update_layout(
        xaxis_title="Registered user growth, YoY (%)",
        yaxis_title="Engagement change, YoY (%)",
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Bubble size = registered users. Dotted lines mark the national figures.")

    seg_table = classified[
        [
            "State_name",
            "Segment",
            "Registered_users",
            "User_growth_pct",
            "Txn_per_user",
            "Engagement_change_pct",
        ]
    ].rename(
        columns={
            "State_name": "State",
            "User_growth_pct": "User growth %",
            "Txn_per_user": "Txn per user",
            "Engagement_change_pct": "Engagement change %",
        }
    )
    st.dataframe(
        seg_table.sort_values(["Segment", "Registered_users"], ascending=[True, False]).round(
            {"User growth %": 1, "Txn per user": 2, "Engagement change %": 1}
        ),
        hide_index=True,
        use_container_width=True,
    )

st.divider()

# ------------------------------------------------------------
# Districts
# ------------------------------------------------------------
st.subheader("District engagement")

district_df = q5.get_district_engagement(year, quarter)
district_df = cl5.add_district_engagement(district_df) if not district_df.empty else district_df

if district_df.empty:
    st.info(
        "No districts could be matched between the top-transaction and "
        "top-user lists for this period. This can happen if district names "
        "differ between the two tables or if top_user was not loaded with "
        "district names."
    )
else:
    d = district_df.dropna(subset=["Txn_per_user"]).copy()
    d["Label"] = [
        f"{clean_name(x)} ({clean_name(s)})" for x, s in zip(d["District"], d["State"])
    ]
    d = d.sort_values("Txn_per_user", ascending=False)
    lcol, rcol = st.columns(2)
    with lcol:
        fig = px.bar(
            d.head(top_n).sort_values("Txn_per_user"),
            x="Txn_per_user",
            y="Label",
            orientation="h",
            title=f"Most engaged districts, {label}",
            height=max(380, 34 * min(top_n, len(d))),
        )
        fig.update_layout(xaxis_title="Transactions per user", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    with rcol:
        fig = px.bar(
            d.tail(top_n).sort_values("Txn_per_user", ascending=False),
            x="Txn_per_user",
            y="Label",
            orientation="h",
            title=f"Least engaged districts, {label}",
            height=max(380, 34 * min(top_n, len(d))),
        )
        fig.update_layout(xaxis_title="Transactions per user", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"{len(d)} districts appear in both published top lists. PhonePe "
        "publishes only the top 10 per state, so this is not every district."
    )

# ------------------------------------------------------------
# Findings
# ------------------------------------------------------------
st.subheader("Findings")
for line in cl5.case5_findings(
    national_row, classified, period_df, district_df, year, quarter
):
    st.markdown(f"- {line}")

with st.expander("How engagement is measured"):
    st.write(
        "The Pulse files used here contain registered users and transaction "
        "counts but no app-open counts, so engagement is transactions in the "
        "quarter divided by registered users at quarter end. Registered users "
        "is cumulative (it includes inactive accounts), so the ratio is useful "
        "for comparing states and quarters, not as an absolute usage rate. "
        "Segments compare each state's year-over-year changes with the "
        "national figures."
    )
