import pandas as pd
from datetime import datetime, timezone


def parse_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts string timestamps into proper datetime objects.
    Without this, we can't do any time-based math.
    """
    df = df.copy()
    df["expected_arrival"] = pd.to_datetime(df["expected_arrival"], utc=True, errors="coerce")
    df["ingested_at"] = pd.to_datetime(df["ingested_at"], utc=True, errors="coerce")
    return df


def compute_delay_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes delay-related features from raw arrival data.
    
    time_to_station is in seconds — we convert it to minutes
    and bucket it into severity levels.
    """
    df = df.copy()

    # convert seconds to minutes, round to 1 decimal
    df["minutes_to_station"] = (df["time_to_station"] / 60).round(1)

    # how late is this vehicle relative to the line average?
    mean_time = df["minutes_to_station"].mean()
    df["delay_vs_average"] = (df["minutes_to_station"] - mean_time).round(1)

    # bucket into severity: normal / delayed / severe
    def classify_delay(mins):
        if pd.isna(mins):
            return "unknown"
        elif mins <= 2:
            return "imminent"
        elif mins <= 10:
            return "normal"
        elif mins <= 20:
            return "delayed"
        else:
            return "severe"

    df["delay_category"] = df["minutes_to_station"].apply(classify_delay)

    return df


def compute_vehicle_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes per-vehicle features by grouping across all records
    for each vehicle_id.

    This is where we spot vehicles that appear too many times
    (bunching) or have missing direction data (data quality issue).
    """
    df = df.copy()

    # how many arrival predictions exist for each vehicle?
    # a high count means this vehicle is appearing at many stations — possible bunching
    vehicle_counts = df.groupby("vehicle_id").size().rename("vehicle_prediction_count")
    df = df.merge(vehicle_counts, on="vehicle_id", how="left")

    # flag vehicles with no direction — these are data quality issues
    df["missing_direction"] = df["direction"].isna()

    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Master function — runs all feature engineering steps in order.
    This is what the rest of the pipeline will call.
    """
    df = parse_timestamps(df)
    df = compute_delay_features(df)
    df = compute_vehicle_features(df)
    return df

