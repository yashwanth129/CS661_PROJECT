import pandas as pd

dataset_path = "./parquet_files/"
#gbd_path = f"{dataset_path}GBD.parquet"
gbd_path = f"pages\\GBD.parquet"
location_mapping = f"pages\\location_mapping.parquet"
cause_mapping = f"pages\\cause_mapping.parquet"
# gdp_path = f"{dataset_path}GDP.parquet"
gdp_path = f"pages\\gdp_processed.parquet"
hie_path = f"pages\\IHME_GBD_2021_HIERARCHIES_Y2024M05D16.XLSX"

df = pd.read_parquet(gbd_path)



df_rate = df[df["metric_name"] == "Rate"]

df_rate = df_rate.drop(columns=['metric_name'])

df_rate = df_rate.rename(columns={"val": "mortality_rate"})


df_rate = df_rate.groupby(['cause_id','location_id', 'year'])['mortality_rate'].sum().reset_index()




df_cause = pd.read_parquet(cause_mapping)

df_loc = pd.read_parquet(location_mapping)

merged_df = pd.merge(df_loc, df_rate, on='location_id')

merged_df = pd.merge(merged_df, df_cause, on='cause_id')

merged_df.drop(columns=['location_id', 'cause_id'])

df = merged_df.groupby(['location_name', 'cause_name', 'year'])['mortality_rate'].sum().reset_index()

df_hie = pd.read_excel(hie_path, sheet_name = 'Cause Hierarchy')
causes = df_hie[df_hie["Level"] == 3]["Cause Name"].unique()
df = df[df['cause_name'].isin(causes)]

world_ = df.groupby(['cause_name','year' ])['mortality_rate'].sum().reset_index()
world_['location_name'] = 'World'
df = pd.concat([df, world_], ignore_index=True)




import streamlit as st
import pandas as pd
import plotly.express as px

# Streamlit app title
st.title("Interactive Mortality Rate Dashboard")

# Sidebar for user input
st.sidebar.header("Filter Options")

# Get unique years and countries
years = sorted(df['year'].unique())
countries = sorted(df['location_name'].unique())

# Find default indices
default_year_index = years.index(2021) if 2021 in years else 0
default_country_index = countries.index('World') if 'World' in countries else 0

# Dropdowns with default selections
selected_year = st.sidebar.selectbox("Select Year:", years, index=default_year_index)
selected_country = st.sidebar.selectbox("Select Country:", countries, index=default_country_index)

# Filter the data
df_filtered = df[(df['year'] == selected_year) & (df['location_name'] == selected_country)]

# Remove zero mortality rates
df_filtered = df_filtered[df_filtered['mortality_rate'] > 0]

# Take Top 50 causes by mortality rate
df_filtered = df_filtered.sort_values(by='mortality_rate', ascending=False).head(50)

# Function to wrap long cause names
def insert_line_breaks(text, max_chars=15):
    words = text.split()
    lines = []
    current_line = ''
    for word in words:
        if len(current_line) + len(word) + 1 <= max_chars:
            current_line += (' ' + word if current_line else word)
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return '<br>'.join(lines)

# Apply line breaks to 'cause_name'
df_filtered['cause_name_wrapped'] = df_filtered['cause_name'].apply(lambda x: insert_line_breaks(x))

# Define vibrant colors
color_sequence = [
    "#FF0000", "#FF6347", "#FF4500", "#FFD700",  # Red/Yellow shades
    "#32CD32", "#00FF00", "#008000",             # Green shades
    "#1E90FF", "#00BFFF", "#4682B4",             # Blue shades
    "#8A2BE2", "#4B0082", "#9370DB"              # Purple shades
]

# Build the treemap
fig = px.treemap(
    df_filtered,
    path=['cause_name_wrapped'],
    values='mortality_rate',
    color_discrete_sequence=color_sequence,
    title=f"Top 50 Causes of Mortality - {selected_country} ({selected_year})",
    template="plotly_dark"
)

# Customize text
fig.update_traces(
    textinfo="label+value",
    textfont=dict(size=18),
    insidetextfont=dict(size=16, color="white"),
    texttemplate="%{label}<br>%{value}",
)

# Layout adjustments
fig.update_layout(
    margin=dict(t=50, l=25, r=25, b=25),
    uniformtext_minsize=14,
)

# Show the treemap
st.plotly_chart(fig, use_container_width=True)

