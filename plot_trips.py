# %% Imports and settings
import json

import pandas as pd
import plotly.express as px

N_TRIPS = 10          # number of trips to plot
RANDOM = True         # True: random sample of trips, False: the first N_TRIPS trips
SEED = 42             # change to get a different random sample
TRIP_IDS = []         # plot these trip IDs instead, e.g. [1372636858620000589]
MIN_POINTS = 3        # skip empty and very short trips

# %%

#TRIP_IDS = pd.read_csv("fast_trip_ids.csv", header=None)[0].tolist()
TRIP_IDS = [1383666543620000534] # Fast trip example


# %% Load trips (reading the whole CSV takes ~15 s, only needed once)
trips = pd.read_csv("porto/porto.csv", usecols=["TRIP_ID", "TAXI_ID", "CALL_TYPE", "TIMESTAMP", "POLYLINE"])
trips["N_POINTS"] = trips["POLYLINE"].str.count(r"\[") - 1   # "[]" -> 0

# %% Select trips
if TRIP_IDS:
    selected = trips[trips["TRIP_ID"].isin(TRIP_IDS)][0:50]
else:
    candidates = trips[trips["N_POINTS"] >= MIN_POINTS]
    selected = candidates.sample(N_TRIPS, random_state=SEED) if RANDOM else candidates.head(N_TRIPS)


def to_points(trips):
    """One row per GPS point: TRIP_ID, SEQ, LON, LAT (+ trip info for hover)."""
    points = trips.assign(POINT=trips["POLYLINE"].map(json.loads)).explode("POINT").dropna(subset="POINT")
    points["SEQ"] = points.groupby("TRIP_ID").cumcount()
    points["LON"] = points["POINT"].str[0]
    points["LAT"] = points["POINT"].str[1]
    points["TIME"] = pd.to_datetime(points["TIMESTAMP"] + points["SEQ"] * 15, unit="s")
    points["TRIP_ID"] = points["TRIP_ID"].astype(str)   # categorical colours instead of a colour scale
    return points.drop(columns=["POLYLINE", "POINT"])


points = to_points(selected)
print(f"{points['TRIP_ID'].nunique()} trips, {len(points)} points")

# %% Plot trips on a map
fig = px.line_map(
    points,
    lat="LAT",
    lon="LON",
    color="TRIP_ID",
    hover_data=["TAXI_ID", "CALL_TYPE", "SEQ", "TIME"],
    zoom=11,
    height=800,
)
fig.update_traces(mode="lines+markers", marker={"size": 5})

# Mark where each trip starts
starts = points[points["SEQ"] == 0]
fig.add_scattermap(lat=starts["LAT"], lon=starts["LON"], mode="markers",
                   marker={"size": 12, "color": "black"}, name="start", hovertext=starts["TRIP_ID"])

fig.update_layout(map_style="open-street-map", margin={"r": 0, "t": 0, "l": 0, "b": 0})
fig.show()
