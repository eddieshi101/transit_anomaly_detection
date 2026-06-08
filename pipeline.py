import requests
import pandas as pd
import json
from datetime import datetime,timezone

APP_KEY = "your_api_key"  # paste your TfL key here

def fetch_vehicle_positions(line_id: str) -> list[dict]:
    """
    Fetches live vehicle positions for a given TfL bus line.
    Returns a list of raw vehicle records.
    """
    url = f"https://api.tfl.gov.uk/Line/{line_id}/Arrivals"
    params = {"app_key": APP_KEY}
    
    response = requests.get(url, params=params)
    response.raise_for_status()  # raises an error if the request failed
    
    return response.json()


def raw_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    Takes raw API records and pulls out the fields we care about.
    This is your first transformation step.
    """
    if not records:
        return pd.DataFrame()
    
    rows = []
    for r in records:
        rows.append({
            "vehicle_id":        r.get("vehicleId"),
            "line_id":           r.get("lineId"),
            "direction":         r.get("direction"),
            "station_name":      r.get("stationName"),
            "destination":       r.get("destinationName"),
            "time_to_station":   r.get("timeToStation"),   # seconds until arrival
            "expected_arrival":  r.get("expectedArrival"),
            "ingested_at":       datetime.now(timezone.utc).isoformat()
        })
    
    return pd.DataFrame(rows)


def save_raw(df: pd.DataFrame, line_id: str):
    """Saves the raw dataframe to the data/ folder."""
    path = f"data/raw_{line_id}.csv"
    df.to_csv(path, index=False)
    print(f"Saved {len(df)} records to {path}")


if __name__ == "__main__":
    from features import engineer_features
    from detect import run_detection, get_anomalies
    from validate import run_validation, print_validation_report, generate_output_report
    from history import init_db, save_run, compute_historical_features

    line_id = "central"
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # initialise database on first run, no-op on subsequent runs
    init_db()

    print(f"Fetching vehicles for line: {line_id}")
    raw = fetch_vehicle_positions(line_id)
    print(f"Got {len(raw)} records from API")

    df = raw_to_dataframe(raw)

    # validate before doing anything else
    validation = run_validation(df)
    print_validation_report(validation)
    if not validation["passed"]:
        print("Pipeline halted due to validation failures.")
        exit(1)

    # feature engineering
    df = engineer_features(df)

    # add historical features before detection
    df = compute_historical_features(df, line_id)

    # detection
    df = run_detection(df)
    anomalies = get_anomalies(df, min_score=1)

    print("Top anomalies:")
    print(anomalies[[
        "vehicle_id", "station_name", "minutes_to_station",
        "delay_category", "anomaly_score",
        "times_flagged_last_7_runs", "is_historically_late"
    ]].head(10).to_string(index=False))

    # save this run to history AFTER detection so scores are included
    save_run(df, run_id)

    generate_output_report(df, anomalies, line_id)
