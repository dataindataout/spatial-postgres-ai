import json

import branca.colormap as cm
import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from spatial_query import EXAMPLE_QUERY, execute_query, nl_to_spatial_sql


# build a folium choropleth map from query result rows, colored by median income
def build_map(rows: list[dict]) -> folium.Map:
    m = folium.Map(location=[35.99, -78.90], zoom_start=11)

    geo_rows = [r for r in rows if r.get("geom_json")]
    if not geo_rows:
        return m

    # scale colormap to the income range present in results
    incomes = [
        r["median_income"] for r in geo_rows if r.get("median_income") is not None
    ]
    colormap = cm.LinearColormap(
        colors=["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"],
        vmin=min(incomes),
        vmax=max(incomes),
        caption="Median Household Income ($)",
    )

    # assemble geojson feature collection from result rows
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": json.loads(row["geom_json"]),
                "properties": {
                    "geoid": row.get("geoid", ""),
                    "median_income": row.get("median_income"),
                    "total_pop": row.get("total_pop"),
                },
            }
            for row in geo_rows
        ],
    }

    # render polygons with income-based fill and a hover tooltip
    folium.GeoJson(
        feature_collection,
        style_function=lambda feature: {
            "fillColor": (
                colormap(feature["properties"]["median_income"])
                if feature["properties"]["median_income"] is not None
                else "#cccccc"
            ),
            "color": "#333333",
            "weight": 1,
            "fillOpacity": 0.65,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["geoid", "median_income", "total_pop"],
            aliases=["GEOID", "Median Income ($)", "Population"],
            localize=True,
        ),
    ).add_to(m)

    colormap.add_to(m)
    return m


# page config and header
st.set_page_config(page_title="Spatial Query Tool", layout="wide")
st.title("Spatial Query Tool")
st.caption("Natural language → PostGIS SQL → map")

query = st.text_area("Enter your question:", value=EXAMPLE_QUERY, height=100)

# run button: call claude then execute the generated sql, store results in session state
if st.button("Run Query"):
    with st.spinner("Generating SQL and querying database..."):
        try:
            sql = nl_to_spatial_sql(query)
            rows = execute_query(sql)
            st.session_state["sql"] = sql
            st.session_state["rows"] = rows
            st.session_state["error"] = None
        except Exception as e:
            st.session_state["sql"] = None
            st.session_state["rows"] = None
            st.session_state["error"] = str(e)

# display any errors, sql, results table, and map from session state
if st.session_state.get("error"):
    st.error(st.session_state["error"])

if st.session_state.get("sql"):
    st.subheader("Generated SQL")
    st.code(st.session_state["sql"], language="sql")

if st.session_state.get("rows") is not None:
    rows = st.session_state["rows"]
    display_df = pd.DataFrame(
        [{k: v for k, v in r.items() if k != "geom_json"} for r in rows]
    )
    st.subheader(f"Results ({len(rows)} row{'s' if len(rows) != 1 else ''})")
    st.dataframe(display_df, width="stretch")

    if any(r.get("geom_json") for r in rows):
        st.subheader("Map")
        st_folium(build_map(rows), width="100%", height=500)
