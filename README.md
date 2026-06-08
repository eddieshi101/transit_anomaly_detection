# Transit Anomaly Detection

A data engineering and anomaly detection pipeline designed to monitor live transit data from the Transport for London (TfL) API. It fetches real-time vehicle arrival predictions, validates data integrity, engineers delay and vehicle-level features, stores historical run data, and scores individual vehicle records for anomalies such as severe delays, line outliers, vehicle bunching, missing direction data, and repeated historical lateness.

---

## 🚀 Features

* **Live Data Ingestion:** Connects directly to the TfL API to fetch real-time bus arrival predictions for a selected line.

* **Strict Data Validation:** Checks incoming data before feature engineering begins. The pipeline flags missing required columns, unusually high null rates, impossible `time_to_station` values, and suspiciously low record counts.

* **Automated Feature Engineering:** Converts raw arrival times from seconds into minutes, assigns readable delay categories, calculates each vehicle's delay compared to the line average, and computes vehicle-level features such as prediction count and missing direction data.

* **Historical Run Tracking:** Saves each pipeline run into a local SQLite database so vehicle behavior can be compared across recent runs.

* **Historically Late Detection:** Flags vehicles that have been anomalous in more than half of their recent appearances. This adds a historical signal instead of only relying on the current live snapshot.

* **Multi-Signal Anomaly Scoring:** Combines multiple detection signals into one `anomaly_score`. Each triggered flag adds one point, making it easy to rank vehicles by severity.

* **CSV Output Reports:** Generates timestamped anomaly reports that can be reviewed by an analyst or used by a downstream system.

---

## 🧠 Detection Signals

The pipeline currently uses the following anomaly flags:

| Flag                     | Description                                                               |
| ------------------------ | ------------------------------------------------------------------------- |
| `flag_severe_delay`      | Vehicle is more than 20 minutes away from the station.                    |
| `flag_delay_outlier`     | Vehicle is significantly worse than the current line average.             |
| `flag_bunching`          | Vehicle appears in an unusually high number of arrival predictions.       |
| `flag_missing_direction` | Vehicle record is missing direction data.                                 |
| `flag_historically_late` | Vehicle has been anomalous in more than half of its recent recorded runs. |

Each flag contributes `1` point to the final `anomaly_score`.

For example:

```text
anomaly_score = 3
```

means that three separate anomaly signals fired for that vehicle record.

---

## 🕓 Historical Lateness Feature

The project includes a historical anomaly feature using a local SQLite database.

After each pipeline run, the system stores vehicle-level results in:

```text
data/history.db
```

The database stores information such as:

* `run_id`
* `vehicle_id`
* `line_id`
* `anomaly_score`
* `was_flagged`
* `minutes_to_station`
* `delay_vs_average`
* `ingested_at`

On future runs, the pipeline loads recent history for the selected line and calculates:

| Column                      | Description                                                                    |
| --------------------------- | ------------------------------------------------------------------------------ |
| `times_flagged_last_7_runs` | Number of recent runs where the vehicle was flagged.                           |
| `total_runs_seen`           | Number of recent runs where the vehicle appeared.                              |
| `avg_delay_historical`      | Average historical minutes to station for that vehicle.                        |
| `is_historically_late`      | `True` if the vehicle was flagged in more than half of its recent appearances. |

This allows the pipeline to detect vehicles that may not look extreme in the current snapshot but have a repeated pattern of poor performance.

---

## 🛠️ Installation & Setup

1. **Clone the repository and set up your virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

2. **Install dependencies:**

   You will need `pandas` and `requests`.

   ```bash
   pip install pandas requests
   ```

3. **Configure your TfL API key:**

   Open `pipeline.py` and replace the placeholder `APP_KEY` with your actual Transport for London API key:

   ```python
   APP_KEY = "your_tfl_api_key_here"
   ```

4. **Make sure the `data/` folder exists:**

   The pipeline writes CSV files and the SQLite history database into the `data/` folder.

   ```bash
   mkdir data
   ```

---

## 💻 Usage

To execute the pipeline, run:

```bash
python pipeline.py
```

By default, the pipeline is configured to pull data for the `"central"` line.

Inside `pipeline.py`, you can change the line by editing:

```python
line_id = "central"
```

Example:

```python
line_id = "victoria"
```

---

## 🔄 Pipeline Flow

The project follows this order:

```text
1. Fetch live TfL arrival data
2. Convert raw API records into a pandas DataFrame
3. Validate required fields and data quality
4. Engineer delay and vehicle-level features
5. Load historical vehicle behavior from SQLite
6. Add historical lateness features
7. Run anomaly detection
8. Compute anomaly scores
9. Save the current run to the history database
10. Export a timestamped anomaly report
```

This structure separates ingestion, validation, feature engineering, detection, history tracking, and reporting into different parts of the pipeline.

---

## 📁 Project Structure

```text
transit_anomaly_detection/
│
├── pipeline.py          # Main script that runs the full pipeline
├── features.py          # Feature engineering functions
├── detect.py            # Anomaly detection rules and scoring
├── validate.py          # Data validation and output report generation
├── history.py           # SQLite history tracking and historical features
├── conftest.py          # Test path configuration
├── .gitignore           # Prevents local files, virtual environments, and data exports from being committed
│
└── data/
    ├── history.db       # Local SQLite database created by the pipeline
    └── anomaly_report_*.csv
```

---

## 📊 Example Output

When the pipeline runs successfully, it prints the top anomalies in the terminal:

```text
Top anomalies:
vehicle_id  station_name  minutes_to_station  delay_category  anomaly_score  times_flagged_last_7_runs  is_historically_late
12345       Example Stop  24.5                severe          3              5                          True
```

It also saves a timestamped CSV report:

```text
data/anomaly_report_central_YYYYMMDD_HHMMSS.csv
```

---

## 🧪 Data Validation Checks

Before feature engineering, the pipeline checks for:

* Missing required columns
* Columns with high null rates
* Negative `time_to_station` values
* `time_to_station` values greater than 2 hours
* Suspiciously low record counts

If critical validation checks fail, the pipeline stops before producing downstream results.

---

## 📝 Notes

* The historical feature becomes more useful after the pipeline has been run multiple times.
* On the first run, there is no existing history, so historical fields are filled with default values.
* The SQLite database is local and intended for lightweight project use.
* The current detection logic is rule-based, making it easy to explain and debug.
* Future improvements could include configurable thresholds, scheduled runs, dashboard visualizations, or machine learning-based anomaly detection.
