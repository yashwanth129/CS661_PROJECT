import streamlit as st
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.cluster import AgglomerativeClustering

st.set_page_config(
    page_title="Mortality Clustering page",  
    page_icon="🌍",  
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #FFFFFF;
    }

    /* General text color */
    .stMarkdown, .stText, div[data-testid="stMarkdownContainer"], span, p {
        color: #000000 !important;
    }

    /* Title (st.title) */
    .stApp h1, h1 {
        color: #000000 !important
    }

    /* Headers and subheaders (st.header, st.subheader) */
    .stApp h2, h2,
    .stApp h3, h3 {
        color: #000000 !important;  /* Dark red */
    }

    /* Button style */
    .stButton button {
        color: #033443 !important;  /* Text color inside button */
        background-color: #ADD8E6 !important;  /* Button background color */
        border: 1px solid #000000 !important;  /* Optional: add border to match button color */
    }

    /* Ensure that the text remains white even in hover and active states */
    .stButton > button {
        color: #FFFFFF !important;  /* Make sure button text is white */
    }

    .stButton button:hover, .stButton button:active {
        color: #FFFFFF !important;  /* Button text stays white when hovered or clicked */
    }

    </style>
    """,
    unsafe_allow_html=True
)

@st.cache_data
def load_data(file):
    import os
    print("----")
    print(os.getcwd())
    print(file)
    data = pd.read_parquet(file)
    cause_map = pd.read_csv("pages\\cause_mapping.csv")
    location_map = pd.read_csv("pages\\location_mapping.csv")
    return data, cause_map, location_map

st.title("Mortality Analysis using Clustering")

if "use_infant" not in st.session_state:
    st.session_state.use_infant = False

data_option = st.radio(
    "Select Data:",
    ["Infant Mortality Data", "General Disease Data"],
    index=0 if st.session_state.get("use_infant", False) else 1,
    horizontal=True
)

st.session_state.use_infant = (data_option == "Infant Mortality Data")

file_path = "pages\\infant_mortality_data.parquet" if st.session_state.use_infant else "pages\\filtered_data.parquet"
data, cause_map, location_map = load_data(file_path)

data = data.merge(cause_map, on="cause_id", how="left")
data = data.merge(location_map, on="location_id", how="left")

data_pd = data
cause_map_pd = cause_map
location_map_pd = location_map

if "selected_causes" not in st.session_state:
    st.session_state.selected_causes = []
if "year_range" not in st.session_state:
    st.session_state.year_range = (1980, 2021)
if "cluster_labels" not in st.session_state:
    st.session_state.cluster_labels = {}
if "pivot" not in st.session_state:
    st.session_state.pivot = pd.DataFrame()

selected_causes = st.multiselect("Select causes:", cause_map_pd["cause_name"].unique(), default=st.session_state.selected_causes)

col1, col2 = st.columns(2)
with col1:
    year_from = st.number_input("Year from", min_value=int(data_pd["year"].min()), max_value=int(data_pd["year"].max()), value=st.session_state.year_range[0])
with col2:
    year_to = st.number_input("Year to", min_value=int(data_pd["year"].min()), max_value=int(data_pd["year"].max()), value=st.session_state.year_range[1])

k = st.number_input("Number of clusters (K):", min_value=2, max_value=20, value=3, step=1)
gender_option = st.radio("Select gender:", ["Both", "Male", "Female"])

if st.button("OK") and selected_causes:
    st.session_state.selected_causes = selected_causes
    st.session_state.year_range = (year_from, year_to)

    filtered = data_pd[ (data_pd["cause_name"].isin(selected_causes)) & (data_pd["year"].between(year_from, year_to)) ]

    if gender_option != "Both":
        gender_map = {"Male": 1, "Female": 2}
        filtered = filtered[filtered["sex_id"] == gender_map[gender_option]]
    else:
        filtered = filtered[filtered["sex_id"] == 3]

    if filtered.empty:
        st.warning("No data available for the selected filters.")
    else:
        filtered["cause_year"] = filtered["cause_name"] + "_" + filtered["year"].astype(str)
        pivot = filtered.pivot_table(index="location_id", columns="cause_year", values="val", aggfunc="mean").fillna(0)

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(pivot)

        pca = PCA(n_components=0.95) 
        X_pca = pca.fit_transform(X_scaled)

        # Apply KMeans on PCA reduced data
        model = KMeans(n_clusters=k, random_state=0, n_init="auto")
        cluster_labels = model.fit_predict(X_pca)
        # Apply Agglomerative Clustering on PCA reduced data
        #model = AgglomerativeClustering(n_clusters=k, linkage="ward")
        #cluster_labels = model.fit_predict(X_pca)

        st.session_state.cluster_labels = cluster_labels
        st.session_state.pivot = pivot

if not st.session_state.pivot.empty:
    pivot = st.session_state.pivot.copy()
    pivot["cluster"] = st.session_state.cluster_labels
    pivot = pivot.reset_index()
    loc_cluster = pivot.merge(location_map_pd, on="location_id", how="left")

    cluster_colors = px.colors.qualitative.Safe + px.colors.qualitative.Bold + px.colors.qualitative.Prism
    color_map = {i: cluster_colors[i % len(cluster_colors)] for i in range(k)}

    loc_cluster["cluster_num"] = loc_cluster["cluster"].astype(str)
    loc_cluster["cluster_num"] = pd.Categorical(loc_cluster["cluster_num"], categories=[str(i) for i in range(k)], ordered=True)
    loc_cluster = loc_cluster.sort_values("cluster_num")

    fig = px.scatter_geo(
        loc_cluster,
        locations="location_name",
        locationmode="country names",
        color="cluster_num",
        title="World Clusters",
        projection="orthographic",
        color_discrete_map={str(i): color_map[i] for i in range(k)}
    )

    fig.update_geos(
        showcoastlines=True, coastlinecolor="gray", showland=True,
        landcolor="rgb(240, 240, 240)", showcountries=True, countrycolor="white",
        showocean=True, oceancolor="LightBlue", showlakes=True, lakecolor="LightBlue",
        projection_type="orthographic", resolution=110, lataxis_showgrid=False, lonaxis_showgrid=False
    )
    
    fig.update_layout(
        height=700, geo=dict(bgcolor='rgba(0,0,0,0)'),
        margin=dict(l=0, r=0, t=50, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        title=dict(x=0.5, xanchor='center'),
        legend=dict(
            title="Cluster", 
            x=0.9, xanchor="left", y=0.5, yanchor="middle",
            font=dict(color='black') , # Set the legend text color to black
            title_font=dict(color='black')
        )
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Cluster Summary Table")

    summary_data = []
    for cluster_id in range(k):
        cluster_locs = loc_cluster[loc_cluster["cluster"] == cluster_id]["location_id"]
        cluster_summary = data_pd[ (data_pd["location_id"].isin(cluster_locs)) & (data_pd["cause_name"].isin(selected_causes)) & (data_pd["year"].between(*st.session_state.year_range)) ]

        if gender_option != "Both":
            gender_map = {"Male": 1, "Female": 2}
            cluster_summary = cluster_summary[cluster_summary["sex_id"] == gender_map[gender_option]]
        else:
            cluster_summary = cluster_summary[cluster_summary["sex_id"] == 3]

        if cluster_summary.empty:
            st.write(f"No data available for Cluster {cluster_id} summary.")
        else:
            grouped = cluster_summary.groupby("cause_name")["val"].agg(['mean', 'median', 'std'])
            grouped["cluster"] = cluster_id
            summary_data.append(grouped.reset_index())

    if summary_data:
        cluster_summary_df = pd.concat(summary_data)
        cluster_summary_pivot = cluster_summary_df.pivot(index="cause_name", columns="cluster", values="mean")
        normalized = cluster_summary_pivot.div(cluster_summary_pivot.max(axis=1), axis=0).fillna(0)

        fig, ax = plt.subplots(figsize=(10, 6))
        sns.heatmap(
            normalized,
            cmap="YlGnBu",
            annot=cluster_summary_pivot.round(1),
            fmt=".1f",
            linewidths=.5,
            ax=ax,
            cbar_kws={'label': 'Relative Intensity per Cause'}
        )
        ax.set_title("Mean Value per Cause by Cluster", fontsize=14)
        st.pyplot(fig)

    st.subheader("Cluster Trends Over Time")

    selected_cause = st.selectbox("Select a cause to view its animated trend:", st.session_state.selected_causes)

    if selected_cause:
        subset = data_pd[ (data_pd["cause_name"] == selected_cause) & (data_pd["location_id"].isin(loc_cluster["location_id"])) & (data_pd["year"].between(*st.session_state.year_range)) ]

        if gender_option != "Both":
            gender_map = {"Male": 1, "Female": 2}
            subset = subset[subset["sex_id"] == gender_map[gender_option]]
        else:
            subset = subset[subset["sex_id"] == 3]

        subset = subset.merge(loc_cluster[["location_id", "cluster"]], on="location_id")
        grouped = subset.groupby(["cluster", "year"])["val"].mean().reset_index()

        if grouped.empty:
            st.write("No data available for the selected cause's animated trend.")
        else:
            fig = go.Figure()
            years = sorted(grouped["year"].unique())
            for cluster in grouped["cluster"].unique():
                df_cluster = grouped[grouped["cluster"] == cluster]
                fig.add_trace(go.Scatter(x=df_cluster["year"], y=df_cluster["val"], name=f"Cluster {cluster}", line=dict(color=color_map[cluster])))

            frames = [
                go.Frame(
                    data=[go.Scatter(
                        x=df[df["year"] <= year]["year"],
                        y=df[df["year"] <= year]["val"],
                        mode='lines+markers'
                    ) for _, df in grouped.groupby("cluster")],
                    name=str(year)
                ) for year in years
            ]

            fig.frames = frames
            fig.update_layout(
                title=f"{selected_cause} Trend by Cluster",
                plot_bgcolor='#FFFFFF',  
                paper_bgcolor='#FFFFFF',  
                font=dict(color='black'),  # General font color
                title_font=dict(color='black'),  # Title font color
                xaxis=dict(
                    title="Year",
                    title_font=dict(color='black'),
                    tickfont=dict(color='black')  # Ticks (numbers) on X-axis
                ),
                yaxis=dict(
                    title="Value",
                    title_font=dict(color='black'),
                    tickfont=dict(color='black')  # Ticks (numbers) on Y-axis
                ),
                legend=dict(font=dict(color='black')),  # Legend font
                updatemenus=[{
                    "buttons": [
                        {"label": "Play", "method": "animate", "args": [None, {"frame": {"duration": 800}, "fromcurrent": True}]},
                        {"label": "Pause", "method": "animate", "args": [[None], {"frame": {"duration": 0}, "mode": "immediate"}]}
                    ],
                    "direction": "left",
                    "pad": {"r": 10, "t": 87},
                    "showactive": False,
                    "type": "buttons",
                    "x": 0.1,
                    "xanchor": "right",
                    "y": 0,
                    "yanchor": "top"
                }]
            )

            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Select causes and click OK to start.")
