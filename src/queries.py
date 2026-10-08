# %%
import math

import polars as pl
from haversine import Unit, haversine, haversine_vector

from local_db import get_connection

connection = get_connection()
cursor = connection.cursor()

# Show up to 25 rows (all of every top 20) and round floats when displaying
pl.Config.set_tbl_rows(25)
pl.Config.set_float_precision(2)


def run(query, params=None, show=True):
    # Runs a query, prints the result and returns it as a polars DataFrame.
    # MySQL returns AVG/SUM results as Decimal, so those are cast to floats for nicer display.
    # show=False for queries that only fetch data for further processing in Python.
    cursor.execute(query, params)
    df = pl.DataFrame(cursor.fetchall(), schema=cursor.column_names, orient="row")
    df = df.with_columns(pl.col(pl.Decimal).cast(pl.Float64))
    if show:
        print(df)
    return df


# %%
# Q1: How many taxis, trips, and total GPS points are there?
run("""
SELECT
    (SELECT COUNT(*) FROM taxi)      AS taxis,
    (SELECT COUNT(*) FROM trip)      AS trips,
    (SELECT COUNT(*) FROM gps_point) AS gps_points
""");
""" output: 
    shape: (1, 3)
    ┌───────┬─────────┬────────────┐
    │ taxis ┆ trips   ┆ gps_points │
    │ ---   ┆ ---     ┆ ---        │
    │ i64   ┆ i64     ┆ i64        │
    ╞═══════╪═════════╪════════════╡
    │ 448   ┆ 1710511 ┆ 83407339   │
    └───────┴─────────┴────────────┘
"""

# %%
# Q2: What is the average number of trips per taxi?
# LEFT JOIN from taxi, so a taxi without trips would count as 0 instead of being left out
run("""
SELECT AVG(n_trips) AS avg_trips_per_taxi
FROM (
    SELECT taxi.taxi_id, COUNT(trip.trip_id) AS n_trips
    FROM taxi
    LEFT JOIN trip ON trip.taxi_id = taxi.taxi_id
    GROUP BY taxi.taxi_id
) AS per_taxi
""");
""" output:
    shape: (1, 1)
    ┌────────────────────┐
    │ avg_trips_per_taxi │
    │ ---                │
    │ f64                │
    ╞════════════════════╡
    │ 3818.10            │
    └────────────────────┘

"""

# %%
# Q3: List the top 20 taxis with the most trips.
run("""
SELECT taxi_id, COUNT(*) AS n_trips
FROM trip
GROUP BY taxi_id
ORDER BY n_trips DESC
LIMIT 20
""");
""" output:
    shape: (20, 2)
    ┌──────────┬─────────┐
    │ taxi_id  ┆ n_trips │
    │ ---      ┆ ---     │
    │ i64      ┆ i64     │
    ╞══════════╪═════════╡
    │ 20000080 ┆ 10716   │
    │ 20000403 ┆ 9237    │
    │ 20000066 ┆ 8437    │
    │ 20000364 ┆ 7821    │
    │ 20000483 ┆ 7729    │
    │ 20000129 ┆ 7607    │
    │ 20000307 ┆ 7496    │
    │ 20000621 ┆ 7276    │
    │ 20000089 ┆ 7265    │
    │ 20000424 ┆ 7176    │
    │ 20000492 ┆ 7171    │
    │ 20000529 ┆ 6937    │
    │ 20000616 ┆ 6924    │
    │ 20000678 ┆ 6538    │
    │ 20000372 ┆ 6535    │
    │ 20000304 ┆ 6505    │
    │ 20000042 ┆ 6467    │
    │ 20000325 ┆ 6460    │
    │ 20000179 ┆ 6430    │
    │ 20000235 ┆ 6410    │
    └──────────┴─────────┘
"""

# %%
# Q4a: What is the most used call type per taxi?
# Count trips per (taxi, call type) and rank the call types within each taxi.
# RANK gives ties the same rank, so a taxi with a tie shows up once per tied call type.
most_used = run("""
WITH counts AS (
    SELECT taxi_id, call_type, COUNT(*) AS n_trips,
           RANK() OVER (PARTITION BY taxi_id ORDER BY COUNT(*) DESC) AS rnk
    FROM trip
    GROUP BY taxi_id, call_type
)
SELECT taxi_id, call_type AS most_used_call_type, n_trips
FROM counts
WHERE rnk = 1
ORDER BY taxi_id
""")

# Summary: how many taxis have each call type as their most used
print(most_used.group_by("most_used_call_type").agg(pl.len().alias("n_taxis")).sort("most_used_call_type"))
""" output:
    shape: (449, 3)
    ┌──────────┬─────────────────────┬─────────┐
    │ taxi_id  ┆ most_used_call_type ┆ n_trips │
    │ ---      ┆ ---                 ┆ ---     │
    │ i64      ┆ str                 ┆ i64     │
    ╞══════════╪═════════════════════╪═════════╡
    │ 20000001 ┆ B                   ┆ 1311    │
    │ 20000002 ┆ B                   ┆ 1576    │
    │ 20000003 ┆ C                   ┆ 844     │
    │ 20000004 ┆ B                   ┆ 2680    │
    │ 20000005 ┆ B                   ┆ 3034    │
    │ 20000006 ┆ B                   ┆ 1702    │
    │ 20000007 ┆ B                   ┆ 2770    │
    │ 20000008 ┆ B                   ┆ 2665    │
    │ 20000009 ┆ B                   ┆ 2099    │
    │ 20000010 ┆ B                   ┆ 2842    │
    │ 20000011 ┆ B                   ┆ 2622    │
    │ 20000012 ┆ B                   ┆ 2257    │
    │ 20000013 ┆ B                   ┆ 2581    │
    │ …        ┆ …                   ┆ …       │
    │ 20000901 ┆ C                   ┆ 1695    │
    │ 20000902 ┆ B                   ┆ 422     │
    │ 20000903 ┆ B                   ┆ 1070    │
    │ 20000904 ┆ C                   ┆ 3026    │
    │ 20000911 ┆ C                   ┆ 2       │
    │ 20000931 ┆ A                   ┆ 1       │
    │ 20000940 ┆ A                   ┆ 1       │
    │ 20000941 ┆ A                   ┆ 9       │
    │ 20000969 ┆ C                   ┆ 61      │
    │ 20000970 ┆ C                   ┆ 1       │
    │ 20000980 ┆ C                   ┆ 5       │
    │ 20000981 ┆ C                   ┆ 19      │
    └──────────┴─────────────────────┴─────────┘
    shape: (3, 2)
    ┌─────────────────────┬─────────┐
    │ most_used_call_type ┆ n_taxis │
    │ ---                 ┆ ---     │
    │ str                 ┆ u32     │
    ╞═════════════════════╪═════════╡
    │ A                   ┆ 12      │
    │ B                   ┆ 354     │
    │ C                   ┆ 83      │
    └─────────────────────┴─────────┘
"""

# %%
# Q4b: For each call type, compute the average trip duration and distance, and also report the share
# of trips starting in four time bands: 00–06, 06–12, 12–18, and 18–24.
# AVG skips NULLs, so trips with missing data or no GPS points only count towards the time band
# shares. start_time is Porto local time.
run("""
SELECT call_type,
       COUNT(*)                                            AS n_trips,
       AVG(duration_s) / 60                                AS avg_duration_min,
       AVG(distance_km)                                    AS avg_distance_km,
       100 * AVG(HOUR(start_time) < 6)                     AS `pct_00-06`,
       100 * AVG(HOUR(start_time) >= 6  AND HOUR(start_time) < 12) AS `pct_06-12`,
       100 * AVG(HOUR(start_time) >= 12 AND HOUR(start_time) < 18) AS `pct_12-18`,
       100 * AVG(HOUR(start_time) >= 18)                   AS `pct_18-24`
FROM trip
GROUP BY call_type
ORDER BY call_type
""");
""" output:
    shape: (3, 8)
    ┌───────────┬─────────┬──────────────┬─────────────┬───────────┬───────────┬───────────┬───────────┐
    │ call_type ┆ n_trips ┆ avg_duration ┆ avg_distanc ┆ pct_00-06 ┆ pct_06-12 ┆ pct_12-18 ┆ pct_18-24 │
    │ ---       ┆ ---     ┆ _min         ┆ e_km        ┆ ---       ┆ ---       ┆ ---       ┆ ---       │
    │ str       ┆ i64     ┆ ---          ┆ ---         ┆ f64       ┆ f64       ┆ f64       ┆ f64       │
    │           ┆         ┆ f64          ┆ f64         ┆           ┆           ┆           ┆           │
    ╞═══════════╪═════════╪══════════════╪═════════════╪═══════════╪═══════════╪═══════════╪═══════════╡
    │ A         ┆ 364765  ┆ 12.52        ┆ 5.40        ┆ 12.04     ┆ 31.79     ┆ 32.58     ┆ 23.59     │
    │ B         ┆ 817863  ┆ 11.11        ┆ 5.06        ┆ 13.02     ┆ 27.76     ┆ 34.53     ┆ 24.69     │
    │ C         ┆ 527883  ┆ 12.96        ┆ 6.33        ┆ 30.97     ┆ 24.50     ┆ 24.42     ┆ 20.11     │
    └───────────┴─────────┴──────────────┴─────────────┴───────────┴───────────┴───────────┴───────────┘
"""

# %%
# Q5: Find the taxis with the most total hours driven as well as total distance driven.
# List them in order of total hours.
# SUM skips NULLs, so trips with missing data or no GPS points add nothing.
# known_trips shows how many of the taxi's trips actually counted towards the totals.
run("""
SELECT taxi_id,
       SUM(duration_s) / 3600 AS total_hours,
       SUM(distance_km)       AS total_km,
       COUNT(*)               AS n_trips,
       COUNT(duration_s)      AS known_trips
FROM trip
GROUP BY taxi_id
ORDER BY total_hours DESC
LIMIT 20
""");
""" output:
    shape: (20, 5)
    ┌──────────┬─────────────┬──────────┬─────────┬─────────────┐
    │ taxi_id  ┆ total_hours ┆ total_km ┆ n_trips ┆ known_trips │
    │ ---      ┆ ---         ┆ ---      ┆ ---     ┆ ---         │
    │ i64      ┆ f64         ┆ f64      ┆ i64     ┆ i64         │
    ╞══════════╪═════════════╪══════════╪═════════╪═════════════╡
    │ 20000904 ┆ 1959.90     ┆ 62646.17 ┆ 5037    ┆ 5016        │
    │ 20000129 ┆ 1649.46     ┆ 36534.29 ┆ 7607    ┆ 7591        │
    │ 20000307 ┆ 1587.10     ┆ 40016.55 ┆ 7496    ┆ 7480        │
    │ 20000529 ┆ 1507.30     ┆ 42389.15 ┆ 6937    ┆ 6931        │
    │ 20000276 ┆ 1419.88     ┆ 47078.20 ┆ 5908    ┆ 5848        │
    │ 20000436 ┆ 1410.69     ┆ 44299.74 ┆ 5561    ┆ 5552        │
    │ 20000483 ┆ 1397.71     ┆ 36174.84 ┆ 7729    ┆ 7711        │
    │ 20000372 ┆ 1387.13     ┆ 40687.94 ┆ 6535    ┆ 6515        │
    │ 20000616 ┆ 1349.14     ┆ 35407.61 ┆ 6924    ┆ 6915        │
    │ 20000179 ┆ 1324.29     ┆ 39841.17 ┆ 6430    ┆ 6424        │
    │ 20000574 ┆ 1301.92     ┆ 37556.28 ┆ 5929    ┆ 5895        │
    │ 20000235 ┆ 1287.88     ┆ 36729.59 ┆ 6410    ┆ 6404        │
    │ 20000621 ┆ 1282.43     ┆ 31987.93 ┆ 7276    ┆ 7276        │
    │ 20000364 ┆ 1280.50     ┆ 41602.18 ┆ 7821    ┆ 7813        │
    │ 20000435 ┆ 1277.47     ┆ 40991.78 ┆ 5887    ┆ 5877        │
    │ 20000199 ┆ 1270.79     ┆ 39565.22 ┆ 6193    ┆ 6179        │
    │ 20000446 ┆ 1266.63     ┆ 35163.69 ┆ 5300    ┆ 5296        │
    │ 20000011 ┆ 1266.12     ┆ 38498.32 ┆ 5963    ┆ 5955        │
    │ 20000395 ┆ 1263.80     ┆ 34208.19 ┆ 5519    ┆ 5507        │
    │ 20000492 ┆ 1262.57     ┆ 33193.58 ┆ 7171    ┆ 7158        │
    └──────────┴─────────────┴──────────┴─────────┴─────────────┘
"""

# %%
# Q6: Find the trips that passed within 100 m of Porto City Hall.
# (longitude, latitude) = (-8.62911, 41.15794)
# Checking the distance for all 83M points is slow, so first fetch only the points inside a small
# box around City Hall (uses the (lat, lon) index), then check the exact distance with haversine.
# 1 degree latitude is ~111.32 km; 1 degree longitude is ~111.32 km * cos(latitude).
CITY_HALL = (41.15794, -8.62911)   # (lat, lon), the order haversine expects
RADIUS_M = 100

lat_pad = RADIUS_M / 111_320 * 1.1      # 10% margin so no point on the edge is missed
lon_pad = RADIUS_M / (111_320 * math.cos(math.radians(CITY_HALL[0]))) * 1.1

candidates = run("""
SELECT trip_id, lat, lon
FROM gps_point
WHERE lat BETWEEN %s AND %s
  AND lon BETWEEN %s AND %s
""", (CITY_HALL[0] - lat_pad, CITY_HALL[0] + lat_pad,
      CITY_HALL[1] - lon_pad, CITY_HALL[1] + lon_pad), show=False)

dist_m = [haversine(p, CITY_HALL, unit=Unit.METERS) for p in candidates.select("lat", "lon").iter_rows()]
near = candidates.with_columns(pl.Series("dist_m", dist_m)).filter(pl.col("dist_m") <= RADIUS_M)

# One row per trip, with how many of its points were within 100 m and how close it got
near_city_hall = (near.group_by("trip_id")
                  .agg(pl.len().alias("points_within_100m"), pl.col("dist_m").min().alias("closest_m"))
                  .sort("trip_id"))

print(len(candidates), "points in the box,", len(near), "within", RADIUS_M, "m")
print(len(near_city_hall), "trips passed within", RADIUS_M, "m of City Hall")
print(near_city_hall)
""" output:
    836121 points in the box, 310120 within 100 m
    126532 trips passed within 100 m of City Hall
    shape: (126_532, 3)
    ┌─────────────────────┬────────────────────┬───────────┐
    │ trip_id             ┆ points_within_100m ┆ closest_m │
    │ ---                 ┆ ---                ┆ ---       │
    │ i64                 ┆ u32                ┆ f64       │
    ╞═════════════════════╪════════════════════╪═══════════╡
    │ 1372636896620000360 ┆ 1                  ┆ 95.64     │
    │ 1372636956620000167 ┆ 2                  ┆ 84.92     │
    │ 1372637423620000341 ┆ 2                  ┆ 96.45     │
    │ 1372637610620000497 ┆ 4                  ┆ 91.76     │
    │ 1372637721620000678 ┆ 19                 ┆ 73.92     │
    │ 1372638361620000154 ┆ 1                  ┆ 98.20     │
    │ 1372638851620000406 ┆ 1                  ┆ 95.91     │
    │ 1372639364620000015 ┆ 4                  ┆ 67.66     │
    │ 1372639441620000012 ┆ 2                  ┆ 80.25     │
    │ 1372640338620000423 ┆ 1                  ┆ 93.02     │
    │ 1372641197620000653 ┆ 2                  ┆ 82.86     │
    │ 1372641991620000231 ┆ 1                  ┆ 80.37     │
    │ 1372642071620000305 ┆ 1                  ┆ 97.12     │
    │ …                   ┆ …                  ┆ …         │
    │ 1404166023620000621 ┆ 1                  ┆ 97.86     │
    │ 1404166470620000184 ┆ 2                  ┆ 99.01     │
    │ 1404166692620000570 ┆ 2                  ┆ 91.92     │
    │ 1404167893620000311 ┆ 4                  ┆ 82.24     │
    │ 1404167911620000467 ┆ 3                  ┆ 82.80     │
    │ 1404167921620000338 ┆ 3                  ┆ 91.18     │
    │ 1404169221620000456 ┆ 1                  ┆ 98.92     │
    │ 1404169709620000392 ┆ 1                  ┆ 87.02     │
    │ 1404169777620000548 ┆ 1                  ┆ 73.47     │
    │ 1404169808620000009 ┆ 1                  ┆ 96.21     │
    │ 1404170795620000242 ┆ 2                  ┆ 97.41     │
    │ 1404170956620000678 ┆ 1                  ┆ 92.73     │
    └─────────────────────┴────────────────────┴───────────┘
"""

# %%
# Q7: Identify the number of invalid trips. An invalid trip is defined as a trip with fewer
# than 3 GPS points.
run("""
SELECT COUNT(*) AS invalid_trips,
       100 * COUNT(*) / (SELECT COUNT(*) FROM trip) AS pct_of_all_trips
FROM trip
WHERE n_points < 3
""");

# Breakdown by point count, since 0 points (empty polyline) is a different case from 1-2 points
run("""
SELECT n_points, COUNT(*) AS n_trips
FROM trip
WHERE n_points < 3
GROUP BY n_points
ORDER BY n_points
""");
""" output:
    shape: (1, 2)
    ┌───────────────┬──────────────────┐
    │ invalid_trips ┆ pct_of_all_trips │
    │ ---           ┆ ---              │
    │ i64           ┆ f64              │
    ╞═══════════════╪══════════════════╡
    │ 43800         ┆ 2.56             │
    └───────────────┴──────────────────┘
    shape: (3, 2)
    ┌──────────┬─────────┐
    │ n_points ┆ n_trips │
    │ ---      ┆ ---     │
    │ i64      ┆ i64     │
    ╞══════════╪═════════╡
    │ 0        ┆ 5894    │
    │ 1        ┆ 30523   │
    │ 2        ┆ 7383    │
    └──────────┴─────────┘
"""

# %%
# Q8: Find the trips that started on one calendar day and ended on the next (midnight crossers).
# DATEDIFF only compares the dates, so 23:59 -> 00:01 counts as 1 day.
# Trips with unknown end_time (missing data, empty polyline) can't be checked and are left out.
run("""
SELECT COUNT(*) AS midnight_crossers
FROM trip
WHERE DATEDIFF(end_time, start_time) = 1
""");

# TODO: fjerne denne?
run("""
SELECT trip_id, taxi_id, start_time, end_time, duration_s / 60 AS duration_min
FROM trip
WHERE DATEDIFF(end_time, start_time) = 1
ORDER BY start_time
LIMIT 20
""");
""" output:
    shape: (1, 1)
    ┌───────────────────┐
    │ midnight_crossers │
    │ ---               │
    │ i64               │
    ╞═══════════════════╡
    │ 8029              │
    └───────────────────┘
    shape: (20, 5)
    ┌─────────────────────┬──────────┬─────────────────────┬─────────────────────┬──────────────┐
    │ trip_id             ┆ taxi_id  ┆ start_time          ┆ end_time            ┆ duration_min │
    │ ---                 ┆ ---      ┆ ---                 ┆ ---                 ┆ ---          │
    │ i64                 ┆ i64      ┆ datetime[μs]        ┆ datetime[μs]        ┆ f64          │
    ╞═════════════════════╪══════════╪═════════════════════╪═════════════════════╪══════════════╡
    │ 1372717190620000388 ┆ 20000388 ┆ 2013-07-01 23:19:50 ┆ 2013-07-02 00:04:35 ┆ 44.75        │
    │ 1372718162620000560 ┆ 20000560 ┆ 2013-07-01 23:36:02 ┆ 2013-07-02 00:02:02 ┆ 26.00        │
    │ 1372718798620000370 ┆ 20000370 ┆ 2013-07-01 23:46:38 ┆ 2013-07-02 00:01:53 ┆ 15.25        │
    │ 1372719050620000596 ┆ 20000596 ┆ 2013-07-01 23:50:50 ┆ 2013-07-02 00:05:35 ┆ 14.75        │
    │ 1372719093620000022 ┆ 20000022 ┆ 2013-07-01 23:51:33 ┆ 2013-07-02 00:02:03 ┆ 10.50        │
    │ 1372719098620000509 ┆ 20000509 ┆ 2013-07-01 23:51:38 ┆ 2013-07-02 00:01:38 ┆ 10.00        │
    │ 1372719157620000632 ┆ 20000632 ┆ 2013-07-01 23:52:37 ┆ 2013-07-02 00:00:37 ┆ 8.00         │
    │ 1372719200620000031 ┆ 20000031 ┆ 2013-07-01 23:53:20 ┆ 2013-07-02 00:06:35 ┆ 13.25        │
    │ 1372719230620000406 ┆ 20000406 ┆ 2013-07-01 23:53:50 ┆ 2013-07-02 00:08:20 ┆ 14.50        │
    │ 1372719271620000503 ┆ 20000503 ┆ 2013-07-01 23:54:31 ┆ 2013-07-02 00:03:01 ┆ 8.50         │
    │ 1372719315620000008 ┆ 20000008 ┆ 2013-07-01 23:55:15 ┆ 2013-07-02 00:05:15 ┆ 10.00        │
    │ 1372719317620000101 ┆ 20000101 ┆ 2013-07-01 23:55:17 ┆ 2013-07-02 00:12:17 ┆ 17.00        │
    │ 1372719396620000304 ┆ 20000304 ┆ 2013-07-01 23:56:36 ┆ 2013-07-02 00:13:36 ┆ 17.00        │
    │ 1372719469620000409 ┆ 20000409 ┆ 2013-07-01 23:57:49 ┆ 2013-07-02 00:02:19 ┆ 4.50         │
    │ 1372804573620000665 ┆ 20000665 ┆ 2013-07-02 23:36:13 ┆ 2013-07-03 00:36:43 ┆ 60.50        │
    │ 1372805001620000007 ┆ 20000007 ┆ 2013-07-02 23:43:21 ┆ 2013-07-03 00:08:21 ┆ 25.00        │
    │ 1372805426620000514 ┆ 20000514 ┆ 2013-07-02 23:50:26 ┆ 2013-07-03 00:05:11 ┆ 14.75        │
    │ 1372805441620000472 ┆ 20000472 ┆ 2013-07-02 23:50:41 ┆ 2013-07-03 00:13:56 ┆ 23.25        │
    │ 1372805454620000307 ┆ 20000307 ┆ 2013-07-02 23:50:54 ┆ 2013-07-03 00:00:24 ┆ 9.50         │
    │ 1372805480620000671 ┆ 20000671 ┆ 2013-07-02 23:51:20 ┆ 2013-07-03 00:15:05 ┆ 23.75        │
    └─────────────────────┴──────────┴─────────────────────┴─────────────────────┴──────────────┘
"""

# %%
# Q9: Find the trips whose start and end points are within 50 m of each other (circular trips).
# Invalid trips (< 3 points, see Q7) are left out: with 1 point start and end are the same point,
# which would make every such trip "circular".
trips = run("""
SELECT trip_id, start_lat, start_lon, end_lat, end_lon
FROM trip
WHERE n_points >= 3
""", show=False)

dist_m = haversine_vector(trips.select("start_lat", "start_lon").to_numpy(),
                          trips.select("end_lat", "end_lon").to_numpy(), Unit.METERS)
circular = (trips.with_columns(pl.Series("start_end_dist_m", dist_m))
            .filter(pl.col("start_end_dist_m") <= 50)
            .select("trip_id", "start_end_dist_m"))

print(len(circular), "circular trips of", len(trips), "valid trips")
print(circular)
""" output:
    21460 circular trips of 1666711 valid trips
    shape: (21_460, 2)
    ┌─────────────────────┬──────────────────┐
    │ trip_id             ┆ start_end_dist_m │
    │ ---                 ┆ ---              │
    │ i64                 ┆ f64              │
    ╞═════════════════════╪══════════════════╡
    │ 1372638303620000112 ┆ 2.47             │
    │ 1372639092620000233 ┆ 8.77             │
    │ 1372644642620000305 ┆ 40.94            │
    │ 1372650711620000403 ┆ 6.73             │
    │ 1372650908620000403 ┆ 2.26             │
    │ 1372661911620000496 ┆ 10.98            │
    │ 1372662261620000031 ┆ 2.51             │
    │ 1372663272620000206 ┆ 12.97            │
    │ 1372664679620000186 ┆ 13.77            │
    │ 1372664787620000397 ┆ 17.79            │
    │ 1372665027620000574 ┆ 23.01            │
    │ 1372667532620000443 ┆ 4.27             │
    │ 1372667871620000152 ┆ 18.52            │
    │ …                   ┆ …                │
    │ 1404154110620000499 ┆ 31.20            │
    │ 1404154570620000013 ┆ 7.23             │
    │ 1404154602620000334 ┆ 32.10            │
    │ 1404154744620000902 ┆ 12.70            │
    │ 1404155788620000255 ┆ 2.14             │
    │ 1404158633620000370 ┆ 11.52            │
    │ 1404159631620000252 ┆ 9.29             │
    │ 1404162871620000216 ┆ 2.47             │
    │ 1404162993620000207 ┆ 17.59            │
    │ 1404164870620000503 ┆ 7.83             │
    │ 1404166379620000525 ┆ 4.82             │
    │ 1404166606620000624 ┆ 6.42             │
    └─────────────────────┴──────────────────┘
"""

# %%
# Q10: For each taxi, compute the average idle time between consecutive trips. List the top 20 taxis
# with the highest average idle time.
# Idle time = next trip's start_time - this trip's end_time, with trips ordered by start_time per taxi.
# Gaps after a trip with unknown end_time are NULL and skipped by AVG.
# Negative gaps (next trip starts before this one ends) are overlapping trips, a data error, so skipped.
run("""
WITH gaps AS (
    SELECT taxi_id,
           TIMESTAMPDIFF(SECOND, end_time,
                         LEAD(start_time) OVER (PARTITION BY taxi_id ORDER BY start_time)) AS idle_s
    FROM trip
)
SELECT taxi_id,
       AVG(idle_s) / 3600 AS avg_idle_hours,
       COUNT(*)           AS n_gaps
FROM gaps
WHERE idle_s >= 0
GROUP BY taxi_id
ORDER BY avg_idle_hours DESC
LIMIT 20
""");
""" output:
    shape: (20, 3)
    ┌──────────┬────────────────┬────────┐
    │ taxi_id  ┆ avg_idle_hours ┆ n_gaps │
    │ ---      ┆ ---            ┆ ---    │
    │ i64      ┆ f64            ┆ i64    │
    ╞══════════╪════════════════╪════════╡
    │ 20000980 ┆ 426.41         ┆ 4      │
    │ 20000941 ┆ 91.69          ┆ 5      │
    │ 20000969 ┆ 86.16          ┆ 47     │
    │ 20000312 ┆ 13.04          ┆ 583    │
    │ 20000510 ┆ 11.87          ┆ 674    │
    │ 20000609 ┆ 11.39          ┆ 577    │
    │ 20000579 ┆ 11.15          ┆ 758    │
    │ 20000079 ┆ 10.52          ┆ 101    │
    │ 20000185 ┆ 8.89           ┆ 671    │
    │ 20000449 ┆ 8.64           ┆ 977    │
    │ 20000902 ┆ 7.39           ┆ 1058   │
    │ 20000072 ┆ 6.98           ┆ 952    │
    │ 20000535 ┆ 6.59           ┆ 1284   │
    │ 20000315 ┆ 6.29           ┆ 1327   │
    │ 20000071 ┆ 6.22           ┆ 1361   │
    │ 20000225 ┆ 5.91           ┆ 1427   │
    │ 20000545 ┆ 5.86           ┆ 1255   │
    │ 20000407 ┆ 5.57           ┆ 1456   │
    │ 20000205 ┆ 5.38           ┆ 1335   │
    │ 20000443 ┆ 5.38           ┆ 1562   │
    └──────────┴────────────────┴────────┘
"""