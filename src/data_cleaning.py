#%%
import json
import numpy as np
import pandas as pd
from haversine import haversine_vector, Unit

THRESHOLD = 150   # km/h

# 1. load data
# read everything as text, so empty cells stay "", this will be null later
df = pd.read_csv("porto/porto.csv", dtype=str, keep_default_na=False)

# 2. Drop duplicate TRIP_IDs, keep the first occurrence of each.
before = len(df)
df = df.drop_duplicates(subset="TRIP_ID", keep="first")
print(before - len(df), "duplicate rows dropped")

# 3. Empty fields become NULL (NaN becomes NULL on insert)
df["ORIGIN_CALL"] = df["ORIGIN_CALL"].replace("", np.nan)
df["ORIGIN_STAND"] = df["ORIGIN_STAND"].replace("", np.nan)

# 4. MISSING_DATA as a real boolean instead of the text "True"/"False".
df["MISSING_DATA"] = df["MISSING_DATA"] == "True"

# 5. Function that reads POLYLINE for each trip, and calculates feature we might need:
# GPS point count, distance, top speed, start/end coords.
def trip_features(polyline):
    coords = json.loads(polyline)
    n = len(coords)

    if n == 0:
        return pd.Series([0, 0.0, 0.0, None, None, None, None]) 

    start_lon, start_lat = coords[0]
    end_lon, end_lat = coords[-1]

    if n == 1: 
        return pd.Series([1, 0.0, 0.0, start_lon, start_lat, end_lon, end_lat])

    pts = np.array(coords)[:, ::-1]  # (lon, lat) -> (lat, lon)
    dist = haversine_vector(pts[:-1], pts[1:], Unit.KILOMETERS)
    km = dist.sum()
    max_speed = dist.max() / (15/3600) # 15 seconds between gps poitns
    return pd.Series([n, km, max_speed, start_lon, start_lat, end_lon, end_lat])

# apply polyline function
feature_cols = ["n_points", "distance_km", "max_speed",
                "start_lon", "start_lat", "end_lon", "end_lat"]
df[feature_cols] = df["POLYLINE"].apply(trip_features)


# 6. Start and end time. Points are 15s apart, so end time follows from the point count alone
df["start_time"] = pd.to_datetime(df["TIMESTAMP"].astype("int64"), unit="s")
df["end_time"] = df["start_time"] + pd.to_timedelta((df["n_points"] - 1).clip(lower=0) * 15, unit="s")

# 7. Flag trips with speed above decided threshold (e.g. because of GPS dropout, tunnel)
df["is_flagged"] = df["max_speed"] > THRESHOLD
print(df["is_flagged"].sum(), "flagged trips of", len(df))

# Last, save the cleaned data, ready for insertion
df.to_csv("porto/porto_clean.csv", index=False)
