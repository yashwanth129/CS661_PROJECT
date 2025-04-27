import streamlit as st
import pandas as pd
import plotly.graph_objects as go


st.set_page_config(page_title="Mortality Dashboard", layout="wide")
st.title(" Global Mortality Data Dashboard")

# Loading data 
@st.cache_data
def load_data():
    return pd.read_csv("pages\\data_2.csv")  

df_csv = load_data()
df_csv["sex"] = df_csv["sex"].str.lower()  

df_parquet = pd.read_parquet('pages\\aggregated_by_year_location.parquet')

# tabs setup
tab1, tab2 = st.tabs(["Top 10 countries Male vs Female", "Global Mortality Trends"])

# tab1 : top 10
with tab1:
    st.header("Top 10 countries Male vs Female")

    col1, col2 = st.columns(2)
    with col1:
        selected_year = st.selectbox("Select Year", sorted(df_csv['year'].dropna().unique()))
    with col2:
        selected_cause = st.selectbox("Select Cause", sorted(df_csv['cause_name'].dropna().unique()))

    filtered_df = df_csv[(df_csv['year'] == selected_year) & (df_csv['cause_name'] == selected_cause)]

    both_df = filtered_df[filtered_df['sex'] == "both"]
    top10_countries = both_df.sort_values("death_rate", ascending=False).head(10)["location_name"].tolist()

    sex_df = filtered_df[(
        filtered_df["sex"].isin(["male", "female","both"])) & 
        (filtered_df["location_name"].isin(top10_countries))
    ]

    pivot_df = sex_df.pivot_table(
        index='location_name',
        columns='sex',
        values='death_rate',
        aggfunc='sum'
    ).reindex(index=top10_countries).fillna(0)

    pivot_df = pivot_df.sort_values(by="both", ascending=True)
    if 'male' not in pivot_df.columns:
        pivot_df['male'] = 0
    if 'female' not in pivot_df.columns:
        pivot_df['female'] = 0

    fig = go.Figure()

    fig.add_trace(go.Bar(
        y=pivot_df.index,
        x=-pivot_df["male"],
        name='Male',
        orientation='h',
        marker_color='steelblue'
    ))

    fig.add_trace(go.Bar(
        y=pivot_df.index,
        x=pivot_df["female"],
        name='Female',
        orientation='h',
        marker_color='lightcoral'
    ))

    fig.update_layout(
        title=f"Top 10 Countries by Death Rate (Both Sexes) - {selected_cause} ({selected_year})",
        barmode='relative',
        xaxis=dict(
            title='Death Rate per 1 Lakh',
            tickvals=[-300, -150, 0, 150, 300],
            ticktext=[300, 150, 0, 150, 300]
        ),
        yaxis=dict(title='Country'),
        height=600,
        margin=dict(l=100, r=20, t=60, b=40)
    )

    st.plotly_chart(fig, use_container_width=True)

# Tab :Global Mortality Trends
with tab2:
    st.header("Global Mortality Trends")

    st.markdown("Compare death rates by country, gender, and disease over the years.")

    countries = st.multiselect(
        "Select Countries:",
        options=sorted(df_parquet['location_name'].unique()),
        default=['Poland', 'Germany']
    )
    sex = st.selectbox(
        "Select Gender:",
        options=['both', 'male', 'female'],
        index=0
    )
    cause = st.selectbox(
        "Select Cause:",
        options=sorted(df_parquet['cause_name'].unique()),
        index=0
    )

    if countries and cause:
        filtered = df_parquet[(
            df_parquet['location_name'].isin(countries)) & 
            (df_parquet['cause_name'] == cause) & 
            (df_parquet['sex'] == sex)
        ]
        aggregated = filtered.groupby(['year', 'location_name', 'sex'], as_index=False)['val'].sum()
        fig2 = go.Figure()
        for country in countries:
            country_df = aggregated[aggregated['location_name'] == country]
            fig2.add_trace(go.Scatter(
                x=country_df['year'],
                y=country_df['val'],
                mode='lines+markers',
                name=country,
                line=dict(width=3),
                marker=dict(size=6),
                hovertemplate=f"<b>{country}</b><br>Year: %{{x}}<br>Rate: %{{y:.2f}}<extra></extra>"
            ))
        fig2.update_layout(
            title=f"<b>{cause}</b> - Gender: <b>{sex}</b>",
            title_font_size=24,
            xaxis_title="Year",
            yaxis_title="Deaths per 100,000",
            hovermode="x unified",
            legend_title="Country",
            margin=dict(l=40, r=40, t=60, b=40),
            paper_bgcolor='#fff',
            plot_bgcolor='#fff',
        )

        st.plotly_chart(fig2)
