# Transit Anomaly Detection

A data engineering and anomaly detection pipeline designed to monitor live transit data from the Transport for London (TfL) API. It fetches real-time vehicle positions, validates data integrity, engineers temporal features, and scores individual vehicle records for anomalies such as severe delays, line outliers, and vehicle bunching.

---

## 🚀 Features

* **Live Data Ingestion:** Connects directly to the TfL API to fetch real-time bus locations and expected arrivals.
* **Strict Data Validation:** Halts the pipeline if incoming data is corrupted, missing required columns, or contains logically impossible timestamps.
* **Automated Feature Engineering:** Transforms raw seconds into readable delay categories and calculates baseline averages for entire transit lines.
* **Multi-Signal Anomaly Scoring:** Uses threshold-based rules to assign an `anomaly_score` to each vehicle based on delays, bunching, and missing data.

---

## 🛠️ Installation & Setup

1.  **Clone the repository and set up your virtual environment:**
    (The `.gitignore` is already configured to ignore `venv/`, `__pycache__`, and local data CSVs).
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use: venv\Scripts\activate
    ```

2.  **Install dependencies:**
    You will need `pandas` and `requests`.
    ```bash
    pip install pandas requests
    ```

3.  **Configure API Keys:**
    Open `pipeline.py` and replace the placeholder `APP_KEY` with your actual Transport for London API key:
    ```python
    APP_KEY = "your_tfl_api_key_here"
    ```

---

## 💻 Usage

To execute the pipeline, run the main pipeline script. By default, it is configured to pull data for the "central" line.

```bash
python pipeline.py