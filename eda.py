# %% Imports
import pandas as pd
from IPython.display import display
import matplotlib.pyplot as plt

# %% Load dataset
df = pd.read_csv("porto/porto.csv")
cols = ["TRIP_ID", "CALL_TYPE", "ORIGIN_CALL", "ORIGIN_STAND",
        "TAXI_ID", "TIMESTAMP", "DAY_TYPE", "MISSING_DATA", "POLYLINE"]

# Notes of the columns we have to work with
identifying_cols = ["TRIP_ID", "ORIGIN_CALL", "ORIGIN_STAND", "TAXI_ID"]
cat_cols = ["CALL_TYPE", "DAY_TYPE", "MISSING_DATA"]
num_cols = ["TIMESTAMP", "POLYLINE"]

# %% - Dataset overview: describe(), head(), etc.
display(df.describe(include='all'))
display(df.head())
#display(df.shape())
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

# find how many trajectories are empty lists: []
empty = (df["POLYLINE"] == "[]").sum()
print("Empty polylines:", empty)

# Own column in the dataset, indicating missing GPS points for Polyline field
# Needs to be handled! 
print(df["MISSING_DATA"].value_counts())


#%% - Check for duplicate 
print("Duplicate TRIP_IDs:", df["TRIP_ID"].duplicated().sum())
# found 81, are these actual duplicates, or updated trip info, etc.


#%% - categorical columns plots
# 3 unique values
df["CALL_TYPE"].value_counts().sort_index().plot.bar(rot=0)
plt.title("CALL_TYPE")
plt.show()

# one unique value, all columsn are "A"
df["DAY_TYPE"].value_counts().sort_index().plot.bar(rot=0)
plt.title("DAY_TYPE")
plt.show()

# 10 rows with Ture (missing values in PolyLine field) 
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
time = pd.to_datetime(df["TIMESTAMP"].astype(int), unit="s")

# shownumber of trips per hour
time.dt.hour.value_counts().sort_index().plot.bar(rot=0)
plt.title("Trips per hour of day")
plt.show()

# weekdays, Monday=0, Thursda=1, etc.
time.dt.dayofweek.value_counts().sort_index().plot.bar(rot=0)
plt.title("Trips per weekday (0 = Monday)")
plt.show()

# Number of trips per day
plt.figure(figsize=(12, 4))
time.dt.date.value_counts().sort_index().plot()
plt.title("Trips per day")
plt.xlabel("Date")
plt.ylabel("Number of trips")
plt.show()
print(time.min(), time.max())

# %%
