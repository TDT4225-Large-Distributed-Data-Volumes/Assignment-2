#%%
import json
import numpy as np
import pandas as pd
from haversine import haversine_vector, Unit

THRESHOLD = 140   # km/h, based on EDA findings

# 1. load data
# read everything as text, so empty cells stay "", this will be null later
df = pd.read_csv("porto/porto.csv", dtype=str, keep_default_na=False)

# 2. Duplicate TRIP_IDs. Exact copies are harmless, so keep one of each.
# Copies that differ (same taxi and start time, different POLYLINE etc.) conflict,
# and we can't tell which one is correct, so drop all of them.
before = len(df)
df = df.drop_duplicates(keep="first") # drop exact duplicates
df = df.drop_duplicates(subset="TRIP_ID", keep=False) # drop all trips with duplicate id
print(before - len(df), "duplicate rows dropped")

# 2b. DAY_TYPE is 'A' for every trip, so it holds no information.
print("DAY_TYPE values:", df["DAY_TYPE"].unique())
df = df.drop(columns="DAY_TYPE")

# 3. Empty fields become NULL (NaN becomes NULL on insert)
df["ORIGIN_CALL"] = df["ORIGIN_CALL"].replace("", np.nan)
df["ORIGIN_STAND"] = df["ORIGIN_STAND"].replace("", np.nan)

# 4. MISSING_DATA as a real boolean instead of the text "True"/"False".
df["MISSING_DATA"] = df["MISSING_DATA"] == "True"

# 5. Function that reads POLYLINE for each trip, and calculates feature we might need:
# GPS point count, distance, top speed, start/end coords.
def trip_features(row):
    coords = json.loads(row["POLYLINE"])
    n = len(coords)

    # Empty polyline: we know nothing about the trip, so distance and speed are NULL
    if n == 0:
        return pd.Series([0, None, None, None, None, None, None])

    start_lon, start_lat = coords[0]
    end_lon, end_lat = coords[-1]

    # Trips with missing GPS points have gaps, so distance and speed would be wrong.
    # Set them to NULL, but keep point count and start/end coords.
    if row["MISSING_DATA"]:
        return pd.Series([n, None, None, start_lon, start_lat, end_lon, end_lat])

    if n == 1:
        return pd.Series([1, 0.0, 0.0, start_lon, start_lat, end_lon, end_lat])

    pts = np.array(coords)[:, ::-1]  # (lon, lat) -> (lat, lon)
    dist = haversine_vector(pts[:-1], pts[1:], Unit.KILOMETERS)
    km = dist.sum()
    max_speed = dist.max() / (15/3600) # 15 seconds between gps points
    return pd.Series([n, km, max_speed, start_lon, start_lat, end_lon, end_lat])

# apply polyline function on each row, since it needs both POLYLINE and MISSING_DATA
feature_cols = ["n_points", "distance_km", "max_speed",
                "start_lon", "start_lat", "end_lon", "end_lat"]
df[feature_cols] = df[["POLYLINE", "MISSING_DATA"]].apply(trip_features, axis=1)


# 6. Start and end time. Points are 15s apart, so end time follows from the point count alone
# TIMESTAMP is a Unix timestamp (UTC). Porto uses Europe/Lisbon time (UTC+0 winter, UTC+1 summer),
# so convert to local time, then drop the zone info since MySQL DATETIME doesn't store it.
# end_time is computed in UTC first, so trips crossing a daylight saving change get the right length.
def to_local(t):
    return t.dt.tz_localize("UTC").dt.tz_convert("Europe/Lisbon").dt.tz_localize(None)

start_utc = pd.to_datetime(df["TIMESTAMP"].astype("int64"), unit="s")
end_utc = start_utc + pd.to_timedelta((df["n_points"] - 1).clip(lower=0) * 15, unit="s")
df["start_time"] = to_local(start_utc)

# end_time is NULL for trips with missing data (point count is incomplete)
# and for empty polylines (no points to count)
unknown = df["MISSING_DATA"] | (df["n_points"] == 0)
df["end_time"] = to_local(end_utc).mask(unknown)

# 7. Flag trips with speed above decided threshold (e.g. because of GPS dropout, tunnel)
# NULL when we don't know the speed (missing data or empty polyline)
df["is_flagged"] = (df["max_speed"] > THRESHOLD).astype("boolean").mask(df["max_speed"].isna())
print(df["is_flagged"].sum(), "flagged trips of", len(df))

# 8. MySQL types: booleans as 1/0 (NULL stays empty), point count as a whole number
df["MISSING_DATA"] = df["MISSING_DATA"].astype("Int8")
df["is_flagged"] = df["is_flagged"].astype("Int8")
df["n_points"] = df["n_points"].astype(int)

# Last, save the cleaned data, ready for insertion
df.to_csv("porto/porto_clean.csv", index=False)

# %%
