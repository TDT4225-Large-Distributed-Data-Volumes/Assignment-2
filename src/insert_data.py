# %%
import json
import time

import pandas as pd

from create_tables import create_tables, drop_tables
from local_db import get_connection

CSV = "porto/porto_clean.csv"
CHUNK_SIZE = 10_000     # trips read from the csv at a time
POINT_BATCH = 50_000    # gps points per INSERT, keeps each packet well under max_allowed_packet

TRIP_COLS = ["TRIP_ID", "TAXI_ID", "CALL_TYPE", "ORIGIN_CALL", "ORIGIN_STAND", "MISSING_DATA",
             "start_time", "end_time", "n_points", "distance_km", "max_speed", "is_flagged",
             "start_lon", "start_lat", "end_lon", "end_lat"]

INSERT_TAXI = "INSERT INTO taxi (taxi_id) VALUES (%s)"
INSERT_TRIP = """
INSERT INTO trip (trip_id, taxi_id, call_type, origin_call, origin_stand, missing_data,
                  start_time, end_time, n_points, distance_km, max_speed, is_flagged,
                  start_lon, start_lat, end_lon, end_lat)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""
INSERT_POINT = "INSERT INTO gps_point (trip_id, point_idx, lon, lat) VALUES (%s, %s, %s, %s)"

# Indexes for the part 2 queries. Built after the load, since that is much faster than
# updating them for every inserted row.
INDEXES = [
    "CREATE INDEX idx_trip_start_time ON trip (start_time)",
    "CREATE INDEX idx_point_lat_lon ON gps_point (lat, lon)",
]

# Nullable integer columns as pandas' Int types, so they come out as python ints / NA, not floats
DTYPES = {"ORIGIN_CALL": "Int64", "ORIGIN_STAND": "Int64", "MISSING_DATA": "Int8",
          "is_flagged": "Int8", "start_time": str, "end_time": str}


def to_rows(df, cols):
    # .tolist() gives native python types (the connector can't handle numpy types),
    # and NaN/NA becomes None, which is NULL in MySQL
    columns = [df[c].tolist() for c in cols]
    return [tuple(None if pd.isna(v) else v for v in row) for row in zip(*columns)]


def point_rows(df):
    # One row per [lon, lat] in POLYLINE, with its position in the trip
    for trip_id, polyline in zip(df["TRIP_ID"].tolist(), df["POLYLINE"].tolist()):
        for idx, (lon, lat) in enumerate(json.loads(polyline)):
            yield (trip_id, idx, lon, lat)


def insert_points(cursor, df):
    batch = []
    for row in point_rows(df):
        batch.append(row)
        if len(batch) == POINT_BATCH:
            cursor.executemany(INSERT_POINT, batch)
            batch = []
    if batch:
        cursor.executemany(INSERT_POINT, batch)


# %%
if __name__ == "__main__":
    connection = get_connection()
    cursor = connection.cursor()

    # 1. Fresh tables
    drop_tables(cursor)
    create_tables(cursor)

    # Skip per-row foreign key and unique checks during the bulk load. The data is already
    # deduplicated and every trip's taxi is inserted first, so the constraints still hold.
    cursor.execute("SET foreign_key_checks = 0")
    cursor.execute("SET unique_checks = 0")

    # 2. Taxis. Only the TAXI_ID column is needed, so this read is quick.
    taxi_ids = pd.read_csv(CSV, usecols=["TAXI_ID"])["TAXI_ID"].unique()
    cursor.executemany(INSERT_TAXI, [(int(t),) for t in taxi_ids])
    connection.commit()
    print(len(taxi_ids), "taxis inserted")

    # 3. Trips and their GPS points, a chunk of trips at a time so the whole file never sits in memory
    start = time.time()
    n_trips = 0
    for chunk in pd.read_csv(CSV, dtype=DTYPES, chunksize=CHUNK_SIZE):
        cursor.executemany(INSERT_TRIP, to_rows(chunk, TRIP_COLS))
        insert_points(cursor, chunk)
        connection.commit()
        n_trips += len(chunk)
        print(f"{n_trips} trips inserted ({time.time() - start:.0f}s)")

    cursor.execute("SET foreign_key_checks = 1")
    cursor.execute("SET unique_checks = 1")

    # 4. Indexes
    for query in INDEXES:
        print(query)
        cursor.execute(query)

    # 5. Sanity check against the csv
    for table in ["taxi", "trip", "gps_point"]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        print(table, cursor.fetchone()[0])

    cursor.close()
    connection.close()
