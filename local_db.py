# %%
import os

import mysql.connector as mysql


def get_connection():
    """
    Returns a connection to the local MySQL container started with docker compose.
    Defaults match the Dockerfile; override with DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.
    """
    return mysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "testdb"),
        user=os.getenv("DB_USER", "testuser"),
        password=os.getenv("DB_PASSWORD", "test123"),
    )

# %%
if __name__ == "__main__":
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT VERSION(), DATABASE();")
    print("Connected to MySQL %s, database: %s" % cursor.fetchone())
    cursor.close()
    connection.close()
