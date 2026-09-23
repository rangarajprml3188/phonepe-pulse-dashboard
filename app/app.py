"""
PhonePe Pulse Explore - Transaction View

Streamlit UI
-------------
app.py              -> UI
analysis/queries.py -> SQL/query layer
db/connection.py    -> PostgreSQL connection

Current data rules
------------------
State total count + amount:
    map_transaction

Transaction category counts:
    aggregated_transaction_state

District transaction counts:
    top_transaction

Important:
The local aggregated/top transaction JSON data contains
NULL transaction amounts.

Therefore this UI does NOT display fabricated
category-level or district-level transaction amounts.
"""

import json
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

from analysis import queries


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="PhonePe Pulse | Explore",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# PROJECT PATH
# ============================================================

# Always resolve paths relative to app.py.
# This avoids problems when Streamlit is launched from
# a different working directory.

APP_DIR = Path(__file__).resolve().parent

GEOJSON_PATH = (
    APP_DIR
    / "maps"
    / "india_states_merged.geojson"
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def format_number(value):
    """Format large numbers using readable units."""

    value = float(value)

    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f} B"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f} M"

    if value >= 1_000:
        return f"{value / 1_000:.2f} K"

    return f"{value:,.0f}"


def format_rupees(value):
    """Format rupee values using Indian units."""

    value = float(value)

    if value >= 1_00_00_000:
        return f"₹{value / 1_00_00_000:.2f} Cr"

    if value >= 1_00_000:
        return f"₹{value / 1_00_000:.2f} L"

    return f"₹{value:,.2f}"


def clean_name(value):
    """Convert database names into readable names."""

    if pd.isna(value):
        return "Unknown"

    return (
        str(value)
        .replace("-", " ")
        .replace("_", " ")
        .title()
    )


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div style="
        padding: 10px 0 5px 0;
        border-bottom: 1px solid #dddddd;
        margin-bottom: 20px;
    ">
        <h1 style="margin-bottom:0;">
            PhonePe Pulse
        </h1>
        <p style="margin-top:2px; color:#666;">
            BEAT OF PROGRESS
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# NAVIGATION
# ============================================================

nav1, nav2, nav3, nav4 = st.columns(4)

with nav1:
    st.markdown("### Explore")

with nav2:
    st.markdown("Trends")

with nav3:
    st.markdown("Insights")

with nav4:
    st.markdown("Fun Facts")


st.divider()


# ============================================================
# FILTERS
# ============================================================

years = queries.get_years()
states = queries.get_states()
quarters = queries.get_quarters()

if not years:
    st.error("No transaction year data available.")
    st.stop()

if not states:
    st.error("No state data available.")
    st.stop()


filter_col1, filter_col2, filter_col3 = st.columns(
    [2, 2, 3]
)


with filter_col1:

    selected_state = st.selectbox(
        "State",
        states,
        index=(
            states.index("maharashtra")
            if "maharashtra" in states
            else 0
        ),
        format_func=clean_name,
    )


with filter_col2:

    selected_year = st.selectbox(
        "Year",
        years,
        index=(
            years.index(2024)
            if 2024 in years
            else len(years) - 1
        ),
    )


with filter_col3:

    selected_quarter = st.selectbox(
        "Quarter",
        quarters,
        index=0,
        format_func=lambda q: f"Q{q}",
    )


st.divider()


# ============================================================
# PAGE TITLE
# ============================================================

st.subheader(
    f"Transactions — {clean_name(selected_state)}"
)

st.caption(
    f"PhonePe Pulse transaction data · "
    f"{selected_year} · Q{selected_quarter}"
)


# ============================================================
# LOAD PHONEPE-STYLE SUMMARY
# ============================================================

summary = queries.get_transaction_summary(
    selected_state,
    selected_year,
    selected_quarter,
)


if summary is None:

    st.warning(
        "No transaction data is available for "
        "the selected state and period."
    )

    st.stop()


# ============================================================
# SUMMARY METRICS
# ============================================================

transaction_count = summary["Transaction_count"]
transaction_amount = summary["Transaction_amount"]
average_value = summary["Average_transaction_value"]


st.markdown("## Transaction Summary")


metric1, metric2, metric3 = st.columns(3)


with metric1:

    st.metric(
        "Total Transactions",
        format_number(transaction_count),
    )


with metric2:

    st.metric(
        "Total Payment Value",
        format_rupees(transaction_amount),
    )


with metric3:

    st.metric(
        "Average Transaction Value",
        f"₹{average_value:,.2f}",
    )


st.divider()


# ============================================================
# TRANSACTION CATEGORIES
# ============================================================

st.markdown("## Transaction Categories")

category_df = summary["Categories"].copy()


if category_df.empty:

    st.info(
        "No transaction category data available."
    )

else:

    category_df["Transaction_type"] = (
        category_df["Transaction_type"]
        .apply(clean_name)
    )

    total_category_count = (
        category_df["Transaction_count"].sum()
    )

    # --------------------------------------------------------
    # Category cards
    # --------------------------------------------------------

    category_columns = st.columns(
        len(category_df)
    )

    for column, (_, row) in zip(
        category_columns,
        category_df.iterrows(),
    ):

        category = row["Transaction_type"]
        count = float(row["Transaction_count"])

        percentage = (
            count / total_category_count * 100
            if total_category_count > 0
            else 0
        )

        with column:

            st.metric(
                category,
                format_number(count),
                f"{percentage:.2f}% of transactions",
            )


    st.write("")


    # --------------------------------------------------------
    # Category chart
    # --------------------------------------------------------

    chart_df = category_df.copy()

    chart_df["Percentage"] = (
        chart_df["Transaction_count"]
        / total_category_count
        * 100
    )


    fig_category = px.bar(
        chart_df,
        x="Transaction_type",
        y="Transaction_count",
        text="Percentage",
        title="Transaction Count by Category",
    )


    fig_category.update_traces(
        texttemplate="%{text:.1f}%",
        textposition="outside",
    )


    fig_category.update_layout(
        yaxis_title="Transaction Count",
        xaxis_title="",
        showlegend=False,
    )


    st.plotly_chart(
        fig_category,
        use_container_width=True,
    )


st.divider()


# ============================================================
# INDIA TRANSACTION MAP
# ============================================================

st.markdown("## India Transaction Map")

try:

    # --------------------------------------------------------
    # Verify GeoJSON file exists
    # --------------------------------------------------------

    if not GEOJSON_PATH.exists():

        st.error(
            "India GeoJSON file was not found."
        )

        st.code(
            str(GEOJSON_PATH)
        )

        st.stop()


    # --------------------------------------------------------
    # Load merged India GeoJSON
    # --------------------------------------------------------

    with open(
        GEOJSON_PATH,
        "r",
        encoding="utf-8",
    ) as geojson_file:

        india_geojson = json.load(
            geojson_file
        )


    # --------------------------------------------------------
    # Load state transaction data
    # --------------------------------------------------------

    map_df = queries.get_state_transaction_totals(
        selected_year,
        selected_quarter,
    ).copy()


    if map_df.empty:

        st.info(
            "No state transaction data available for the map."
        )

    else:

        # ----------------------------------------------------
        # Database → GeoJSON state-name mapping
        # ----------------------------------------------------

        state_name_mapping = {

            "karnataka": "Karnataka",
            "maharashtra": "Maharashtra",
            "telangana": "Telangana",
            "andhra pradesh": "Andhra Pradesh",
            "uttar pradesh": "Uttar Pradesh",
            "rajasthan": "Rajasthan",
            "bihar": "Bihar",
            "madhya pradesh": "Madhya Pradesh",
            "west bengal": "West Bengal",
            "odisha": "Odisha",
            "tamil nadu": "Tamil Nadu",
            "gujarat": "Gujarat",
            "delhi": "NCT of Delhi",
            "haryana": "Haryana",
            "jharkhand": "Jharkhand",
            "chhattisgarh": "Chhattisgarh",
            "assam": "Assam",
            "kerala": "Kerala",
            "punjab": "Punjab",
            "uttarakhand": "Uttarakhand",
            "jammu & kashmir": "Jammu & Kashmir",
            "himachal pradesh": "Himachal Pradesh",
            "goa": "Goa",
            "arunachal pradesh": "Arunachal Pradesh",
            "tripura": "Tripura",
            "puducherry": "Puducherry",
            "chandigarh": "Chandigarh",
            "meghalaya": "Meghalaya",
            "nagaland": "Nagaland",
            "manipur": "Manipur",
            "sikkim": "Sikkim",
            "andaman & nicobar islands":
                "Andaman & Nicobar Island",
            "ladakh": "Ladakh",
            "mizoram": "Mizoram",
            "lakshadweep": "Lakshadweep",
        }


        # ----------------------------------------------------
        # Create GeoJSON state-name column
        # ----------------------------------------------------

        map_df["geo_state"] = (
            map_df["State"]
            .str.lower()
            .map(state_name_mapping)
        )


        # ----------------------------------------------------
        # Handle Dadra & Nagar Haveli + Daman & Diu
        # ----------------------------------------------------

        dadra_row = map_df[
            map_df["State"].str.lower()
            == "dadra & nagar haveli & daman & diu"
        ]


        if not dadra_row.empty:

            combined_count = float(
                dadra_row["Transaction_count"].iloc[0]
            )

            combined_amount = float(
                dadra_row["Transaction_amount"].iloc[0]
            )


            # Remove combined database row.
            map_df = map_df[
                map_df["State"].str.lower()
                != "dadra & nagar haveli & daman & diu"
            ]


            # Add the two GeoJSON polygons.
            extra_rows = pd.DataFrame(
                [
                    {
                        "State": "dadra & nagar haveli",
                        "Transaction_count":
                            combined_count,
                        "Transaction_amount":
                            combined_amount,
                        "geo_state":
                            "Dadara & Nagar Havelli",
                    },
                    {
                        "State": "daman & diu",
                        "Transaction_count":
                            combined_count,
                        "Transaction_amount":
                            combined_amount,
                        "geo_state":
                            "Daman & Diu",
                    },
                ]
            )


            map_df = pd.concat(
                [map_df, extra_rows],
                ignore_index=True,
            )


        # ----------------------------------------------------
        # Check for unmapped states
        # ----------------------------------------------------

        unmapped_states = map_df[
            map_df["geo_state"].isna()
        ]["State"].tolist()


        if unmapped_states:

            st.warning(
                "Some database states could not be matched "
                "to the GeoJSON: "
                + ", ".join(unmapped_states)
            )

            map_df = map_df[
                map_df["geo_state"].notna()
            ]


        # ----------------------------------------------------
        # Create choropleth map
        # ----------------------------------------------------

        fig_map = px.choropleth(
            map_df,
            geojson=india_geojson,
            locations="geo_state",
            featureidkey="properties.ST_NM",
            color="Transaction_count",
            hover_name="geo_state",
            hover_data={
                "Transaction_count": ":,.0f",
                "Transaction_amount": ":,.2f",
                "geo_state": False,
            },
            title=(
                f"State-wise Transactions — "
                f"{selected_year} Q{selected_quarter}"
            ),
        )


        # ----------------------------------------------------
        # Map appearance
        # ----------------------------------------------------

        fig_map.update_geos(
            fitbounds="locations",
            visible=False,
        )


        fig_map.update_layout(
            height=850,
            margin={
                "r": 0,
                "t": 60,
                "l": 0,
                "b": 0,
            },
            coloraxis_colorbar_title=(
                "Transaction Count"
            ),
        )


        st.plotly_chart(
            fig_map,
            use_container_width=True,
        )


        st.caption(
            "Map shows state-level transaction counts. "
            "Payment value is available at state level."
        )


except FileNotFoundError:

    st.error(
        "India GeoJSON file was not found."
    )

    st.code(
        str(GEOJSON_PATH)
    )


except Exception as error:

    st.error(
        "Unable to load the India transaction map."
    )

    st.exception(error)


st.divider()


# ============================================================
# STATES / DISTRICTS
# ============================================================

st.markdown("## States / Districts")


location_tab1, location_tab2 = st.tabs(
    [
        "States",
        "Districts",
    ]
)


# ============================================================
# STATES VIEW
# ============================================================

with location_tab1:

    state_df = queries.get_state_transaction_totals(
        selected_year,
        selected_quarter,
    )


    if state_df.empty:

        st.info(
            "No state transaction data available."
        )

    else:

        state_display = state_df.copy()

        state_display["State"] = (
            state_display["State"]
            .apply(clean_name)
        )


        # ----------------------------------------------------
        # State transaction summary
        # ----------------------------------------------------

        st.markdown(
            "### State Transaction Summary"
        )


        st.dataframe(
            state_display[
                [
                    "State",
                    "Transaction_count",
                    "Transaction_amount",
                ]
            ].head(10),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# DISTRICTS VIEW
# ============================================================

with location_tab2:

    district_df = queries.get_district_transaction_totals(
        selected_state,
        selected_year,
        selected_quarter,
    )


    if district_df.empty:

        st.info(
            "No district transaction data available."
        )

    else:

        district_display = district_df.copy()


        district_display["District"] = (
            district_display["District"]
            .apply(clean_name)
        )


        district_display = (
            district_display[
                district_display["District"] != "Unknown"
            ]
            .sort_values(
                "Transaction_count",
                ascending=False,
            )
        )


        st.markdown(
            f"### Top Districts — "
            f"{clean_name(selected_state)}"
        )


        # ----------------------------------------------------
        # Top district cards
        # ----------------------------------------------------

        top_districts = (
            district_display
            .head(5)
            .reset_index(drop=True)
        )


        if not top_districts.empty:

            district_columns = st.columns(
                min(len(top_districts), 5)
            )


            for column, (_, row) in zip(
                district_columns,
                top_districts.iterrows(),
            ):

                with column:

                    st.metric(
                        row["District"],
                        format_number(
                            row["Transaction_count"]
                        ),
                    )


        st.write("")


        # ----------------------------------------------------
        # District chart
        # ----------------------------------------------------

        chart_district = (
            district_display
            .head(15)
            .sort_values(
                "Transaction_count",
                ascending=True,
            )
        )


        if not chart_district.empty:

            fig_district = px.bar(
                chart_district,
                x="Transaction_count",
                y="District",
                orientation="h",
                title=(
                    f"Top Districts — "
                    f"{clean_name(selected_state)}"
                ),
            )


            fig_district.update_layout(
                xaxis_title="Transaction Count",
                yaxis_title="",
            )


            st.plotly_chart(
                fig_district,
                use_container_width=True,
            )


        # ----------------------------------------------------
        # District table
        # ----------------------------------------------------

        st.markdown(
            "### District Details"
        )


        district_table = district_display[
            [
                "District",
                "Transaction_count",
            ]
        ].head(20)


        st.dataframe(
            district_table,
            use_container_width=True,
            hide_index=True,
        )


st.divider()


# ============================================================
# DATA LIMITATION
# ============================================================

with st.expander(
    "About the transaction data"
):

    st.write(
        """
        The local PhonePe Pulse dataset contains valid
        transaction amounts at the state level through
        `map_transaction`.

        The aggregated transaction category and district
        records contain missing transaction amounts.

        Therefore this dashboard uses:

        • State-level payment value from map_transaction

        • Category transaction counts from
          aggregated_transaction_state

        • District transaction counts from top_transaction

        Category-level and district-level payment values
        are not estimated or fabricated.
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "PhonePe Pulse Explore — "
    "PostgreSQL + Python + Streamlit"
)