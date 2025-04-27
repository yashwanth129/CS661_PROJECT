import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import numpy as np
from sklearn.preprocessing import MinMaxScaler
import torch
import torch.nn as nn
from plotly.subplots import make_subplots

os.environ["STREAMLIT_WATCHER_TYPE"] = "none"


# -------------------- PAGE CONFIG --------------------
st.set_page_config(layout="wide", page_title="Mortality Trend Forecasting")

# -------------------- LOAD DATA --------------------
@st.cache_data
def load_data():
    data = pd.read_parquet("pages\\filtered_data.parquet")
    location_map = pd.read_csv("pages\\location_mapping.csv")
    cause_map = pd.read_csv("pages\\cause_mapping.csv")
    return data, location_map, cause_map


# Create lag sequences function
def create_lag_sequences(values, sequence_length=3):
    sequences, targets = [], []
    for i in range(sequence_length, len(values)):
        sequences.append(values[i-sequence_length:i])
        targets.append(values[i])
    return np.array(sequences), np.array(targets)

# LSTM Model Class
class LSTMRegressor(nn.Module):
    def __init__(self, input_size=1, hidden_size=16, num_layers=1, dropout=0.0):
        super(LSTMRegressor, self).__init__()
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                            dropout=dropout if num_layers > 1 else 0.0, batch_first=True)
        self.fc = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])

# Forecast single prediction for 2022
def rolling_forecast_lstm(location_id, sex_id, cause_id, df):
    group_df = df[(df['location_id'] == location_id) &
                  (df['sex_id'] == sex_id) &
                  (df['cause_id'] == cause_id)].sort_values('year').copy()

    if group_df.shape[0] < 10:
        return "Not enough data to train"

    scaler = MinMaxScaler()
    scaled_vals = scaler.fit_transform(group_df[['val']].values)

    years = group_df['year'].values
    X_seq, y_seq = create_lag_sequences(scaled_vals[:len(group_df)-1], sequence_length=3)
    if len(X_seq) == 0:
        return "Not enough data to create sequences for prediction"

    X_tensor = torch.tensor(X_seq, dtype=torch.float32).view(-1, 3, 1)
    model = LSTMRegressor()
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    model.train()
    for _ in range(100):
        optimizer.zero_grad()
        output = model(X_tensor)
        loss = criterion(output.view(-1), torch.tensor(y_seq, dtype=torch.float32).view(-1))
        loss.backward()
        optimizer.step()

    last_3 = scaled_vals[-3:].reshape(1, 3, 1)
    input_tensor = torch.tensor(last_3, dtype=torch.float32)

    model.eval()
    with torch.no_grad():
        pred_scaled = model(input_tensor).item()

    pred_val = scaler.inverse_transform([[pred_scaled]])[0][0]
    actuals = group_df['val'].values[:len(group_df)-1]
    predicted_years = [2022]

    return actuals, [pred_val], years[:len(group_df)-1], predicted_years


data, location_map, cause_map = load_data()

# Merge names into the main dataframe
data = data.merge(location_map, on='location_id', how='left')
data = data.merge(cause_map, on='cause_id', how='left')

# -------------------- SIDEBAR FILTERS --------------------
with st.sidebar:
    st.header("Filters")

    # Country & Year for Pie Chart
    selected_country = st.selectbox("Select Country (Pie Chart)", sorted(data['location_name'].unique()))
    selected_year = st.selectbox("Select Year (Pie Chart)", sorted(data['year'].unique()))
    top_k = st.slider("Top K Causes", min_value=1, max_value=25, value=10, step=1)

    # Disease & Year for Map
    selected_disease = st.selectbox("Select Disease (Map)", sorted(data['cause_name'].unique()))
    map_year_options = ["All Years"] + sorted(data["year"].unique())
    selected_map_year = st.selectbox("Select Year (Map)", map_year_options)

# -------------------- PIE CHART --------------------
pie_data = data[
    (data['location_name'] == selected_country) &
    (data['year'] == selected_year) &
    (data['sex_id'] == 3)
]

# Filter and prepare
excluded = ['all_causes', 'All causes', 'Non-communicable diseases']
pie_data = pie_data[~pie_data['cause_name'].isin(excluded)]
pie_data = pie_data[['cause_name', 'val']].copy()
pie_data['val'] = pie_data['val'].fillna(0)
pie_data = pie_data[pie_data['val'] > 0]
pie_data = pie_data.sort_values(by='val', ascending=False).head(top_k)
pie_data['short_name'] = pie_data['cause_name'].apply(lambda x: x[:15] + '...' if len(x) > 15 else x)

# Plot pie
fig_pie = px.pie(
    pie_data,
    names='short_name',
    values='val',
    color_discrete_sequence=px.colors.sequential.Viridis,
    height=600
)

fig_pie.update_traces(
    textinfo='percent+label',
    textfont=dict(size=12),
    hovertemplate='<b>%{label}</b><br>Full Name: %{customdata}<br>Value: %{value:,.2f}<extra></extra>',
    customdata=pie_data['cause_name'],
    marker=dict(line=dict(color='white', width=2)),
    domain=dict(y=[0.15, 1.0])  # << move the pie up closer to title!
)

fig_pie.update_layout(
    showlegend=False,
    margin=dict(l=20, r=20, t=20, b=20),  # smaller top margin
    paper_bgcolor='rgba(0,0,0,0)',
    autosize=True,

)

# -------------------- MAP --------------------
map_data = data[data['cause_name'] == selected_disease]
if selected_map_year != "All Years":
    map_data = map_data[map_data['year'] == selected_map_year]

map_grouped = map_data.groupby('location_name', as_index=False)['val'].mean()

# Prepare full map coverage
all_countries = location_map['location_name'].unique()
map_df = pd.DataFrame({'Country': all_countries})
map_df = map_df.merge(map_grouped, left_on='Country', right_on='location_name', how='left')
map_df["Death_Display"] = map_df["val"].fillna(0)

colorscale = [
    [0, "#2c2c2c"], [0.00001, "#330000"], [0.2, "#800000"],
    [0.4, "#b30000"], [0.6, "#e34a33"], [0.8, "#fc8d59"], [1.0, "#fdbb84"]
]

fig_map = go.Figure(data=go.Choropleth(
    locations=map_df["Country"],
    locationmode="country names",
    z=map_df["Death_Display"],
    colorscale=colorscale,
    zmin=0,
    zmax=map_df["val"].max() if map_df["val"].max() else 1,
    marker_line_color="black",
    marker_line_width=0.4,
    colorbar_title="Death Rate",
    showscale=True,
    hovertemplate="<b>%{location}</b><br>Death Rate: %{z:.2f}<extra></extra>"
))

# Move the map down and remove background
fig_map.update_layout(
    geo=dict(
        projection_type="natural earth",
        showframe=True,
        showcoastlines=False,
        showland=True,
        landcolor="#111",
        oceancolor="rgb(0,0,50)",
        showocean=True,
        bgcolor="rgba(0,0,0,0)"  # transparent inside map
    ),
    paper_bgcolor="white",
    plot_bgcolor="rgb(0,0,0)",
    margin=dict(l=0, r=0, t=100, b=0),  # move map down
    title=dict(
        text=f"<b>{selected_disease} – Death Rate Visualization ({'All Years' if selected_map_year == 'All Years' else selected_map_year})</b>",
        font=dict(size=22, color="black"),
        x=0.5,   # center horizontally
        y=0.95,  # move higher vertically
        xanchor='center',  # anchor horizontally from center
        yanchor='top'      # anchor vertically from the top
    ),
    font=dict(color="black")
)


# -------------------- LAYOUT --------------------
# Adjusted column ratio (70:30)
col1, col2 = st.columns([6, 4])

# Left column (Map)
with col1:
    st.markdown(f"###  Disease Heatmap")
    st.plotly_chart(fig_map, use_container_width=True)

# Right column (Pie Chart)
with col2:
    st.markdown(f"### Top {top_k} Causes of Death in **{selected_country}** ({selected_year})")
    st.plotly_chart(fig_pie, use_container_width=True)

#st.set_page_config(layout="wide")
st.title(" Top 5 Countries by Mortality Rate (2010–2021)")

# --- Load CSVs ---
@st.cache_data
def load_data():
    filtered_data = pd.read_parquet("pages\\filtered_data.parquet")
    cause_mapping = pd.read_csv("pages\\cause_mapping.csv")
    location_mapping = pd.read_csv("pages\\location_mapping.csv")
    return filtered_data, cause_mapping, location_mapping

filtered_data, cause_mapping, location_mapping = load_data()

# --- Merge mapping ---
df = filtered_data.merge(cause_mapping, on='cause_id').merge(location_mapping, on='location_id')

# --- Sidebar Filters ---
st.sidebar.header("Filter Options")
selected_cause = st.sidebar.selectbox("Select Cause", sorted(df['cause_name'].unique()))
selected_sex = st.sidebar.radio("Select Sex", ["Male", "Female", "Both"])

sex_map = {"Male": 1, "Female": 2, "Both": 3}
sex_val = sex_map[selected_sex]

# --- Filter data ---
df = df[(df['cause_name'] == selected_cause) & (df['sex_id'] == sex_val)]

# --- Validate ---
years = list(range(2010, 2022))
bars_per_year = 5
df = df[df["year"].isin(years)]
if df.empty:
    st.warning("No data for selected filters and years.")
    st.stop()

# --- Top 5 countries per year ---
top_rows = []
for year in years:
    top = df[df["year"] == year].nlargest(bars_per_year, "val").sort_values("val", ascending=True)
    top_rows.append(top)
df_top = pd.concat(top_rows)

max_val = df_top["val"].max()
df_top["Normalized"] = df_top["val"] / max_val
df_top["year"] = df_top["year"].astype(str)

# --- Angle and Color ---
df_top = df_top.reset_index(drop=True)
df_top["Index"] = df_top.index
df_top["Angle"] = df_top["Index"] * (360 / len(df_top))
color_sequence = px.colors.qualitative.Set3
year_color_map = {year: color_sequence[i % len(color_sequence)] for i, year in enumerate(sorted(df_top["year"].unique()))}
df_top["Color"] = df_top["year"].map(year_color_map)
df_top["Label"] = df_top["location_name"] + " (" + df_top["year"] + ")"

# --- Create initial figure ---
fig = make_subplots(rows=1, cols=2, subplot_titles=("Radial View", "Bar Chart"),
                    specs=[[{'type': 'polar'}, {'type': 'xy'}]])

initial_year = str(years[0])
year_df = df_top[df_top["year"] == initial_year]

# Radial chart
fig.add_trace(
    go.Barpolar(
        r=year_df["Normalized"],
        theta=year_df["Angle"],
        marker_color=year_df["Color"],
        width=[(360 / len(df_top)) * 0.85] * len(year_df),
        hovertext=year_df["Label"] + "<br>Rate: " + year_df["val"].astype(int).astype(str),
        hoverinfo="text"
       
    ),
    row=1, col=1
)

# Horizontal bar
fig.add_trace(
    go.Bar(
        x=year_df["val"],
        y=year_df["location_name"],
        orientation="h",
        marker_color=year_df["Color"]
    ),
    row=1, col=2
)

fig.update_layout(
    title_text=f"Top 5 Countries by Mortality Rate (2010–2021) - {selected_cause} ({selected_sex})",
    showlegend=False,
    polar=dict(radialaxis=dict(visible=False), angularaxis=dict(showticklabels=False)),
    height=650,
)

# --- Frames ---
frames = []
for year in years:
    year_str = str(year)
    year_df = df_top[df_top["year"] == year_str]
    frames.append(
        go.Frame(
            data=[
                # Radial Chart
                go.Barpolar(
                    r=year_df["Normalized"],
                    theta=year_df["Angle"],
                    marker_color=year_df["Color"],
                    width=[(360 / len(df_top)) * 0.85] * len(year_df),
                    hovertext=year_df["Label"] + "<br>Rate: " + year_df["val"].astype(int).astype(str),
                    hoverinfo="text"
                ),
                # Horizontal Bar Chart
                go.Bar(
                    x=year_df["val"],
                    y=year_df["location_name"],
                    orientation="h",
                    marker_color=year_df["Color"]
                )
            ],
            name=f"frame_{year}",
            layout=go.Layout(
                annotations=[  # Updated annotation for each frame
                    dict(
                        text=f"<b>{year}</b>",  # The year annotation is updated dynamically here
                        x=0.21, y=0.5, xref="paper", yref="paper",
                        showarrow=False,
                        font=dict(size=30, color="black")
                    )
                ]
            )
        )
    )

fig.frames = frames


# --- Animation controls ---
fig.update_layout(
    updatemenus=[dict(
        type="buttons",
        showactive=False,
        buttons=[
            dict(
                label="Play",
                method="animate",
                args=[
                    [f"frame_{y}" for y in years],
                    {
                        "frame": {"duration": 1000, "redraw": True},
                        "fromcurrent": True,
                        "transition": {"duration": 300}
                    }
                ]
            ),
            dict(
                label="Pause",
                method="animate",
                args=[
                    [None],
                    {"frame": {"duration": 0, "redraw": False}, "mode": "immediate"}
                ]
            )
        ]
    )],
        sliders=[{
        "steps": [
            {
                "args": [[f"frame_{year}"], {"frame": {"duration": 1000, "redraw": True},
                                             "mode": "immediate",
                                             "transition": {"duration": 300}}],
                "label": str(year),
                "method": "animate"
            } for year in years
        ],
        "transition": {"duration": 300},
        "x": 0.1,
        "len": 0.8,
        "currentvalue": {"prefix": "Year: "}
    }]

    
)

# --- Display chart ---
st.plotly_chart(fig, use_container_width=True)
# Streamlit UI
def main():
    st.title("Mortality Trend Forecasting")

    df = pd.read_parquet("pages\\filtered_data.parquet")
    cause_mapping = pd.read_csv("pages\\cause_mapping.csv")
    location_mapping = pd.read_csv("pages\\location_mapping.csv")

    df = df.merge(cause_mapping, on='cause_id', how='left')
    df = df.merge(location_mapping, on='location_id', how='left')

    cause_id = st.selectbox("Choose Cause of Death", df['cause_name'].unique())
    location_id = st.selectbox("Choose Country", df['location_name'].unique())

    cause_id_selected = cause_mapping[cause_mapping['cause_name'] == cause_id]['cause_id'].values[0]
    location_id_selected = location_mapping[location_mapping['location_name'] == location_id]['location_id'].values[0]

    st.write(f"Predicting Mortality for Cause: {cause_id}, Country: {location_id}")

    results = rolling_forecast_lstm(location_id_selected, 3, cause_id_selected, df)

    if isinstance(results, str):
        st.warning(results)
        return

    actuals, predictions, actual_years, predicted_years = results

    # Animate mortality plot
    frames = []
    for i in range(len(actuals)):
        frames.append(go.Frame(
            data=[go.Scatter(x=actual_years[:i+1], y=actuals[:i+1], mode='lines',
                             name='Actual (1980-2021)', line=dict(color='blue', width=3))],
            name=f'frame_{i}'
        ))

    frames.append(go.Frame(
        data=[
            go.Scatter(x=actual_years, y=actuals, mode='lines',
                       name='Actual (1980-2021)', line=dict(color='blue', width=3)),
            go.Scatter(x=[actual_years[-1], predicted_years[0]],
                       y=[actuals[-1], predictions[0]],
                       mode='lines+markers', name='Predicted (2022)',
                       line=dict(color='red', width=3, dash='dot'),
                       marker=dict(color='red', size=12, symbol='circle'))
        ],
        name='frame_final'
    ))

    fig = go.Figure(
        data=[
            go.Scatter(x=[], y=[], mode='lines', name='Actual (1980-2021)', line=dict(color='blue', width=3)),
            go.Scatter(x=[], y=[], mode='markers', name='Predicted (2022)', marker=dict(color='red', size=12))
        ],
        layout=go.Layout(
            title=f"Mortality Trend for Cause: {cause_id} in {location_id}",
            xaxis_title="Year",
            yaxis_title="Mortality Rate per 100,000",
            showlegend=True,
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white'),
            updatemenus=[{
                'buttons': [
                    {'args': [None, {'frame': {'duration': 500, 'redraw': True}, 'fromcurrent': True}],
                     'label': 'Play', 'method': 'animate'},
                    {'args': [[None], {'frame': {'duration': 0, 'redraw': False},
                                       'mode': 'immediate', 'transition': {'duration': 0}}],
                     'label': 'Pause', 'method': 'animate'}
                ],
                'direction': 'left',
                'pad': {'r': 10, 't': 87},
                'showactive': False,
                'type': 'buttons',
                'x': 0.1,
                'xanchor': 'right',
                'y': 0,
                'yanchor': 'top',
                'bgcolor':'black',
                'bordercolor':'white',
                'font':{'color':'white'}
            }],
            margin=dict(l=40, r=40, t=50, b=40)
        ),
        frames=frames
    )

    st.plotly_chart(fig, use_container_width=True)

    # 🏆 Top 5 countries with highest 2022 predicted value for this cause
    st.subheader("Top 5 Countries by Predicted Mortality in 2022")

    top_countries_df = df[df['cause_id'] == cause_id_selected]
    country_preds = []

    for loc_id in top_countries_df['location_id'].unique():
        res = rolling_forecast_lstm(loc_id, 3, cause_id_selected, df)
        if isinstance(res, str):
            continue
        _, pred_2022, _, _ = res
        loc_name = location_mapping[location_mapping['location_id'] == loc_id]['location_name'].values[0]
        country_preds.append((loc_name, pred_2022[0]))

    top_5 = sorted(country_preds, key=lambda x: x[1], reverse=True)[:5]

    for i, (country, pred) in enumerate(top_5, 1):
        st.write(f"{i}. {country}: {pred:.2f} per 100,000")

if __name__ == "__main__":
    main()






