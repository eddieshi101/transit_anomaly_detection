import pandas as pd


# these are your thresholds — in a real system these would be
# configurable per client, which is exactly what GeoComply does
THRESHOLDS = {
    "severe_delay_minutes": 20,
    "high_delay_vs_average": 10,
    "bunching_prediction_count": 12,
    "missing_direction": True,
}


def flag_severe_delay(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flags vehicles that are severely behind schedule in absolute terms.
    """
    df["flag_severe_delay"] = df["minutes_to_station"] > THRESHOLDS["severe_delay_minutes"]
    return df


def flag_delay_outlier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flags vehicles that are significantly worse than the current line average.
    This catches delays even when the whole line is running slow.
    """
    df["flag_delay_outlier"] = df["delay_vs_average"] > THRESHOLDS["high_delay_vs_average"]
    return df


def flag_bunching(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flags vehicles with an unusually high number of arrival predictions.
    High count = vehicle is appearing at too many stations = bunching.
    """
    df["flag_bunching"] = df["vehicle_prediction_count"] >= THRESHOLDS["bunching_prediction_count"]
    return df


def flag_missing_direction(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flags records with no direction data — these are data quality issues
    that could corrupt downstream aggregations.
    """
    df["flag_missing_direction"] = df["missing_direction"]
    return df


def compute_anomaly_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Combines all flags into a single anomaly score per record.
    Each flag adds 1 point — the higher the score, the more signals
    are firing simultaneously.
    
    This is exactly how risk scoring works at companies like GeoComply:
    multiple weak signals combine into a stronger overall flag.
    """
    flag_cols = [
        "flag_severe_delay",
        "flag_delay_outlier", 
        "flag_bunching",
        "flag_missing_direction",
    ]
    # sum booleans — True counts as 1, False as 0
    df["anomaly_score"] = df[flag_cols].sum(axis=1)
    return df


def run_detection(df: pd.DataFrame) -> pd.DataFrame:
    """
    Master detection function — runs all flags then scores each record.
    Returns the full dataframe with all flag columns and anomaly score added.
    """
    df = flag_severe_delay(df)
    df = flag_delay_outlier(df)
    df = flag_bunching(df)
    df = flag_missing_direction(df)
    df = compute_anomaly_score(df)
    return df


def get_anomalies(df: pd.DataFrame, min_score: int = 1) -> pd.DataFrame:
    """
    Filters down to only the records that triggered at least one flag.
    min_score lets you control sensitivity — set to 2 to only see
    records where multiple signals fired simultaneously.
    """
    anomalies = df[df["anomaly_score"] >= min_score].copy()
    anomalies = anomalies.sort_values("anomaly_score", ascending=False)
    return anomalies