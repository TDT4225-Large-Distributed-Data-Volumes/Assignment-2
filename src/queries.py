# %%
import math

import numpy as np
from haversine import Unit, haversine, haversine_vector
from tabulate import tabulate

from local_db import get_connection

connection = get_connection()
cursor = connection.cursor()


def run(query, params=None):
    # Runs a query, prints the result as a table and returns the rows
    cursor.execute(query, params)
    rows = cursor.fetchall()
    print(tabulate(rows, headers=cursor.column_names, floatfmt=".2f"))
    return rows


# %%
# Q1: How many taxis, trips, and total GPS points are there?
run("""
SELECT
    (SELECT COUNT(*) FROM taxi)      AS taxis,
    (SELECT COUNT(*) FROM trip)      AS trips,
    (SELECT COUNT(*) FROM gps_point) AS gps_points
""")

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
""")

# %%
# Q3: List the top 20 taxis with the most trips.
run("""
SELECT taxi_id, COUNT(*) AS n_trips
FROM trip
GROUP BY taxi_id
ORDER BY n_trips DESC
LIMIT 20
""")

# %%
# Q4a: What is the most used call type per taxi?
# Count trips per (taxi, call type) and rank the call types within each taxi.
# RANK gives ties the same rank, so a taxi with a tie shows up once per tied call type.
rows = run("""
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
summary = {}
for _, call_type, _ in rows:
    summary[call_type] = summary.get(call_type, 0) + 1
print(tabulate(sorted(summary.items()), headers=["most_used_call_type", "n_taxis"]))

# %%
# Q4b: For each call type, the average trip duration and distance, and the share of trips
# starting in each time band. AVG skips NULLs, so trips with missing data or no GPS points
# only count towards the time band shares. start_time is Porto local time.
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
""")

# %%
# Q5: The taxis with the most total hours driven, with their total distance, in order of hours.
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
""")

# %%
# Q6: Find the trips that passed within 100 m of Porto City Hall.
# Checking the distance for all 83M points is slow, so first fetch only the points inside a small
# box around City Hall (uses the (lat, lon) index), then check the exact distance with haversine.
# 1 degree latitude is ~111.32 km; 1 degree longitude is ~111.32 km * cos(latitude).
CITY_HALL = (41.15794, -8.62911)   # (lat, lon), the order haversine expects
RADIUS_M = 100

lat_pad = RADIUS_M / 111_320 * 1.1      # 10% margin so no point on the edge is missed
lon_pad = RADIUS_M / (111_320 * math.cos(math.radians(CITY_HALL[0]))) * 1.1

cursor.execute("""
SELECT trip_id, lat, lon
FROM gps_point
WHERE lat BETWEEN %s AND %s
  AND lon BETWEEN %s AND %s
""", (CITY_HALL[0] - lat_pad, CITY_HALL[0] + lat_pad,
      CITY_HALL[1] - lon_pad, CITY_HALL[1] + lon_pad))
candidates = cursor.fetchall()

# trip_id -> number of its points within 100 m
near_city_hall = {}
for trip_id, lat, lon in candidates:
    if haversine((lat, lon), CITY_HALL, unit=Unit.METERS) <= RADIUS_M:
        near_city_hall[trip_id] = near_city_hall.get(trip_id, 0) + 1

print(len(candidates), "points in the box,", sum(near_city_hall.values()), "within", RADIUS_M, "m")
print(len(near_city_hall), "trips passed within", RADIUS_M, "m of City Hall")
print(tabulate(sorted(near_city_hall.items())[:20], headers=["trip_id", "points_within_100m"]))

# %%
# Q7: Number of invalid trips, i.e. trips with fewer than 3 GPS points.
run("""
SELECT COUNT(*) AS invalid_trips,
       100 * COUNT(*) / (SELECT COUNT(*) FROM trip) AS pct_of_all_trips
FROM trip
WHERE n_points < 3
""")

# Breakdown by point count, since 0 points (empty polyline) is a different case from 1-2 points
run("""
SELECT n_points, COUNT(*) AS n_trips
FROM trip
WHERE n_points < 3
GROUP BY n_points
ORDER BY n_points
""")

# %%
# Q8: Trips that started on one calendar day and ended on the next (midnight crossers).
# DATEDIFF only compares the dates, so 23:59 -> 00:01 counts as 1 day.
# Trips with unknown end_time (missing data, empty polyline) can't be checked and are left out.
run("""
SELECT COUNT(*) AS midnight_crossers
FROM trip
WHERE DATEDIFF(end_time, start_time) = 1
""")

run("""
SELECT trip_id, taxi_id, start_time, end_time, duration_s / 60 AS duration_min
FROM trip
WHERE DATEDIFF(end_time, start_time) = 1
ORDER BY start_time
LIMIT 20
""")

# %%
# Q9: Trips whose start and end points are within 50 m of each other (circular trips).
# Invalid trips (< 3 points, see Q7) are left out: with 1 point start and end are the same point,
# which would make every such trip "circular".
cursor.execute("""
SELECT trip_id, start_lat, start_lon, end_lat, end_lon
FROM trip
WHERE n_points >= 3
""")
trips = cursor.fetchall()

coords = np.array([row[1:] for row in trips])
dist_m = haversine_vector(coords[:, 0:2], coords[:, 2:4], Unit.METERS)

circular = [(trips[i][0], dist_m[i]) for i in np.flatnonzero(dist_m <= 50)]
print(len(circular), "circular trips of", len(trips), "valid trips")
print(tabulate(circular[:20], headers=["trip_id", "start_end_distance_m"], floatfmt=".1f"))

# %%
# Q10: Average idle time between consecutive trips per taxi, top 20.
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
""")
