# TDT4225 Assignment 2 – Porto taxi trips in MySQL

Group 106: Amund Mørk, Vetle Hodne

The dataset is not included because it is too large. Place `porto.csv` in a `porto/` folder in the project root:

```
porto/porto.csv
```

## Setup

Requires Docker and Python 3.

```bash
docker compose up -d                # start MySQL on localhost:3306
pip install -r requirements.txt
```

Connection settings are in `src/local_db.py` and match the `Dockerfile`.

## Run

Run all scripts from the project root, in this order:

```bash
python src/data_cleaning.py   # porto/porto.csv -> porto/porto_clean.csv
python src/insert_data.py     # creates the tables and inserts the cleaned data
python src/queries.py         # runs the Part 2 queries
```

`src/insert_data.py` drops and recreates the tables, so it can be rerun.

## Other files

- `src/eda.py` – exploratory data analysis and plots
- `src/plot_trips.py` – plots trip trajectories on a map
- `src/create_tables.py` – the `CREATE TABLE` statements
