"""
app.py file should be next to the *data/* directory that already
holds GBD.csv, locations_with_codes.csv, cause_mapping.csv and
country_classification_by_income.xlsx, then run:
    streamlit run app.py
"""

from pathlib import Path
import textwrap

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st


#  CONFIGURATION


st.set_page_config(
    page_title="GBD Mortality Explorer",
    layout="wide",
    initial_sidebar_state="expanded",
)

#DATA_DIR = Path(__file__).parent / "data"
GBD_PATH = "pages\\GBD.csv"
LOCATION_PATH = "pages\\locations_with_codes.csv"
COUNTRY_CLS_BY_INCOME_PATH ="pages\\country_classification_by_income.xlsx"
#CAUSE_MAPPING_PATH = DATA_DIR /"cause_mapping.csv"
CAUSE_MAPPING_PATH ="pages\\cause_mapping.csv"
COUNTRY_CLS_BY_INCOME_PATH_SHEET_NAME = "Country Analytical History"

# colour palette
COLOR_MAP = {
    "H": "#1f77b4",
    "UM": "#2ca02c",
    "LM": "#ff7f0e",
    "L": "#9467bd",
    "ALL": "#555555",
}
INCOME_GROUPS = ["H", "UM", "LM", "L"]
INCOME_LABELS = {
    "H": "High Income",
    "UM": "Upper-middle Income",
    "LM": "Lower-middle Income",
    "L": "Low Income",
    "ALL": "Global",
}

# Lists of cause_ids kept for each cause hierarchy level 
LEVEL_CAUSE_IDS = {
    1: [
        295,
        409,
        687,
        1058,
        1029,
        1026,
        1027,
        1028,
        1059,
    ],
    2: [
        955,
        956,
        957,
        344,
        961,
        962,
        386,
        410,
        491,
        508,
        526,
        542,
        558,
        973,
        974,
        653,
        669,
        626,
        640,
        688,
        696,
        717,
    ],
    3: [
        298, 393, 297, 322, 328, 329, 1048, 302, 958, 959,
        321, 345, 356, 357, 358, 359, 360, 364, 405, 843,
        935, 936, 346, 365, 347, 350, 351, 352, 353, 354,
        355, 332, 337, 338, 339, 340, 341, 342, 400, 408,
        366, 380, 387, 388, 389, 390, 391, 444, 423, 426,
        459, 462, 1011, 1012, 429, 432, 435, 465, 447, 438,
        468, 471, 474, 477, 1008, 1013, 480, 483, 484, 450,
        485, 486, 487, 489, 490, 411, 414, 441, 417, 453,
        456, 981, 674, 679, 627, 628, 630, 631, 632, 639,
        641, 594, 603, 613, 619, 680, 686, 492, 502, 503,
        507, 493, 494, 498, 504, 499, 1004, 500, 501, 509,
        510, 515, 516, 520, 521, 541, 992, 529, 530, 531,
        532, 533, 534, 535, 543, 544, 545, 546, 554, 972,
        557, 559, 585, 567, 570, 571, 572, 575, 578, 579,
        582, 560, 561, 587, 589, 588, 654, 664, 665, 668,
        655, 980, 658, 659, 660, 661, 662, 663, 689, 695,
        697, 842, 729, 1056, 698, 699, 700, 704, 708, 709,
        712, 718, 724, 945, 854,
    ],
}


# DATA PREPARATION


def _load_raw_gbd() -> pd.DataFrame:
    """Read and lightly filter the raw GBD CSV."""
    gbd_dtypes = {
        "location_id": "int16",
        "sex_id": "int8",
        "cause_id": "int16",
        "metric_id": "int8",
        "year": "int16",
        "val": "float32",
        "metric_name": "category",
    }
    use_cols = [
        "location_id",
        "sex_id",
        "cause_id",
        "metric_id",
        "year",
        "val",
        "metric_name",
    ]
    
    df = pd.read_csv(GBD_PATH, usecols=use_cols, dtype=gbd_dtypes)
    # keep only mortality rates (metric_id = 3) for both sexes (sex_id = 3)
    exclude_ids = [149, 320, 374, 413]
    df = (
        df[(df.metric_id == 3) & (df.sex_id == 3) & (df.year >= 1987)]
        .loc[~df.location_id.isin(exclude_ids)]
        .rename(columns={"val": "rate"})[["location_id", "cause_id", "year", "rate"]]
    )
    return df


def _load_income_lookup() -> pd.DataFrame:
    """Return a tidy mapping (location_id, year) → income_group."""
    df_loc = pd.read_csv(
        LOCATION_PATH,
        usecols=["location_id", "country_code"],
        dtype={"location_id": "int16", "country_code": "string"},
    ).rename(columns={"country_code": "iso3"})

    df_wide = (
        pd.read_excel(
            COUNTRY_CLS_BY_INCOME_PATH,
            sheet_name=COUNTRY_CLS_BY_INCOME_PATH_SHEET_NAME,
            header=5,
            dtype=str,
        )
        .drop(index=range(0, 5))
        .reset_index(drop=True)
    )
    df_wide = df_wide.rename(columns={df_wide.columns[0]: "iso3", df_wide.columns[1]: "country_name"})

    year_cols = [c for c in df_wide.columns if (isinstance(c, int) or (isinstance(c, str) and c.isdigit()))]
    df_income = (
        df_wide.melt(id_vars=["iso3", "country_name"], value_vars=year_cols, var_name="year", value_name="income_group")
        .assign(year=lambda d: d["year"].astype(int))
        .loc[lambda d: d.year <= 2021]
    )

    df = (
        df_loc.merge(df_income, on="iso3", how="inner")
        .assign(income_group=lambda d: d["income_group"].replace(["..", " "], "MISSING"))
        [["location_id", "year", "income_group"]]
    )
    return df


@st.cache_data(show_spinner="Loading & preprocessing data …", ttl=24 * 3600)
def load_prepared_frames():
    """Return trio: df_grouped_by_year_income_cause, df_causes, df_global."""
    gbd_df = _load_raw_gbd()
    income_lookup = _load_income_lookup()

    df = gbd_df.merge(income_lookup, on=["location_id", "year"], how="left")

    # Average rate by (year, income_group, cause)
    grouped = (
        df.groupby(["year", "income_group", "cause_id"], as_index=False)["rate"].mean().rename(columns={"rate": "avg_rate"})
    )

    # Cause names
    df_causes = pd.read_csv(CAUSE_MAPPING_PATH, usecols=["cause_id", "cause_name"], dtype={"cause_id": "int16", "cause_name": "string"})

    # Global (all countries) mean
    df_global = (
        df.groupby(["year", "cause_id"], as_index=False)["rate"].mean()
        .rename(columns={"rate": "avg_rate"})
        .merge(df_causes, on="cause_id", how="inner")
    )
    return grouped, df_causes, df_global



# HELPER FUNCTIONS


def prep_level_datasets(level: int, grouped: pd.DataFrame, causes: pd.DataFrame, df_global: pd.DataFrame):
    """Given the overall grouped frame, slice out the level‐specific datasets."""
    keep_ids = LEVEL_CAUSE_IDS[level]
    df_level = grouped[grouped.cause_id.isin(keep_ids)].copy()
    df_global_level = df_global[df_global.cause_id.isin(keep_ids)].copy()

    # Top‑10 by income_group+year
    top10 = (
        df_level.sort_values(["year", "income_group", "avg_rate"], ascending=[True, True, False])
        .groupby(["year", "income_group"], as_index=False)
        .head(10)
        .merge(causes, on="cause_id", how="inner")
    )[["year", "income_group", "cause_id", "cause_name", "avg_rate"]]

    return df_level, df_global_level, top10


def plot_top10_for_year(year: int, top10: pd.DataFrame, df_global_level: pd.DataFrame):
    """5‑panel (4 income + global) bar chart for a single year."""
    # Determine a nice shared x‑axis max for all panels
    x_max = max(top10["avg_rate"].max(), df_global_level["avg_rate"].max()) * 1.1

    fig = make_subplots(
        rows=3,
        cols=2,
        specs=[[{}, {}], [{}, {}], [{"colspan": 2}, None]],
        subplot_titles=[*(INCOME_LABELS[i] for i in INCOME_GROUPS), "Global"],
        vertical_spacing=0.18,
        horizontal_spacing=0.12,
    )

    # Income panels
    for i, inc in enumerate(INCOME_GROUPS):
        df_sel = top10.loc[(top10.year == year) & (top10.income_group == inc)].nlargest(10, "avg_rate")
        r, c = divmod(i, 2)
        fig.add_trace(
            go.Bar(
                x=df_sel["avg_rate"],
                y=df_sel["cause_name"],
                orientation="h",
                marker_color=COLOR_MAP[inc],
                hovertemplate="<b>%{y}</b><br>Rate: %{x:.1f}<extra></extra>",
                showlegend=False,
            ),
            row=r + 1,
            col=c + 1,
        )

    # Global panel
    df_glob = df_global_level.loc[df_global_level.year == year].nlargest(10, "avg_rate")
    fig.add_trace(
        go.Bar(
            x=df_glob["avg_rate"],
            y=df_glob["cause_name"],
            orientation="h",
            marker_color=COLOR_MAP["ALL"],
            hovertemplate="<b>%{y}</b><br>Rate: %{x:.1f}<extra></extra>",
            showlegend=False,
        ),
        row=3,
        col=1,
    )

    # Shared formatting
    for idx in range(5):
        r, c = (divmod(idx, 2) if idx < 4 else (2, 0))
        fig.update_xaxes(title_text="Mortality Rate (Per 100,000)", range=[0, x_max], row=r + 1, col=c + 1, ticks="outside", tickfont=dict(size=11))
        fig.update_yaxes(autorange="reversed", row=r + 1, col=c + 1, tickfont=dict(size=11))

    fig.update_layout(
        template="plotly_white",
        # title_text=f"Top 10 Causes of Death by Income Group — {year}",
        # title_x=0.5,
        title=dict(                     # <-- use the full title object
            text=f"Top 10 Causes of Death by Income Group — {year}",
            x=0.4,                      # 50 % of the plotting *paper*
            xanchor='center',           # anchor the *centre* of the text at x
            xref='paper'                # position relative to the figure’s paper, not data
        ),
        height=1050,
        margin=dict(l=80, r=80, t=140, b=60),
    )
    return fig


def plot_animated_top10(top10: pd.DataFrame, df_global_level: pd.DataFrame, income_label: str):
    """Animated horizontally‑stacked bars over years for a single income group (or Global)."""
    if income_label == "Global":
        # Build global top‑10 per year from df_global_level
        df = (
            df_global_level.sort_values(["year", "avg_rate"], ascending=[True, False])
            .groupby("year", as_index=False)
            .head(10)
        )
        df["Income Label"] = "Global"
    else:
        df = top10.copy()
        df["Income Label"] = df["income_group"].map(INCOME_LABELS)
        df = df[df["Income Label"] == income_label]

    fig = px.bar(
        df,
        x="avg_rate",
        y="cause_name",
        orientation="h",
        animation_frame="year",
        animation_group="cause_name",
        color_discrete_sequence=[COLOR_MAP.get({v: k for k, v in INCOME_LABELS.items()}[income_label], "#1f77b4")],
        range_x=[0, df["avg_rate"].max() * 1.05],
        title=f"Top 10 Causes of Death Over Time — {income_label}",
        labels={"avg_rate": "Mortality Rate (Per 100,000)", "cause_name": "Cause of Death", "year": "Year"},
    )

    # slow animation
    fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 700
    fig.layout.sliders[0].transition = {"duration": 700, "easing": "linear"}

    fig.update_yaxes(autorange="reversed", tickfont=dict(size=11), automargin=False, fixedrange=True)
    fig.update_xaxes(fixedrange=True)
    fig.update_layout(template="plotly_white",
                    # title_x=0.5,    
                    title=dict(
                        text=f"Top 10 Causes of Death Over Time — {income_label}",
                        x=0.3,         
                        xanchor="center",
                        xref="paper"
                    ),                 
                    height=500, showlegend=False, margin=dict(l=290, r=40, t=80, b=40))
    return fig


def plot_disease_trend(df_line_all: pd.DataFrame, disease: str):
    """Multi‑panel line chart of a single disease over time across income groups + Global."""
    panels = [INCOME_LABELS[i] for i in INCOME_GROUPS] + ["Global"]
    fig = make_subplots(
        rows=3,
        cols=2,
        specs=[[{}, {}], [{}, {}], [{"colspan": 2}, None]],
        subplot_titles=panels,
        vertical_spacing=0.12,
        horizontal_spacing=0.08,
    )

    for idx, label in enumerate(panels):
        dfp = df_line_all[(df_line_all["cause_name"] == disease) & (df_line_all["Income_Label"] == label)]
        r, c = (divmod(idx, 2) if label != "Global" else (2, 0))
        fig.add_trace(
            go.Scatter(x=dfp["year"], y=dfp["avg_rate"], mode="lines+markers", name=label),
            row=r + 1,
            col=c + 1,
        )
        fig.update_xaxes(title_text="Year", row=r + 1, col=c + 1, fixedrange=True)
        fig.update_yaxes(title_text="Mortality Rate (Per 100,000)", row=r + 1, col=c + 1, fixedrange=True, tickfont=dict(size=11))

    fig.update_layout(template="plotly_white",
                    #    title=f"{disease} — Mortality Rate Over Time", title_x=0.5,
                        title=dict(
                            text=f"{disease} — Mortality Rate Over Time",
                            x=0.5,          # centred in figure ‘paper’ coordinates
                            xanchor="center",
                            xref="paper"
                    ),
                      
                       height=1000, showlegend=False, margin=dict(l=60, r=40, t=80, b=40))
    return fig


def build_line_dataset(df_level: pd.DataFrame, df_causes: pd.DataFrame, df_global_level: pd.DataFrame):
    """Tidy DataFrame with avg_rate lines for all income groups + Global for each cause."""
    df_line = df_level.merge(df_causes, on="cause_id", how="inner")[["year", "income_group", "cause_name", "avg_rate"]]
    df_line["Income_Label"] = df_line["income_group"].map(INCOME_LABELS)

    df_global_line = df_global_level.assign(Income_Label="Global")[["year", "Income_Label", "cause_name", "avg_rate"]]
    df_all = pd.concat([df_line, df_global_line], ignore_index=True)
    return df_all

###############################################################################
# ---------------------------------- UI ------------------------------------- #
###############################################################################

grouped, df_causes, df_global = load_prepared_frames()

LEVEL_LABELS = {
    1: "High-Level",
    2: "Mid-Level",
    3: "Low-Level",
}


st.sidebar.title("Controls")
level = st.sidebar.selectbox("Cause hierarchy level",
                              options=[1, 2, 3], format_func=lambda x: f"Level {x}: {LEVEL_LABELS[x]}")
view = st.sidebar.radio(
    "Visualisation",
    options=["Bar Graph: Compare Top-10 (per Y)",
              "Bar Race: Top‑10 over Time (per IG)",
            "Line Chart: Mortality Trends (per D)"],
)

# Prepare level‑specific datasets just once per selection (cached)
@st.cache_data(show_spinner=False)
def _prep(level_: int):
    return prep_level_datasets(level_, grouped, df_causes, df_global)

df_level, df_global_level, top10 = _prep(level)

st.title("GBD Mortality Explorer")
level_blurb = {
    1: "Level-1 (High Level)",
    2: "Level-2 (Mid Level)",
    3: "Level-3 (Low Level)",
}

st.markdown(f"### Explore {level_blurb[level]}")

if view == "Bar Graph: Compare Top-10 (per Y)":
    # build a dropdown of available years
    years = sorted(top10.year.unique())
    sel_year = st.sidebar.selectbox(
        "Year",
        options=years,
        index=0,              # default to the first (earliest) year
    )

    # call plot_top10_for_year(year, top10, df_global_level)
    fig = plot_top10_for_year(sel_year, top10, df_global_level)
    st.plotly_chart(fig, use_container_width=True)




elif view == "Bar Race: Top‑10 over Time (per IG)":
    income_label = st.sidebar.selectbox("Income group", options=["Global"] + [INCOME_LABELS[i] for i in INCOME_GROUPS])
    fig = plot_animated_top10(top10, df_global_level, income_label)
    st.plotly_chart(fig, use_container_width=True)
    st.info("Use the ▶️ button in the lower‑left of the chart to play the animation.")

else:  # Trend by disease
    df_line_all = build_line_dataset(df_level, df_causes, df_global_level)
    diseases = sorted(df_line_all.cause_name.unique())
    sel_dis = st.sidebar.selectbox("Disease", options=diseases, index=0)
    fig = plot_disease_trend(df_line_all, sel_dis)
    st.plotly_chart(fig, use_container_width=True)
