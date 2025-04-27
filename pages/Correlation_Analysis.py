import pandas as pd
import pycountry
import os

gbd_path = f"pages\\GBD.parquet"
location_mapping = f"pages\\location_mapping.parquet"
cause_mapping = f"pages\\cause_mapping.parquet"
# gdp_path = f"{dataset_path}GDP.parquet"
gdp_path = f"pages\\gdp_processed.parquet"
pop_path = f"pages\\world_population.parquet"
health_exp_path = f"pages\\health_exp.parquet"
life_expectancy = f"pages\\life_expectancy.parquet"



## Load Main Dataset 
df_main = pd.read_parquet(gbd_path)

df_rate = df_main[df_main["metric_name"] == "Rate"]
df_rate = df_rate.drop(columns=['metric_name'])
df_rate = df_rate.rename(columns={"val": "mortality_rate"})
df_rate = df_rate.groupby(['location_id', 'year'])['mortality_rate'].sum().reset_index()

df_rate = df_rate.pivot(index='location_id', columns='year', values='mortality_rate')
df_rate.columns = df_rate.columns.astype(str)
df_rate.columns.name = None
df_rate.reset_index(inplace=True)

df_loc = pd.read_parquet(location_mapping)
df_rate = pd.merge(df_rate, df_loc, on='location_id', how='left')
cols = ['location_name'] + [col for col in df_rate if col != 'location_name']
df_rate = df_rate[cols]
df_rate.drop(columns=['location_id'], inplace=True)

years_to_drop = [str(year) for year in range(1980, 2000)]

df_rate.drop(columns=[col for col in years_to_drop if col in df_rate.columns], inplace=True)


## Load GDP Dataset
df_gdp = pd.read_parquet(gdp_path)
years_to_drop = [str(year) for year in range(1960, 2000)]
years_to_drop.append("2022")
years_to_drop.append("2023")
years_to_drop.append("2024")
years_to_drop.append("Unnamed: 69")

df_gdp.drop(columns=[col for col in years_to_drop if col in df_gdp.columns], inplace=True)
df_gdp = df_gdp.rename(columns={"Country Name":"location_name" })

df_pop = pd.read_parquet(pop_path)
df_pop.drop(columns=['Country Code', 'Indicator Name', 'Indicator Code'], inplace=True)
df_pop = df_pop.rename(columns={"Country Name": "location_name"})
years_to_drop = [str(year) for year in range(1960, 2000)]
years_to_drop.append("2022")
years_to_drop.append("2023")
years_to_drop.append("2024")
years_to_drop.append("Unnamed: 69")

df_pop.drop(columns=[col for col in years_to_drop if col in df_pop.columns], inplace=True)


## Load Health EXP
df_health_exp = pd.read_parquet(health_exp_path)
df_health_exp.drop(columns=['Country Code', 'Indicator Name', 'Indicator Code'], inplace=True)
df_health_exp = df_health_exp.rename(columns={"Country Name": "location_name"})
years_to_drop = [str(year) for year in range(1960, 2000)]
years_to_drop.append("2022")
years_to_drop.append("2023")
years_to_drop.append("2024")
years_to_drop.append("Unnamed: 69")

df_health_exp.drop(columns=[col for col in years_to_drop if col in df_health_exp.columns], inplace=True)

## Load Life Exp Dataset

df_life_expectancy = pd.read_parquet(life_expectancy)
df_life_expectancy = df_life_expectancy.rename(columns={"Entity": "location_name", "Period life expectancy at birth - Sex: total - Age: 0": "EXP"})
df_life_expectancy.drop(columns=['Code',], inplace=True)
df_life_expectency = df_life_expectancy.groupby(['location_name', 'Year'])['EXP'].sum().reset_index()
df_life_expectancy = df_life_expectancy.pivot(index='location_name', columns='Year', values='EXP')
df_life_expectancy.columns = df_life_expectancy.columns.astype(str)
df_life_expectancy.columns.name = None
df_life_expectancy.reset_index(inplace=True)

years_to_drop = [str(year) for year in range(1543, 2000)]
years_to_drop.append("2022")
years_to_drop.append("2023")
years_to_drop.append("2024")
years_to_drop.append("Unnamed: 69")

df_life_expectancy.drop(columns=[col for col in years_to_drop if col in df_life_expectancy.columns], inplace=True)

## Drop NAN
df_rate.dropna(inplace=True)
df_gdp.dropna(inplace=True)
df_pop.dropna(inplace=True)
df_health_exp.dropna(inplace=True)
df_life_expectancy.dropna(inplace=True)



## Standardize Country Names
def standardize_country(name):
    try:
        return pycountry.countries.lookup(name).name
    except:
        return name

df_rate["location_name"] = df_rate["location_name"].apply(standardize_country)
df_gdp["location_name"] = df_gdp["location_name"].apply(standardize_country)
df_pop["location_name"] = df_pop["location_name"].apply(standardize_country)
df_health_exp["location_name"] = df_health_exp["location_name"].apply(standardize_country)
df_life_expectancy["location_name"] = df_life_expectancy["location_name"].apply(standardize_country)



## Sort Dataset by Countries Names
df_rate = df_rate.sort_values(by='location_name')
df_gdp = df_gdp.sort_values(by='location_name')
df_pop = df_pop.sort_values(by='location_name')
df_health_exp = df_health_exp.sort_values(by='location_name')
df_life_expectency = df_life_expectency.sort_values(by='location_name')


## Remove Duplicates
common_countries = set(df_rate['location_name']) & set(df_gdp['location_name']) & set(df_pop['location_name'])  & set(df_health_exp['location_name'])  & set(df_life_expectancy['location_name'])

df_gdp = df_gdp[df_gdp['location_name'].isin(common_countries)]
df_rate = df_rate[df_rate['location_name'].isin(common_countries)]
df_pop = df_pop[df_pop['location_name'].isin(common_countries)]
df_health_exp = df_health_exp[df_health_exp['location_name'].isin(common_countries)]
df_life_expectancy = df_life_expectancy[df_life_expectancy['location_name'].isin(common_countries)]




## Normalize 
df_rate_normalized = df_rate.copy()
df_gdp_normalized = df_gdp.copy()
df_pop_normalized = df_pop.copy()
df_health_exp_normalized = df_health_exp.copy()
df_life_exp_normalized = df_life_expectancy.copy()




## Creating Dataset
df_rate_long = df_rate_normalized.melt(id_vars='location_name', var_name='Year', value_name='Mortality_Rate')
df_gdp_long = df_gdp_normalized.melt(id_vars='location_name', var_name='Year', value_name='GDP_per_capita')
df_health_exp_long = df_health_exp_normalized.melt(id_vars='location_name', var_name='Year', value_name='Health_Exp_per_capita')
df_life_exp_long = df_life_exp_normalized.melt(id_vars='location_name', var_name='Year', value_name='Life_Exp')
df_pop_long = df_pop_normalized.melt(id_vars='location_name', var_name='Year', value_name='Population')

df_merged = df_rate_long.merge(df_gdp_long, on=['location_name', 'Year']).merge(df_health_exp_long, on=['location_name', 'Year']) \
                        .merge(df_pop_long, on=['location_name', 'Year']).merge(df_life_exp_long, on=['location_name', 'Year'])

df_merged.rename(columns={'location_name': 'Country'}, inplace=True)

df_merged['Year'] = df_merged['Year'].astype(int)

data = {
    'Country': df_merged['Country'].tolist(),
    'Health_Exp_per_capita': df_merged['Health_Exp_per_capita'].tolist(),
    'GDP_per_capita': df_merged['GDP_per_capita'].tolist(),
    'Life_Exp' : df_merged["Life_Exp"].tolist(),
    'Mortality_Rate': df_merged['Mortality_Rate'].tolist(),
    'Population': df_merged['Population'].tolist(),
    'Year': df_merged['Year'].tolist()
}


##############################################################################
import streamlit as st
import pandas as pd
import plotly.express as px

# Assuming 'data' dictionary is already created and cleaned
df = pd.DataFrame(data)

st.set_page_config(page_title="Global Mortality Dashboard", layout="wide")

all_years = sorted(df["Year"].unique())
all_countries = sorted(df["Country"].unique())
# ✅ Updated this line to include 'Life_Exp'
numeric_columns = ['Health_Exp_per_capita', 'Mortality_Rate', 'Population', 'GDP_per_capita', 'Life_Exp']

# Sidebar for controls
st.sidebar.header("Filters")

year = st.sidebar.selectbox("Select Year", all_years, index=len(all_years) - 1)

x_col = st.sidebar.selectbox(
    "Select X-axis",
    options=numeric_columns,
    index=numeric_columns.index('Health_Exp_per_capita')
)

y_available = [col for col in numeric_columns if col != x_col]
y_col = st.sidebar.selectbox(
    "Select Y-axis",
    options=y_available,
    index=y_available.index('Mortality_Rate') if 'Mortality_Rate' in y_available else 0
)

size_available = [col for col in numeric_columns if col not in [x_col, y_col]]
size_col = st.sidebar.selectbox(
    "Select Bubble Size",
    options=size_available,
    index=size_available.index('Population') if 'Population' in size_available else 0
)

selected_countries = st.sidebar.multiselect(
    "Select Countries",
    options=all_countries,
    default=all_countries
)

st.sidebar.subheader("Filter Based on Selected Variables")

x_min, x_max = st.sidebar.slider(
    f"{x_col.replace('_', ' ').title()} Range",
    float(df[x_col].min()), float(df[x_col].max()),
    (float(df[x_col].min()), float(df[x_col].max()))
)

y_min, y_max = st.sidebar.slider(
    f"{y_col.replace('_', ' ').title()} Range",
    float(df[y_col].min()), float(df[y_col].max()),
    (float(df[y_col].min()), float(df[y_col].max()))
)

size_min, size_max = st.sidebar.slider(
    f"{size_col.replace('_', ' ').title()} Range",
    float(df[size_col].min()), float(df[size_col].max()),
    (float(df[size_col].min()), float(df[size_col].max()))
)

filtered_df = df[
    (df["Year"] == year) &
    (df["Country"].isin(selected_countries)) &
    (df[x_col].between(x_min, x_max)) &
    (df[y_col].between(y_min, y_max)) &
    (df[size_col].between(size_min, size_max))
]

st.subheader(f"{x_col.replace('_', ' ').title()} vs {y_col.replace('_', ' ').title()} | Bubble Size: {size_col.replace('_', ' ').title()} | Year: {year} | Countries Selected: {len(selected_countries)}")

if filtered_df.empty:
    st.warning("No data available for selected filters.")
else:
    fig_bubble = px.scatter(
        filtered_df,
        x=x_col,
        y=y_col,
        size=size_col,
        color="Country",
        hover_name="Country",
        size_max=60,
        labels={
            x_col: x_col.replace("_", " ").title(),
            y_col: y_col.replace("_", " ").title(),
            size_col: size_col.replace("_", " ").title()
        }
    )

    fig_bubble.update_traces(marker=dict(opacity=0.6, line=dict(width=1, color='black')))
    fig_bubble.update_layout(
        template="plotly_white",
        showlegend=False,
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            type="log",
            showgrid=False,
            showline=True,
            linecolor='black',
            zeroline=False
        ),
        yaxis=dict(
            showgrid=False,
            showline=True,
            linecolor='black',
            zeroline=False
        ),
        annotations=[dict(
            text=str(year),
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=100, color="rgba(200,200,200,0.3)")
        )]
    )
    st.plotly_chart(fig_bubble, use_container_width=True)
