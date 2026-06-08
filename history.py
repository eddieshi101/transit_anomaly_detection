import sqlite3
import pandas as pd
from datetime import datetime, timezone

DB_PATH = "data/history.db"


def init_db():
    """
    Creates the database and tables if they don't exist yet.
    Safe to call every pipeline run — it won't overwrite existing data.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # stores one row per vehicle per pipeline run
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicle_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          TEXT NOT NULL,
            vehicle_id      TEXT NOT NULL,
            line_id         TEXT NOT NULL,
            anomaly_score   INTEGER NOT NULL,
            was_flagged     INTEGER NOT NULL,  -- 1 if anomaly_score >= 1, else 0
            minutes_to_station REAL,
            delay_vs_average   REAL,
            ingested_at     TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def save_run(df: pd.DataFrame, run_id: str):
    """
    Saves the current pipeline run to the database.
    Called after detection so we have anomaly scores to store.
    """
    conn = sqlite3.connect(DB_PATH)

    rows = []
    for _, row in df.iterrows():
        rows.append({
            "run_id":             run_id,
            "vehicle_id":         row["vehicle_id"],
            "line_id":            row["line_id"],
            "anomaly_score":      int(row["anomaly_score"]),
            "was_flagged":        1 if row["anomaly_score"] >= 1 else 0,
            "minutes_to_station": row.get("minutes_to_station"),
            "delay_vs_average":   row.get("delay_vs_average"),
            "ingested_at":        str(row["ingested_at"]),
        })

    runs_df = pd.DataFrame(rows)
    runs_df.to_sql("vehicle_runs", conn, if_exists="append", index=False)

    conn.close()
    print(f"Saved {len(rows)} records to history (run_id: {run_id})")


def load_vehicle_history(line_id: str, last_n_runs: int = 7) -> pd.DataFrame:
    """
    Loads the last N run IDs for this line, then returns all vehicle
    records from those runs. This is what we use to compute historical features.
    """
    conn = sqlite3.connect(DB_PATH)

    # get the most recent N distinct run IDs for this line
    recent_runs_query = """
        SELECT DISTINCT run_id
        FROM vehicle_runs
        WHERE line_id = ?
        ORDER BY ingested_at DESC
        LIMIT ?
    """
    recent_runs = pd.read_sql(recent_runs_query, conn, params=(line_id, last_n_runs))

    if recent_runs.empty:
        conn.close()
        return pd.DataFrame()

    # get all records from those runs
    run_ids = tuple(recent_runs["run_id"].tolist())
    placeholders = ",".join("?" * len(run_ids))
    history_query = f"""
        SELECT *
        FROM vehicle_runs
        WHERE run_id IN ({placeholders})
    """
    history = pd.read_sql(history_query, conn, params=run_ids)

    conn.close()
    return history


def compute_historical_features(current_df: pd.DataFrame, line_id: str) -> pd.DataFrame:
    """
    Looks up each vehicle's history and adds historical features
    to the current dataframe.

    New columns added:
    - times_flagged_last_7_runs  : how many recent runs this vehicle was anomalous
    - total_runs_seen            : how many total runs this vehicle has appeared in
    - avg_delay_historical       : average minutes_to_station across historical runs
    - is_historically_late       : True if flagged in more than half of recent runs
    """
    history = load_vehicle_history(line_id, last_n_runs=7)

    if history.empty:
        # first ever run — no history yet, fill with defaults
        current_df["times_flagged_last_7_runs"] = 0
        current_df["total_runs_seen"]           = 0
        current_df["avg_delay_historical"]      = None
        current_df["is_historically_late"]      = False
        return current_df

    # compute per-vehicle stats from history
    stats = history.groupby("vehicle_id").agg(
        times_flagged_last_7_runs = ("was_flagged", "sum"),
        total_runs_seen           = ("run_id", "nunique"),
        avg_delay_historical      = ("minutes_to_station", "mean"),
    ).reset_index()

    stats["avg_delay_historical"] = stats["avg_delay_historical"].round(1)

    # a vehicle is historically late if it was flagged in more than
    # half of the runs it appeared in
    stats["is_historically_late"] = (
        stats["times_flagged_last_7_runs"] / stats["total_runs_seen"] > 0.5
    )

    # merge historical stats onto the current run's dataframe
    current_df = current_df.merge(stats, on="vehicle_id", how="left")

    # fill in zeros for vehicles we've never seen before
    current_df["times_flagged_last_7_runs"] = current_df["times_flagged_last_7_runs"].fillna(0).astype(int)
    current_df["total_runs_seen"]           = current_df["total_runs_seen"].fillna(0).astype(int)
    current_df["is_historically_late"]      = current_df["is_historically_late"].fillna(False)

    return current_df
