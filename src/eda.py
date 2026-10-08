# %% Imports
import pandas as pd
from IPython.display import display
import matplotlib.pyplot as plt
import json
from haversine import haversine

# %% Load dataset
df = pd.read_csv("porto/porto.csv")
cols = ["TRIP_ID", "CALL_TYPE", "ORIGIN_CALL", "ORIGIN_STAND",
        "TAXI_ID", "TIMESTAMP", "DAY_TYPE", "MISSING_DATA", "POLYLINE"]

# Notes of the columns we have to work with
identifying_cols = ["TRIP_ID", "ORIGIN_CALL", "ORIGIN_STAND", "TAXI_ID"]
cat_cols = ["CALL_TYPE", "DAY_TYPE", "MISSING_DATA"]
num_cols = ["TIMESTAMP", "POLYLINE"]

# %% - Dataset overview: describe(), head(), etc.
print(df.shape)
display(df.describe(include='all'))
display(df.head())
print(df.info()) # data types, size, etc.
print(df.nunique()) # shows how many unique values in each column

#%% EDA - Missing values
missing = (df.isna() | (df == "")).sum()
print(missing)

missing.plot.bar()
plt.title("Missing values per column")
plt.ylabel("Number of rows")
plt.tight_layout()
plt.show()

#%% Missing values in POLYLINE
# find how many trajectories are empty lists: []
empty = (df["POLYLINE"] == "[]").sum()
print("Polylines with empty lists []:", empty)

# Column in the set indicating missing GPS points for Polyline field
print(df["MISSING_DATA"].value_counts())

# check if empty polylines are actually marked in missing data column
print(pd.crosstab(df["MISSING_DATA"], df["POLYLINE"] == "[]"))


#%% EDA - Duplicates 
print("Duplicate TRIP_IDs:", df["TRIP_ID"].duplicated().sum())
print("Fully identical rows:", df.duplicated().sum())
 
# are these actual duplicates, or different trips with the same id?
dups = df[df["TRIP_ID"].duplicated(keep=False)].sort_values("TRIP_ID")
display(dups.head(10))

# which columns differ between rows that share a TRIP_ID?
differs = (dups.groupby("TRIP_ID").nunique(dropna=False) > 1).sum()
differs.plot.bar(rot=45)
plt.title("Columns that differ within duplicate TRIP_IDs")
plt.ylabel("Number of TRIP_IDs")
plt.tight_layout()
plt.show()

#%% - EDA Categorical columns
# ORIGIN_CALL should only be set for A, ORIGIN_STAND only for B
print(df["CALL_TYPE"].value_counts().sort_index())
print(df.groupby("CALL_TYPE")["ORIGIN_CALL"].count())
print(df.groupby("CALL_TYPE")["ORIGIN_STAND"].count())
# all A trips have ORIGIN_CALL, but some B trips have no ORIGIN_STAND

#%% - categorical columns plots
# 3 unique values
df["CALL_TYPE"].value_counts().sort_index().plot.bar(rot=0)
plt.title("CALL_TYPE")
plt.show()

# one unique value, all columsn are "A"
df["DAY_TYPE"].value_counts().sort_index().plot.bar(rot=0)
plt.title("DAY_TYPE")
plt.show()

# 10 rows with true (missing values in PolyLine field) 
df["MISSING_DATA"].value_counts().sort_index().plot.bar(rot=0)
plt.title("MISSING_DATA")
plt.show()


#%% - Trips per taxi (e.g. how many taxis made 2000 trips)
trips_per_taxi = df["TAXI_ID"].value_counts()
print(df["TAXI_ID"].nunique())
print(trips_per_taxi.describe())

trips_per_taxi.plot.hist(bins=50)
plt.title("Histogram of trips per taxi (combined)")
plt.xlabel("Number of trips")
plt.ylabel("Number of taxis")
plt.show()

# %% - Plots of times of trips, days, etc.
time = pd.to_datetime(df["TIMESTAMP"].astype(int), unit="s")   # UTC
local = time.dt.tz_localize("UTC").dt.tz_convert("Europe/Lisbon").dt.tz_localize(None)

# UTC vs local time: Porto is UTC+1 in summer, so the hours are shifted
summer = time.dt.month.isin([7, 8])
pd.DataFrame({
    "UTC": time[summer].dt.hour.value_counts().sort_index(),
    "Local (Lisbon)": local[summer].dt.hour.value_counts().sort_index(),
}).plot(marker="o")
plt.title("Trips per hour in July–August: UTC vs local time")
plt.xlabel("Hour")
plt.show()

# from here on, use local time (same as in data_cleaning.py)
local.dt.hour.value_counts().sort_index().plot.bar(rot=0)
plt.title("Trips per hour of day")
plt.show()

# weekdays, Monday=0, Tuesday=1, etc.
local.dt.dayofweek.value_counts().sort_index().plot.bar(rot=0)
plt.title("Trips per weekday (0 = Monday)")
plt.show()

# Number of trips per day
plt.figure(figsize=(12, 4))
local.dt.date.value_counts().sort_index().plot()
plt.title("Trips per day")
plt.xlabel("Date")
plt.ylabel("Number of trips")
plt.show()
print(local.min(), local.max())

# %% Number of GPS points per trip
df["points"] = df["POLYLINE"].str.count(r"\],\[") + 1
df.loc[df["POLYLINE"] == "[]", "points"] = 0
print(df["points"].describe())

# each point is 15 seconds apart
df["minutes"] = (df["points"] - 1).clip(lower=0) * 15 / 60

df.loc[df["points"] <= 3000, "points"].plot.hist(bins=100, logy=True)
plt.title("GPS points per trip (capped at 3000 points)")
plt.xlabel("Points")
plt.show()

df.loc[df["minutes"] < 60, "minutes"].plot.hist(bins=60, logy=True)
plt.title("Trip duration under 60 minutes")
plt.xlabel("Minutes")
plt.show()

print((df["points"] == 1).sum(), "trips with one point")
print((df["points"] < 3).sum(), "trips with fewer than three points")
print((df["minutes"] > 240).sum(), "trips longer than 4 hours")
print("Highest amounts of points in a trip: ", (df["points"]).max())
print("Longest trip:", df["minutes"].max() / 60, "hours")

# %% Sample of trips, parsed to lists of [lon, lat]
sample = df[df["points"] > 0].sample(20000, random_state=1).copy()
sample["coords"] = sample["POLYLINE"].apply(json.loads)

# %% example trajectories
plt.figure(figsize=(8, 8))
for coords in sample["coords"].head(100):
    lons = [p[0] for p in coords]
    lats = [p[1] for p in coords]
    plt.plot(lons, lats, marker=".", markersize=3)
plt.title("Example trajectories")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.show()

# %% Trip distance and max speed (haversine wants (lat, lon))
def trip_stats(coords):
    dist = 0
    max_speed = 0
    for i in range(1, len(coords)):
        a = (coords[i - 1][1], coords[i - 1][0])
        b = (coords[i][1], coords[i][0])
        d = haversine(a, b)                        # km
        dist += d
        max_speed = max(max_speed, d / (15 / 3600))  # km/h
    return dist, max_speed

stats = sample["coords"].apply(trip_stats)
sample["km"] = stats.apply(lambda x: x[0])
sample["max_speed"] = stats.apply(lambda x: x[1])

sample.loc[sample["km"] < 30, "km"].plot.hist(bins=60, logy=True)
plt.title("Trip distance (km)")
plt.xlabel("km")
plt.show()

THRESHOLD = 140

sample["max_speed"].clip(upper=500).plot.hist(bins=100, logy=True)
plt.axvline(THRESHOLD, color="red", linestyle="--", label=f"{THRESHOLD} km/h")
plt.title("Max speed per trip (clipped at 500 km/h)")
plt.xlabel("km/h")
plt.legend()
plt.show()

# how many trips each threshold would flag
for t in [100, 140, 150, 200, 300]:
    print(f"> {t} km/h: {(sample['max_speed'] > t).mean() * 100:.1f}% of trips")

# %% Trips with the biggest jumps
print(sample.nlargest(5, "max_speed")[["TRIP_ID", "max_speed", "points"]])
# TRIP_ID     max_speed  points 
# 597583   1383666543620000534  21812.631343     329
# 1224320  1395653018620000698  11658.738772     181
# 318134   1378881561620000178  10026.690618     309
# 1587561  1402067105620000207   7811.154926     125
# 41298    1373361455620000541   3401.758789     371

# %% Plot a single trip
#trip = sample.loc[sample["max_speed"].idxmax()]   # trip with the biggest jump
trip = sample[sample["TRIP_ID"] == 1378881561620000178].iloc[0]   # or pick one by id

lons = [p[0] for p in trip["coords"]]
lats = [p[1] for p in trip["coords"]]

plt.figure(figsize=(8, 8))
plt.plot(lons, lats, marker=".", markersize=4)
plt.title(f"Trip {trip['TRIP_ID']}, max speed {trip['max_speed']:.0f} km/h")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.show()

# %%
