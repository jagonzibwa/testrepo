# Time-Series Pipeline — Metro Interstate Traffic Volume (Group 21)

An end-to-end pipeline for forecasting **hourly traffic on Interstate 94** (Minneapolis–St Paul): exploratory analysis → feature engineering → model training with hyperparameter tuning → **MySQL and MongoDB** storage → a **FastAPI** CRUD / time-series API → a prediction script that pulls data from the API and forecasts the next hour.

| | |
|---|---|
| **Dataset** | [Metro Interstate Traffic Volume](https://www.kaggle.com/datasets/pooriamst/metro-interstate-traffic-volume) (Kaggle; originally UCI ML Repository #492) — 48,204 rows, hourly, 2012-10-02 → 2018-09-30 |
| **Target** | `traffic_volume` — westbound vehicles per hour at MnDOT ATR station 301 |
| **Variables** | temperature, rain, snow, cloud cover, weather category, holiday |
| **Task** | One-step-ahead (next hour) regression forecast |
| **Best model** | Tuned Random Forest — **test MAE 140 veh/h, R² 0.988** (seasonal-naive baseline: MAE 340) |

## Why this problem
Short-term traffic forecasts feed ramp metering, incident response, roadwork scheduling and congestion alerts. The dataset has a clean timestamp, a target that matters, and several external drivers (weather, holidays). It also has real defects to fix: duplicate timestamps, 22.8% missing hours including a 10-month outage, and impossible sensor values.

---

## Repository structure

```
├── data/
│   ├── raw/Metro_Interstate_Traffic_Volume.csv.gz      original dataset
│   └── processed/traffic_hourly_clean.csv.gz           model-ready features (written by notebook 01)
├── notebooks/
│   ├── 01_eda_preprocessing.ipynb     Task 1A/B: EDA, missing data, 6 analytical questions
│   └── 02_model_training.ipynb        Task 1C: 9 experiments, tuning, experiment table
├── src/
│   ├── preprocessing.py               shared cleaning + feature pipeline (training AND inference)
│   ├── records.py                     API record <-> MongoDB document mapping
│   ├── plotting.py                    chart style
│   └── config.py                      paths + DB settings from .env
├── database/                          Task 2 (see database/README.md)
│   ├── sql/schema.sql, queries.sql, erd.png
│   ├── mongodb/validator.json, sample_documents.json, queries.js
│   ├── load_mysql.py, load_mongodb.py, run_queries.py, draw_erd.py
├── api/                               Task 3: FastAPI app
│   ├── main.py, sql_routes.py, mongo_routes.py, schemas.py, db.py
├── scripts/
│   ├── predict.py                     Task 4: fetch from API -> preprocess -> load model -> forecast
│   └── test_api.py                    end-to-end test of every endpoint (both databases)
├── models/
│   ├── traffic_model.joblib           trained model
│   └── model_metadata.json            features, metrics, training period
├── outputs/
│   ├── figures/                       every chart used in the report
│   ├── experiment_results.csv / .md   experiment table
│   ├── query_results/                 SQL + MongoDB queries with results
│   └── api_test_results.md            request/response log of the API test
├── report/
│   ├── Group21_Time_Series_Pipeline_Report.pdf   submission report
│   └── build_report.py                rebuilds the PDF from the saved outputs (edit TEAM at the top)
└── requirements.txt, .env.example
```

---

## Reproducing the results

### 1. Environment
```bash
python -m venv .venv
```
```bash
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
```
```bash
pip install -r requirements.txt
```

### 2. Databases
You need **MySQL 8.x** and **MongoDB 5.0+** (`$setWindowFields` is used). On Windows:
```bash
winget install Oracle.MySQL
```
```bash
winget install MongoDB.Server
```
Create a MySQL user and database (as root):
```sql
CREATE DATABASE metro_traffic;
CREATE USER 'traffic_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON metro_traffic.* TO 'traffic_user'@'localhost';
```
Copy `.env.example` to `.env` and fill in the password and connection details.

### 3. Load data and run queries
```bash
python database/load_mysql.py
```
```bash
python database/load_mongodb.py
```
```bash
python database/run_queries.py
```

### 4. Notebooks (EDA + training)
```bash
jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda_preprocessing.ipynb
```
```bash
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=3600 notebooks/02_model_training.ipynb
```
Notebook 02 takes about 15 minutes (hyperparameter searches). It writes `models/traffic_model.joblib`.

### 5. API
```bash
uvicorn api.main:app --reload
```
Interactive docs: <http://127.0.0.1:8000/docs>. Test every endpoint on both databases:
```bash
python scripts/test_api.py
```

### 6. Forecast
```bash
python scripts/predict.py
```
```bash
python scripts/predict.py --source sql --at 2018-09-28T17:00
```
The first forecasts the hour after the latest record. The second back-tests a known hour and prints the error.

---

## Task summaries

### Task 1 — EDA, preprocessing, modelling
* **Time range / granularity:** 2 Oct 2012 – 30 Sep 2018, hourly.
* **Data problems and fixes:** duplicate timestamps (one row per weather condition) collapsed to one row per hour; 11,976 missing hours. Gaps of ≤ 3 h are time-interpolated and flagged. Longer gaps (incl. a 10-month outage) are **not** filled, and the affected lag windows are dropped. 0 K temperatures and a 9,831 mm rain value are set to NaN. Holiday labels are spread from 00:00 to the whole day.
* **Six analytical questions** (each with charts and interpretation): trend with 7/30/365-day **moving averages**, daily/weekly seasonality, **lag effects** (ACF/PACF; lag 168 h r = 0.946), weather effects, holiday effects (−27%), and whether **lagged moving-average deviations** predict departures from last week (r = 0.47).
* **Features (33):** calendar + cyclical encodings, weather, lags 1/2/3/24/168 h, rolling means 3/24/168 h, 24 h rolling std.
* **Experiments:** seasonal naive, Linear, Ridge (grid search), Random Forest (default + randomised search), HistGradientBoosting (default + randomised search), and two feature ablations. Tuning uses `TimeSeriesSplit` on 2012–2017; the 2018 hold-out is only used for final reporting.

| Exp | Model | CV MAE | Test MAE | Test RMSE | Test R² |
|---|---|---:|---:|---:|---:|
| E1 | Seasonal naive (lag 168) | 352.9 | 340.2 | 651.2 | 0.891 |
| E2 | Linear Regression | 295.2 | 281.8 | 397.7 | 0.959 |
| E3 | Ridge (tuned) | 294.7 | 281.7 | 398.0 | 0.959 |
| E4 | Random Forest (default) | 184.4 | 146.4 | 231.4 | 0.986 |
| **E5** | **Random Forest (tuned)** | **173.8** | **140.0** | **219.4** | **0.988** |
| E6 | HistGradientBoosting (default) | 181.7 | 149.7 | 229.3 | 0.987 |
| E7 | HistGradientBoosting (tuned) | 174.5 | 139.7 | 218.1 | 0.988 |
| E8 | E7 without lags / moving averages | 301.4 | 222.1 | 377.4 | 0.963 |
| E9 | E7 without weather | 174.5 | 140.0 | 219.8 | 0.988 |

### Task 2 — Databases
* **MySQL:** 4 normalised tables — `traffic_observations` (hourly fact table), `weather_conditions` (lookup), `observation_weather` (junction; an hour can have several conditions), `holidays`. ERD: [`database/sql/erd.png`](database/sql/erd.png).
* **MongoDB:** `traffic_readings`, one document per hour with embedded weather conditions and a pre-computed `calendar` sub-document, `$jsonSchema` validation and a unique `timestamp` index.
* 6 SQL + 5 MongoDB queries (joins, CTEs, window functions, `$setWindowFields` moving averages). Results: [`outputs/query_results/`](outputs/query_results/). Details: [`database/README.md`](database/README.md).

### Task 3 — API
The same endpoints exist under `/sql/records` (MySQL) and `/mongo/records` (MongoDB), with one shared record schema:

| Method | Path | Description |
|---|---|---|
| POST | `/{db}/records` | Create an hourly record (409 if the hour exists) |
| GET | `/{db}/records?limit=&offset=` | List, newest first |
| GET | `/{db}/records/latest` | **Latest record** |
| GET | `/{db}/records/range?start=&end=` | **Records by date range** |
| GET | `/{db}/records/{id}` | One record |
| PUT | `/{db}/records/{id}` | Update the fields sent |
| DELETE | `/{db}/records/{id}` | Delete (SQL cascades weather links) |
| GET | `/` | Health check with record counts |

Inputs are validated by Pydantic (e.g. cloud cover 0–100, non-negative volume). MongoDB also enforces its own `$jsonSchema`. `scripts/test_api.py` runs 23 checks across both databases ([log](outputs/api_test_results.md)).

### Task 4 — Prediction script
`scripts/predict.py` (1) fetches the latest record and two weeks of history from the API, (2) runs them through **the same `src/preprocessing.py` pipeline** used in training, (3) loads `models/traffic_model.joblib`, and (4) prints and saves the forecast to `outputs/latest_forecast.json`. Features built from API data match the training features to within 1e-11.

```
 Forecast for Monday 01 Oct 2018, 00:00
   predicted traffic volume :    542 vehicles/hour
   previous hour            :    954
   same hour last week      :    509
```

---

## Team contributions

| Member | Main components | Key files |
|---|---|---|
| _Name 1_ | Task 1A/B — EDA, missing-data strategy, analytical questions | `notebooks/01_eda_preprocessing.ipynb`, `src/preprocessing.py` |
| _Name 2_ | Task 1C — feature engineering, experiments, tuning | `notebooks/02_model_training.ipynb`, `models/` |
| _Name 3_ | Task 2 — SQL schema, ERD, MongoDB design, queries | `database/` |
| _Name 4_ | Task 3 & 4 — API endpoints, prediction script | `api/`, `scripts/` |

## Data source and licence
Hogue, J. (2019). *Metro Interstate Traffic Volume* [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5X60B — CC BY 4.0. Traffic data from MnDOT; weather from OpenWeatherMap.
