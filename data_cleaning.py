#%%
import json
import numpy as np
import pandas as pd
from haversine import haversine_vector, Unit

THRESHOLD = 150   # km/h

df = pd.read_csv("porto/porto.csv", dtype=str, keep_default_na=False)


def has_jump(polyline):
    coords = json.loads(polyline)
    if len(coords) < 2:
        return False
    pts = np.array(coords)[:, ::-1]
    dist = haversine_vector(pts[:-1], pts[1:], Unit.KILOMETERS)
    speed = dist / (15 / 3600)
    return bool((speed > THRESHOLD).any())


df["is_flagged"] = df["POLYLINE"].apply(has_jump)

print(df["is_flagged"].sum(), "flagged trips of", len(df))
df.to_csv("porto/porto_clean.csv", index=False)

# TODO Remove duplicates