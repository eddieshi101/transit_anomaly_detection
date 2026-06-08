import pandas as pd
from datetime import datetime, timezone


# These are your data quality rules — the pipeline checks these
# before doing any feature engineering. If the data coming in
# looks wrong, you want to know immediately rather than let bad
# data silently corrupt your output.

REQUIRED_COLUMNS = [
    "vehicle_id",
    "line_id", 
    "direction",
    "station_name",
    "time_to_station",
    "expected_arrival",
    "ingested_at",
]


def check_required_columns(df: pd.DataFrame) -> list[str]:
    """
    Returns a list of any required columns that are missing.
    Empty list means the schema looks correct.
    """
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    return missing


def check_null_rates(df: pd.DataFrame, threshold: float = 0.5) -> list[str]:
    """
    Flags any column where more than `threshold` percent of values are null.
    A column that's 80% null usually means something broke upstream.
    """
    flagged = []
    for col in df.columns:
        null_rate = df[col].isna().mean()
        if null_rate > threshold:
            flagged.append(f"{col} ({null_rate:.0%} null)")
    return flagged


def check_time_to_station(df: pd.DataFrame) -> list[str]:
    """
    Checks that time_to_station values make sense.
    Negative values or impossibly large values indicate corrupt data.
    """
    issues = []
    if (df["time_to_station"] < 0).any():
        count = (df["time_to_station"] < 0).sum()
        issues.append(f"{count} records have negative time_to_station")
    if (df["time_to_station"] > 7200).any():
        count = (df["time_to_station"] > 7200).sum()
        issues.append(f"{count} records have time_to_station > 2 hours")
    return issues


def check_record_count(df: pd.DataFrame, min_records: int = 10) -> list[str]:
    """
    Flags if we got suspiciously few records from the API.
    Could mean the API is degraded or the line has no active vehicles.
    """
    if len(df) < min_records:
        return [f"Only {len(df)} records returned — expected at least {min_records}"]
    return []


def run_validation(df: pd.DataFrame) -> dict:
    """
    Runs all validation checks and returns a report dict.
    The pipeline should call this before feature engineering.
    If any critical issues are found, the pipeline should stop.
    """
    issues = {
        "missing_columns":   check_required_columns(df),
        "high_null_columns": check_null_rates(df),
        "time_range_issues": check_time_to_station(df),
        "record_count":      check_record_count(df),
    }
    issues["total_issues"] = sum(len(v) for v in issues.values() if isinstance(v, list))
    issues["passed"] = issues["total_issues"] == 0
    return issues


def print_validation_report(issues: dict):
    print("\n── Validation Report ──────────────────────────")
    if issues["passed"]:
        print("✓ All checks passed")
    else:
        print(f"✗ {issues['total_issues']} issue(s) found:")
        for key, vals in issues.items():
            if isinstance(vals, list) and vals:
                for v in vals:
                    print(f"  [{key}] {v}")
    print("───────────────────────────────────────────────\n")


def generate_output_report(df: pd.DataFrame, anomalies: pd.DataFrame, line_id: str):
    """
    Generates a clean summary CSV of anomalies with a run timestamp.
    This is your pipeline's final output — what a downstream system
    or analyst would actually consume.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = f"data/anomaly_report_{line_id}_{timestamp}.csv"

    report = anomalies[[
        "vehicle_id",
        "line_id",
        "station_name",
        "direction",
        "minutes_to_station",
        "delay_category",
        "delay_vs_average",
        "times_flagged_last_7_runs",
        "total_runs_seen",
        "avg_delay_historical",
        "is_historically_late",
        "anomaly_score",
        "flag_severe_delay",
        "flag_delay_outlier",
        "flag_bunching",
        "flag_missing_direction",
        "flag_historically_late",
        "ingested_at"
    ]].copy()

    report.to_csv(path, index=False)
    print(f"Anomaly report saved to {path}")
    print(f"  Total records processed : {len(df)}")
    print(f"  Anomalies detected      : {len(anomalies)}")
    print(f"  Anomaly rate            : {len(anomalies)/len(df):.1%}")
    return path
