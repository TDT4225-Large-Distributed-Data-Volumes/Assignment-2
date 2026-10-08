# %%
from local_db import get_connection

# One row per taxi. Only an id in the dataset, but gives trip.taxi_id something to reference.
CREATE_TAXI = """
CREATE TABLE IF NOT EXISTS taxi (
    taxi_id INT NOT NULL PRIMARY KEY
)
"""

# One row per trip, with the features computed in data_cleaning.py.
# Times are Porto local time (Europe/Lisbon). Columns we couldn't trust are NULL
# (distance/speed/end_time for MISSING_DATA trips, everything GPS-related for empty polylines).
CREATE_TRIP = """
CREATE TABLE IF NOT EXISTS trip (
    trip_id      BIGINT       NOT NULL PRIMARY KEY,
    taxi_id      INT          NOT NULL,
    call_type    CHAR(1)      NOT NULL,
    origin_call  INT          NULL,
    origin_stand SMALLINT     NULL,
    missing_data BOOLEAN      NOT NULL,
    start_time   DATETIME     NOT NULL,
    end_time     DATETIME     NULL,
    duration_s   INT GENERATED ALWAYS AS (IF(end_time IS NULL, NULL, (n_points - 1) * 15)) STORED,
    n_points     INT          NOT NULL,
    distance_km  DOUBLE       NULL,
    max_speed    DOUBLE       NULL,
    is_flagged   BOOLEAN      NULL,
    start_lon    DOUBLE       NULL,
    start_lat    DOUBLE       NULL,
    end_lon      DOUBLE       NULL,
    end_lat      DOUBLE       NULL,
    CONSTRAINT fk_trip_taxi FOREIGN KEY (taxi_id) REFERENCES taxi (taxi_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_call_type CHECK (call_type IN ('A', 'B', 'C'))
)
"""

# One row per GPS point in a trip's POLYLINE. point_idx is the position in the polyline (0-based),
# so the point's time is start_time + point_idx * 15s.
# The composite primary key keeps each trip's points stored together and in order.
CREATE_GPS_POINT = """
CREATE TABLE IF NOT EXISTS gps_point (
    trip_id   BIGINT   NOT NULL,
    point_idx SMALLINT UNSIGNED NOT NULL,
    lon       DOUBLE   NOT NULL,
    lat       DOUBLE   NOT NULL,
    PRIMARY KEY (trip_id, point_idx),
    CONSTRAINT fk_point_trip FOREIGN KEY (trip_id) REFERENCES trip (trip_id)
        ON DELETE CASCADE ON UPDATE CASCADE
)
"""

TABLES = [CREATE_TAXI, CREATE_TRIP, CREATE_GPS_POINT]


def drop_tables(cursor):
    # children first, because of the foreign keys
    for table in ["gps_point", "trip", "taxi"]:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")


def create_tables(cursor):
    for query in TABLES:
        cursor.execute(query)


# %%
if __name__ == "__main__":
    connection = get_connection()
    cursor = connection.cursor()
    drop_tables(cursor)
    create_tables(cursor)
    connection.commit()
    cursor.execute("SHOW TABLES")
    print([row[0] for row in cursor.fetchall()])
    cursor.close()
    connection.close()
