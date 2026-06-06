import pytest
import pandas as pd
import numpy as np
from features import (
    parse_timestamps,
    compute_delay_features,
    compute_vehicle_features,
    engineer_features,
)
from detect import (
    run_detection,
    get_anomalies,
    flag_severe_delay,
    flag_bunching,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def make_sample_df():
    """
    Creates a small realistic dataframe we can run tests against.
    Using a fixed dataset means tests are deterministic — they don't
    depend on live API data which changes every run.
    """
    return pd.DataFrame({
        "vehicle_id":      ["A", "A", "B", "C", "C", "C"],
        "line_id":         ["central"] * 6,
        "direction":       ["inbound", "outbound", "inbound", None, "inbound", "outbound"],
        "station_name":    ["St1", "St2", "St3", "St4", "St5", "St6"],
        "destination":     ["Ealing"] * 6,
        "time_to_station": [120, 300, 900, 1500, 1800, 60],
        "expected_arrival":["2026-06-05T10:00:00Z"] * 6,
        "ingested_at":     ["2026-06-05T09:58:00Z"] * 6,
    })


# ── Feature engineering tests ─────────────────────────────────────────────

class TestParseTimestamps:
    def test_converts_strings_to_datetime(self):
        df = make_sample_df()
        result = parse_timestamps(df)
        assert pd.api.types.is_datetime64_any_dtype(result["expected_arrival"]), \
            "expected_arrival should be datetime after parsing"

    def test_does_not_mutate_input(self):
        df = make_sample_df()
        original_type = type(df["expected_arrival"].iloc[0])
        parse_timestamps(df)
        assert type(df["expected_arrival"].iloc[0]) == original_type, \
            "parse_timestamps should not modify the original dataframe"


class TestDelayFeatures:
    def test_minutes_to_station_converts_correctly(self):
        df = make_sample_df()
        result = compute_delay_features(df)
        # 120 seconds should become 2.0 minutes
        assert result["minutes_to_station"].iloc[0] == 2.0

    def test_delay_categories_are_valid(self):
        df = make_sample_df()
        result = compute_delay_features(df)
        valid_categories = {"imminent", "normal", "delayed", "severe", "unknown"}
        actual = set(result["delay_category"].unique())
        assert actual.issubset(valid_categories), \
            f"Unexpected categories found: {actual - valid_categories}"

    def test_severe_category_assigned_correctly(self):
        df = make_sample_df()
        result = compute_delay_features(df)
        # 1800 seconds = 30 minutes → should be severe
        severe_rows = result[result["time_to_station"] == 1800]
        assert (severe_rows["delay_category"] == "severe").all(), \
            "30-minute delay should be classified as severe"

    def test_imminent_category_assigned_correctly(self):
        df = make_sample_df()
        result = compute_delay_features(df)
        # 60 seconds = 1 minute → should be imminent
        imminent_rows = result[result["time_to_station"] == 60]
        assert (imminent_rows["delay_category"] == "imminent").all()


class TestVehicleFeatures:
    def test_prediction_count_is_correct(self):
        df = make_sample_df()
        result = compute_vehicle_features(df)
        # vehicle C appears 3 times in our sample
        vehicle_c = result[result["vehicle_id"] == "C"]
        assert (vehicle_c["vehicle_prediction_count"] == 3).all(), \
            "Vehicle C should have prediction count of 3"

    def test_missing_direction_flagged(self):
        df = make_sample_df()
        result = compute_vehicle_features(df)
        # row 3 has direction=None
        assert result["missing_direction"].iloc[3] == True, \
            "Row with None direction should be flagged"

    def test_no_false_missing_direction_flags(self):
        df = make_sample_df()
        result = compute_vehicle_features(df)
        # rows with real direction values should not be flagged
        has_direction = result[result["direction"].notna()]
        assert not has_direction["missing_direction"].any(), \
            "Rows with direction data should not be flagged as missing"


# ── Detection tests ───────────────────────────────────────────────────────

class TestDetection:
    def test_severe_delay_flag_fires_correctly(self):
        df = engineer_features(make_sample_df())
        result = flag_severe_delay(df)
        # 1800 seconds = 30 minutes, over our 20 minute threshold
        severe = result[result["time_to_station"] == 1800]
        assert severe["flag_severe_delay"].all()

    def test_severe_delay_flag_does_not_fire_for_short_delays(self):
        df = engineer_features(make_sample_df())
        result = flag_severe_delay(df)
        # 120 seconds = 2 minutes, well under threshold
        short = result[result["time_to_station"] == 120]
        assert not short["flag_severe_delay"].any()

    def test_anomaly_score_does_not_exceed_flag_count(self):
        df = engineer_features(make_sample_df())
        result = run_detection(df)
        assert result["anomaly_score"].max() <= 4, \
            "Anomaly score cannot exceed number of flags (4)"

    def test_anomaly_score_is_never_negative(self):
        df = engineer_features(make_sample_df())
        result = run_detection(df)
        assert result["anomaly_score"].min() >= 0

    def test_get_anomalies_filters_correctly(self):
        df = engineer_features(make_sample_df())
        df = run_detection(df)
        anomalies = get_anomalies(df, min_score=1)
        assert (anomalies["anomaly_score"] >= 1).all(), \
            "get_anomalies should only return records with score >= min_score"

    def test_get_anomalies_sorted_by_score(self):
        df = engineer_features(make_sample_df())
        df = run_detection(df)
        anomalies = get_anomalies(df, min_score=1)
        scores = anomalies["anomaly_score"].tolist()
        assert scores == sorted(scores, reverse=True), \
            "Anomalies should be sorted highest score first"


# ── Edge case tests ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_dataframe_does_not_crash(self):
        empty = pd.DataFrame(columns=make_sample_df().columns)
        try:
            result = engineer_features(empty)
            assert len(result) == 0
        except Exception as e:
            pytest.fail(f"engineer_features crashed on empty dataframe: {e}")

    def test_all_missing_directions(self):
        df = make_sample_df()
        df["direction"] = None
        result = compute_vehicle_features(df)
        assert result["missing_direction"].all(), \
            "All rows should be flagged when all directions are missing"