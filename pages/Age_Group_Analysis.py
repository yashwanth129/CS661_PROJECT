import plotly.express as px
from plotly.subplots import make_subplots
from plotly.colors import qualitative
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
st.set_page_config(page_title="Death-Rate Trends Across Age-Groups Dashboard", layout="wide", initial_sidebar_state="expanded")

# Inject custom CSS styling
# Inject custom CSS styling
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
    }
    .stTitle h1 {
        margin-top: 0rem;
        margin-bottom: 0.5rem;
    }
    
    </style>
    """,
    unsafe_allow_html=True
)

def generate_line_charts(df_pivot, current_year):
    age_groups = df_pivot.columns.tolist()
    rows = (len(age_groups) + 2) // 3
    fig = make_subplots(rows=rows, cols=3, subplot_titles=age_groups)

    for idx, age in enumerate(age_groups):
        r, c = divmod(idx, 3)
        r += 1
        c += 1
        y_vals = df_pivot[age]
        mean_val = y_vals.mean()
        fig.add_trace(go.Scatter(x=df_pivot.index, y=y_vals, mode='lines+markers', name=f'{age}', line=dict(color='blue')), row=r, col=c)
        fig.add_trace(go.Scatter(x=df_pivot.index, y=[mean_val]*len(df_pivot), mode='lines', name=f'{age} Avg', line=dict(color='red', dash='dash')), row=r, col=c)
        fig.add_vline(x=current_year, line_dash="dot", line_color="orange", row=r, col=c)

    fig.update_layout(height=300*rows, title="Death Rate Trends with Average per Age Group", plot_bgcolor='#f4f6f9')
    return fig


# Cache the data loading function
@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if 'All causes' in df['cause'].unique():
        df = df[df['cause'] != 'All causes']
    df['year'] = pd.to_numeric(df['year'], errors='coerce').astype(int)
    for col in ['val']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

# Load mappings from codebook
def load_mappings(codebook_path: str) -> dict:
    codebook = pd.read_csv(codebook_path, header=0, skiprows=[1])
    codebook.columns = codebook.columns.str.replace(r"^Variable:\s*", "", regex=True).str.strip()
    return {
        "measure": dict(codebook[["measure_id", "measure_name"]].drop_duplicates().values),
        "location": dict(codebook[["location_id", "location_name"]].drop_duplicates().values),
        "sex": dict(codebook[["sex_id", "sex_label"]].drop_duplicates().values),
        "age": dict(codebook[["age_group_id", "age_group_name"]].drop_duplicates().values),
        "cause": dict(codebook[["cause_id", "cause_name"]].drop_duplicates().values)
    }

# Sidebar filter controls
def get_sidebar_filters(df: pd.DataFrame):
    st.sidebar.header("Filter data")
    all_countries = sorted(df['location'].unique())
    mode = st.sidebar.radio("Location mode", ["Global", "By Country"], index=0)
    if mode == "By Country":
        default_countries = ["India"] if "India" in all_countries else [all_countries[0]]
        locs = st.sidebar.multiselect("Select Countries for Dashboard", options=all_countries, default=default_countries)
        if not locs:
            locs = ["Global"]
        comp_countries = st.sidebar.multiselect("Compare Countries (max 2)", options=all_countries, default=default_countries, help="Select up to two countries for comparison")
        if len(comp_countries) > 2:
            st.sidebar.warning("Select at most 2 countries.")
            comp_countries = comp_countries[:2]
    else:
        locs = ["Global"]
        comp_countries = []
    cause_totals = df.groupby('cause', as_index=False)['val'].sum()
    top_causes = cause_totals.nlargest(10, 'val')['cause'].tolist()
    causes = st.sidebar.multiselect("Cause", options=sorted(df['cause'].unique()), default=top_causes)
    sexes = st.sidebar.multiselect("Sex", options=sorted(df['sex'].unique()), default=sorted(df['sex'].unique()))
    year_min, year_max = int(df['year'].min()), int(df['year'].max())
    year_range = st.sidebar.slider("Year range", year_min, year_max, (year_min, year_max), step=1)
    return tuple(locs), tuple(causes), tuple(sexes), year_range, tuple(comp_countries)

# Cache filtered data
@st.cache_data(show_spinner=False)
def filter_data(locations: tuple, causes: tuple, sexes: tuple, year_range: tuple, df_ref: pd.DataFrame) -> pd.DataFrame:
    df = df_ref.copy()
    if 'Global' not in locations:
        df = df[df['location'].isin(locations)]
    df = df[df['cause'].isin(causes) & df['sex'].isin(sexes) & df['year'].between(year_range[0], year_range[1])]
    return df

# Bar chart function
def bar_chart_age(df: pd.DataFrame):
    agg = df.groupby(['age', 'cause'], as_index=False)['val'].sum()
    fig = px.bar(agg, x='age', y='val', color='cause', labels={'age':'Age group','val':'Death Rate Proportion of causes','cause':'Cause'}, title='Stacked Bar Chart by Age Group and Cause', hover_data={'val':':.4f'})
    fig.update_layout(barmode='stack', xaxis={'categoryorder':'total descending'})
    return fig

# Line chart function
def line_chart_trend(df: pd.DataFrame):
    df_t = df.groupby(['year', 'age'], as_index=False)['val'].mean()
    fig = px.line(df_t, x='year', y='val', color='age', labels={'year':'Year','val':'Avg value','age':'Age group'}, title='Trend of Avg Value by Age Group')
    return fig

# Apply mappings to dataset
def apply_mapping(df: pd.DataFrame, mappings: dict, columns: list) -> pd.DataFrame:
    df_copy = df.copy()
    for col in columns:
        df_copy[col] = df_copy[col].map(mappings[col])
    return df_copy

@st.cache_data(show_spinner=False)
def filter_data_for_animation(df: pd.DataFrame, location: str, sex: str, cause: str):
    df_filtered = df[
        (df['location'] == location) &
        (df['sex'] == sex) &
        (df['cause'] == cause)
    ]
    return df_filtered

def prepare_data_for_race(df: pd.DataFrame, selected_location: str) -> pd.DataFrame:
    df_filtered = df[(df['location'] == selected_location) & (df['cause'] == 'All causes')]
    df_filtered = df_filtered[['year', 'age', 'val']]
    df_filtered = df_filtered.groupby(['year', 'age'], as_index=False)['val'].sum()
    df_pivot = df_filtered.pivot(index='year', columns='age', values='val')
    df_pivot = df_pivot.fillna(0)
    return df_pivot


def generate_race_plot(df_pivot):
    years = df_pivot.index.tolist()
    top_n = 10

    # Define color palette
    color_list = qualitative.Plotly * 3  # Expand color list if needed

    fig = go.Figure()

    initial_year = years[0]
    initial_data = df_pivot.loc[initial_year].sort_values(ascending=False).head(top_n)

    fig.add_trace(go.Bar(
        x=initial_data.values,
        y=initial_data.index,
        orientation='h',
        text=initial_data.index,
        textposition='outside',
        textfont=dict(color='black'),
        marker_color=color_list[:len(initial_data)]
    ))

    frames = []
    for year in years:
        data_year = df_pivot.loc[year].sort_values(ascending=False).head(top_n)
        frames.append(go.Frame(
            data=[go.Bar(
                x=data_year.values,
                y=data_year.index,
                orientation='h',
                text=data_year.index,
                textposition='outside',
                textfont=dict(color='black'),
                marker_color=color_list[:len(data_year)]
            )],
            name=str(year)
        ))

    fig.frames = frames

    fig.update_layout(
        updatemenus=[{
            'buttons': [
                {
                    'args': [None, {'frame': {'duration': 300, 'redraw': True}, 'fromcurrent': True}],
                    'label': 'Play',
                    'method': 'animate'
                },
                {
                    'args': [[None], {'frame': {'duration': 0, 'redraw': False}, 'mode': 'immediate'}],
                    'label': 'Pause',
                    'method': 'animate'
                }
            ],
            'direction': 'left',
            'pad': {'r': 10, 't': 87},
            'showactive': True,
            'type': 'buttons',
            'x': 0.1,
            'y': 0
        }],
        sliders=[{
            'active': 0,
            'yanchor': 'top',
            'xanchor': 'left',
            'currentvalue': {'font': {'size': 20}, 'prefix': 'Year:', 'visible': True, 'xanchor': 'right'},
            'transition': {'duration': 300, 'easing': 'cubic-in-out'},
            'pad': {'b': 10, 't': 50},
            'len': 0.9,
            'x': 0.1,
            'y': 0,
            'steps': [{'args': [[str(year)], {'frame': {'duration': 300, 'redraw': True}, 'mode': 'immediate'}], 'label': str(year), 'method': 'animate'} for year in years]
        }]
    )

    fig.update_layout(
        title='Death Rate by Age Group Over Years',
        xaxis_title='Death Rate',
        yaxis_title='Age Group',
        yaxis=dict(autorange="reversed", automargin=True),
        xaxis=dict(automargin=True, range=[0, df_pivot.max().max() * 1.1]),
        plot_bgcolor='white'
    )

    return fig

def create_dumbbell_plot(df, country_a, country_b):
    df = df[df['cause'] == 'All causes']
    latest_year = df['year'].max()
    df = df[df['year'] == latest_year]
    df = df[df['location'].isin([country_a, country_b])]

    grouped = df.groupby(['location', 'age'])['val'].sum().reset_index()
    pivoted = grouped.pivot(index='age', columns='location', values='val').dropna()
    pivoted['gap'] = (pivoted[country_a] - pivoted[country_b]).abs()
    pivoted = pivoted.sort_values('gap', ascending=False)

    # Assign color to each value based on which country it belongs to
    value_colors = {}
    for age_group in pivoted.index:
        val_a = pivoted.loc[age_group, country_a]
        val_b = pivoted.loc[age_group, country_b]
        value_colors[val_a] = '#1f77b4'  # color for country_a
        value_colors[val_b] = '#ff7f0e'  # color for country_b

    fig = go.Figure()
    connector_color = '#4B0082'

    for age_group in pivoted.index:
        val_a = pivoted.loc[age_group, country_a]
        val_b = pivoted.loc[age_group, country_b]
        gap = pivoted.loc[age_group, 'gap']
        # Determine left and right based on value
        if val_a <= val_b:
            left_val, right_val = val_a, val_b
        else:
            left_val, right_val = val_b, val_a

        y = age_group

        # Draw connector line between both points
        fig.add_trace(go.Scatter(
            x=[left_val, right_val],
            y=[y, y],
            mode='lines+text',
            line=dict(color=connector_color, width=5),
            text=[None, f"                         {gap:,.0f}"],
            textposition='top center',
            textfont=dict(color='black', size=12),
            showlegend=False
        ))

        # Plot left point
        fig.add_trace(go.Scatter(
            x=[left_val],
            y=[y],
            mode='markers',
            marker=dict(color=value_colors[left_val], size=14, line=dict(width=2, color='black')),
            name=country_a if val_a == left_val else country_b,
            showlegend=(age_group == pivoted.index[0] and (country_a if val_a == left_val else country_b) not in [t.name for t in fig.data])
        ))

        # Plot right point
        fig.add_trace(go.Scatter(
            x=[right_val],
            y=[y],
            mode='markers',
            marker=dict(color=value_colors[right_val], size=14, line=dict(width=2, color='black')),
            name=country_a if val_a == right_val else country_b,
            showlegend=(age_group == pivoted.index[0] and (country_a if val_a == right_val else country_b) not in [t.name for t in fig.data])
        ))

    fig.update_layout(
        title=f"Dumbbell Plot of Death Rate by Age Group ({latest_year}): {country_a} vs {country_b}",
        xaxis_title="Death Rate",
        yaxis_title="Age Group",
        height=800,
        plot_bgcolor='#616178',
        paper_bgcolor='#616178',
        legend=dict(title='', itemsizing='trace', traceorder='normal')
    )
    return fig

@st.cache_data(show_spinner=False)
def filter_age_bracket_data(df, locations, sexes, causes):
    return df[(df['location'].isin(locations)) & (df['sex'].isin(sexes)) & (df['cause'].isin(causes))]

def main():
    st.title("\U0001F9EC Death Rate Trends Across Age-Groups Dashboard")
    mappings = load_mappings("pages\\IHME_GBD_2021_CODEBOOK_Y2024M05D16.CSV")
    df = load_data("pages\\age_moratility_data_95percentile.csv")
    df = apply_mapping(df, mappings, ['location', 'sex', 'age', 'cause'])
    locs, causes, sexes, year_range, comp_countries = get_sidebar_filters(df)
    df_f = filter_data(locs, causes, sexes, year_range, df)
    st.markdown(f"**Filtered records:** {len(df_f)}")
    if df_f.empty:
        st.warning("No data for selected filters.")
        return
    tabs = st.tabs(["Overview", "Age-Group mortality Comparison between two countries", "Ranking of Age Brackets for a cause", "Animated Mortality Trends by Age Group"])

    with tabs[0]:
        st.plotly_chart(bar_chart_age(df_f), use_container_width=True)

    with tabs[1]:
        st.subheader("Age-Bracket Trends Analysis")

        # New input selectors inside the tab
        countries = st.multiselect("Select two countries to compare:", options=sorted(df['location'].unique()))
        selected_causes = st.multiselect("Select Causes:", options=sorted(df['cause'].unique()),
                                         default=['All causes'] if 'All causes' in df['cause'].unique() else [])
        selected_sexes = st.multiselect("Select Sexes:", options=sorted(df['sex'].unique()),
                                        default=sorted(df['sex'].unique()))
        year_min, year_max = int(df['year'].min()), int(df['year'].max())
        year_range_tab = st.slider("Select Year Range:", year_min, year_max, (year_min, year_max), step=1)

        if len(countries) == 2:
            a, b = countries
            dumbbell_fig = create_dumbbell_plot(df, a, b)
            st.plotly_chart(dumbbell_fig, use_container_width=True)
            df_comp = df[
                (df['location'].isin(countries)) &
                (df['cause'].isin(selected_causes)) &
                (df['sex'].isin(selected_sexes)) &
                (df['year'].between(year_range_tab[0], year_range_tab[1]))
                ]

            if df_comp.empty:
                st.warning("No data available for the selected filters.")
            else:
                # Bar Chart: Difference between countries across Age
                df_age = (df_comp.groupby(['age', 'location'], as_index=False)['val']
                          .sum()
                          .pivot(index='age', columns='location', values='val')
                          .fillna(0))
                df_age['diff'] = df_age[a] - df_age[b]
                df_age = df_age.reset_index()
                fig1 = px.bar(df_age, x='diff', y='age', orientation='h', color='diff',
                              color_continuous_scale='RdBu',
                              title=f"Difference in Sum of Values: {a} minus {b}")
                max_age = df_age.iloc[df_age['diff'].abs().idxmax()]['age']
                fig1.add_annotation(x=df_age['diff'].max(), y=max_age,
                                    text=f"Max diff: {df_age['diff'].max():.2f}", showarrow=True)
                st.plotly_chart(fig1, use_container_width=True)

                # Line Chart: Trend by Age Bracket
                fig2 = px.line(df_comp, x='year', y='val', color='location',
                               facet_col='age', facet_col_wrap=4,
                               labels={'val': 'Avg value', 'year': 'Year'},
                               title='Trend by Age Bracket')
                fig2.update_layout(height=800)
                st.plotly_chart(fig2, use_container_width=True)


        else:
            st.info("Please select exactly two countries to compare.")

    with tabs[2]:
        st.subheader("Cause Insights: Bump Chart & Streamgraph")
        selected_cause = st.selectbox("Choose a cause to inspect:", options=sorted(df['cause'].unique()))
        df_ci = df[(df['location'].isin(locs) if 'Global' not in locs else df['location'].notna()) & (df['sex'].isin(sexes)) & (df['year'].between(year_range[0], year_range[1])) & (df['cause'] == selected_cause)]
        ranked = df_ci.groupby(['year', 'age'], as_index=False)['val'].sum()
        ranked['rank'] = ranked.groupby('year')['val'].rank(method='first', ascending=False)
        df_stream = df_ci.groupby(['year', 'age'], as_index=False)['val'].sum().sort_values(by=['year', 'age'])
        pivot_df = df_stream.pivot(index='year', columns='age', values='val').fillna(0)
        age_totals = pivot_df.sum(axis=0).sort_values(ascending=False)
        pivot_df = pivot_df[age_totals.index]
        pivot_df = pivot_df.div(pivot_df.sum(axis=1), axis=0)
        age_list = list(pivot_df.columns)
        dark_palette = qualitative.Dark24
        color_map = {age: dark_palette[i % len(dark_palette)] for i, age in enumerate(age_list)}
        selected_ages = st.multiselect("Highlight age group(s):", options=age_list, default=age_list, key="highlight_ages")
        fig_bump = go.Figure()
        for age in reversed(age_list):
            df_age = ranked[ranked['age'] == age]
            fig_bump.add_trace(go.Scatter(x=df_age['year'], y=df_age['rank'], mode='lines+markers+text', line=dict(shape='spline', color=color_map[age]), marker=dict(symbol='square', size=20, color=color_map[age]), text=df_age['rank'].astype(int).astype(str), textposition='middle center', textfont=dict(color='white', size=15), name=age, opacity=1.0 if age in selected_ages else 0.15, hovertemplate=f'<span style="font-size:18px"><b>Year</b>: %{{x}}<br><b>Rank</b>: %{{y}}<br><b>Age Group</b>: {age}</span>'))
        fig_bump.update_layout(title=f"Bump Chart: Ranking of Age Brackets over Time for {selected_cause}", xaxis_title='Year', yaxis_title='Rank', yaxis=dict(autorange='reversed', dtick=1), legend_title='Age group')
        st.plotly_chart(fig_bump, use_container_width=True)
        fig_stream = go.Figure()
        for age in reversed(age_list):
            fig_stream.add_trace(go.Scatter(textposition='middle center', x=pivot_df.index, y=pivot_df[age], mode='lines+text', stackgroup='one', name=age, line=dict(color=color_map[age]), hovertemplate=f'<span style="font-size:18px"><b>Year</b>: %{{x}}<br><b>Proportion</b>: %{{y:.2%}}<br><b>Age Group</b>: {age}</span>'))
        fig_stream.update_layout(title=f"Streamgraph: Death Rate Proportions over Time for {selected_cause}", xaxis_title='Year', yaxis_title='Proportion', showlegend=True, height=400)
        st.plotly_chart(fig_stream, use_container_width=True)

    with tabs[3]:
        st.subheader("\U0001F4CA Mortality Race Animation")
        selected_location = st.selectbox("Select Location", options=sorted(df['location'].unique()), index=0)
        race_df = prepare_data_for_race(df, selected_location)
        fig = generate_race_plot(race_df)
        st.plotly_chart(fig, use_container_width=True)


if __name__ == '__main__':
    main()
