"""
PhonePe Pulse - Business Case Studies 7 and 8

Case 7: Transaction Analysis Across States and Districts
Case 8: User Registration Analysis

Place this file in app/pages/ next to 1_Case_Studies.py.

DATA RULES
----------
- Payment value exists only at state level (map_transaction).
- Districts are ranked by transaction count / registered users.
- Pin codes are not loaded by the ETL, so analysis stops at district level.
- Registered users is a cumulative total; new registrations in a quarter
  are the difference from the previous quarter.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import case_logic as cl
from analysis import case_logic_78 as cl78
from analysis import case_queries as cq
from analysis import case_queries_78 as q78

st.set_page_config(
    page_title="PhonePe Pulse | Cases 7 and 8",
    page_icon="📊",
    layout="wide",
)


def clean_name(value):
    if pd.isna(value):
        return "Unknown"
    return str(value).replace("-", " ").replace("_", " ").title()


# ============================================================
# HEADER + FILTERS
# ============================================================

st.title("Business Case Studies: Rankings")
st.caption(
    "Top states and districts for transactions (case 7) and user "
    "registrations (case 8). Pin codes are not part of the loaded data."
)

periods = cq.get_periods()
if not periods:
    st.error("No transaction data found. Run phonepe_master.py first.")
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

tab7, tab8 = st.tabs(
    ["Case 7 - Transactions", "Case 8 - User Registrations"]
)


# ============================================================
# CASE 7 - TRANSACTIONS ACROSS STATES AND DISTRICTS
# ============================================================

with tab7:
    st.header("Transaction Analysis Across States and Districts")
    st.write(
        "Which states and districts lead on transaction volume and value, "
        "and where is marketing effort best targeted?"
    )

    states = q78.get_state_transactions(year, quarter)
    if states.empty:
        st.warning(f"No transaction data for {label}.")
    else:
        s = cl78.add_state_shares(states)
        s["State_name"] = s["State"].apply(clean_name)

        k1, k2, k3 = st.columns(3)
        k1.metric("Transactions", cl.compact(s["Transaction_count"].sum()))
        k2.metric("Payment value", cl.rupees(s["Transaction_amount"].sum()))
        top5 = (
            s.sort_values("Transaction_count", ascending=False)["Count_share_pct"]
            .head(5)
            .sum()
        )
        k3.metric("Top 5 states' share of volume", cl.pct(top5))

        left, right = st.columns(2)
        with left:
            d = s.sort_values("Transaction_count", ascending=False).head(top_n)
            fig = px.bar(
                d.sort_values("Transaction_count"),
                x="Transaction_count",
                y="State_name",
                orientation="h",
                title=f"Top {top_n} states by transaction count, {label}",
            )
            fig.update_layout(xaxis_title="Transactions", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            d = s.sort_values("Transaction_amount", ascending=False).head(top_n)
            fig = px.bar(
                d.sort_values("Transaction_amount"),
                x="Transaction_amount",
                y="State_name",
                orientation="h",
                title=f"Top {top_n} states by payment value, {label}",
            )
            fig.update_layout(xaxis_title="Payment value (₹)", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("**State table**")
        table = s[
            [
                "State_name",
                "Transaction_count",
                "Count_share_pct",
                "Transaction_amount",
                "Amount_share_pct",
                "Avg_ticket",
            ]
        ].rename(
            columns={
                "State_name": "State",
                "Count_share_pct": "Count share %",
                "Amount_share_pct": "Value share %",
                "Avg_ticket": "Avg ticket (₹)",
            }
        )
        st.dataframe(
            table.sort_values("Transaction_count", ascending=False).round(
                {"Count share %": 2, "Value share %": 2, "Avg ticket (₹)": 2}
            ),
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        # ---------------- districts ----------------
        st.subheader("Districts")
        st.caption(
            "District rankings use transaction count. The source data has "
            "no district-level value."
        )

        districts = q78.get_top_districts_transactions(year, quarter, limit=top_n)
        if districts.empty:
            st.info("No district data for this period.")
        else:
            dd = districts.copy()
            dd["Label"] = [
                f"{clean_name(d)} ({clean_name(st_)})"
                for d, st_ in zip(dd["District"], dd["State"])
            ]
            fig = px.bar(
                dd.sort_values("Transaction_count"),
                x="Transaction_count",
                y="Label",
                orientation="h",
                title=f"Top {top_n} districts in India by transaction count, {label}",
                height=max(380, 34 * len(dd)),
            )
            fig.update_layout(xaxis_title="Transactions", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

        pick = st.selectbox(
            "Drill into a state",
            sorted(s["State"].unique()),
            format_func=clean_name,
            key="case7_state",
        )
        sd = q78.get_state_districts_transactions(pick, year, quarter)
        if sd.empty:
            st.info("No district data for this state and period.")
        else:
            fig = px.bar(
                sd.assign(District=sd["District"].apply(clean_name)).sort_values(
                    "Transaction_count"
                ),
                x="Transaction_count",
                y="District",
                orientation="h",
                title=f"Top districts in {clean_name(pick)}, {label}",
            )
            fig.update_layout(xaxis_title="Transactions", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "PhonePe publishes up to 10 districts per state, so this is "
                "the published top list, not every district."
            )

        st.subheader("Findings")
        all_districts = q78.get_top_districts_transactions(year, quarter, limit=10)
        for line in cl78.case7_findings(states, all_districts, year, quarter):
            st.markdown(f"- {line}")


# ============================================================
# CASE 8 - USER REGISTRATIONS
# ============================================================

with tab8:
    st.header("User Registration Analysis")
    st.write(
        "Which states and districts have the most registered users, and "
        "where are registrations growing fastest?"
    )

    py, pq = cl78.prev_period(year, quarter)
    reg = q78.get_state_registrations(year, quarter, py, pq)

    if reg.empty:
        st.warning(f"No registration data for {label}.")
    else:
        r = reg.copy()
        r["State_name"] = r["State"].apply(clean_name)

        total_users = r["Registered_users"].sum()
        net_new = r["Net_new_users"].sum(min_count=1)

        k1, k2, k3 = st.columns(3)
        k1.metric("Registered users", cl.compact(total_users))
        k2.metric(
            f"Net new vs {cl.period_label(py, pq)}",
            cl.compact(net_new) if pd.notna(net_new) else "n/a",
        )
        k3.metric(
            "Top 5 states' share",
            cl.pct(
                r.sort_values("Registered_users", ascending=False)["Registered_users"]
                .head(5)
                .sum()
                / total_users
                * 100
            ),
        )

        left, right = st.columns(2)
        with left:
            d = r.sort_values("Registered_users", ascending=False).head(top_n)
            fig = px.bar(
                d.sort_values("Registered_users"),
                x="Registered_users",
                y="State_name",
                orientation="h",
                title=f"Top {top_n} states by registered users, {label}",
            )
            fig.update_layout(xaxis_title="Registered users", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        with right:
            d = (
                r.dropna(subset=["Net_new_users"])
                .sort_values("Net_new_users", ascending=False)
                .head(top_n)
            )
            if d.empty:
                st.info(
                    "Net new users need the previous quarter, which isn't "
                    "available for this period."
                )
            else:
                fig = px.bar(
                    d.sort_values("Net_new_users"),
                    x="Net_new_users",
                    y="State_name",
                    orientation="h",
                    title=f"Top {top_n} states by net new users, {label}",
                )
                fig.update_layout(xaxis_title="Net new users", yaxis_title="")
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("**State table**")
        table = r[
            ["State_name", "Registered_users", "Net_new_users", "QoQ_growth_pct"]
        ].rename(
            columns={
                "State_name": "State",
                "Net_new_users": "Net new users",
                "QoQ_growth_pct": "QoQ growth %",
            }
        )
        st.dataframe(
            table.sort_values("Registered_users", ascending=False).round(
                {"QoQ growth %": 2}
            ),
            hide_index=True,
            use_container_width=True,
        )

        st.divider()

        # ---------------- districts ----------------
        st.subheader("Districts")

        health = q78.get_top_user_health()
        data_ok = health["named_districts"] > 0 and health["nonzero_users"] > 0
        if not data_ok:
            st.warning(
                "The top_user table has no district names or no user counts. "
                "The ETL may be reading the wrong JSON keys for the top/user "
                "files. District charts are skipped until this is fixed."
            )
            all_districts_u = pd.DataFrame()
        else:
            all_districts_u = q78.get_top_districts_users(year, quarter, limit=top_n)
            if all_districts_u.empty:
                st.info("No district data for this period.")
            else:
                dd = all_districts_u.copy()
                dd["Label"] = [
                    f"{clean_name(d)} ({clean_name(st_)})"
                    for d, st_ in zip(dd["District"], dd["State"])
                ]
                fig = px.bar(
                    dd.sort_values("Registered_users"),
                    x="Registered_users",
                    y="Label",
                    orientation="h",
                    title=f"Top {top_n} districts in India by registered users, {label}",
                    height=max(380, 34 * len(dd)),
                )
                fig.update_layout(xaxis_title="Registered users", yaxis_title="")
                st.plotly_chart(fig, use_container_width=True)

            pick = st.selectbox(
                "Drill into a state",
                sorted(r["State"].unique()),
                format_func=clean_name,
                key="case8_state",
            )
            sd = q78.get_state_districts_users(pick, year, quarter)
            if sd.empty:
                st.info("No district data for this state and period.")
            else:
                fig = px.bar(
                    sd.assign(District=sd["District"].apply(clean_name)).sort_values(
                        "Registered_users"
                    ),
                    x="Registered_users",
                    y="District",
                    orientation="h",
                    title=f"Top districts in {clean_name(pick)}, {label}",
                )
                fig.update_layout(xaxis_title="Registered users", yaxis_title="")
                st.plotly_chart(fig, use_container_width=True)
                st.caption(
                    "PhonePe publishes up to 10 districts per state, so this "
                    "is the published top list, not every district."
                )

        st.subheader("Findings")
        for line in cl78.case8_findings(reg, all_districts_u, year, quarter):
            st.markdown(f"- {line}")

        with st.expander("How new registrations are measured"):
            st.write(
                "Registered users is a cumulative total at the end of each "
                "quarter. Net new users is this quarter's total minus the "
                "previous quarter's total, so it can understate gross "
                "sign-ups if users are removed or merged."
            )
