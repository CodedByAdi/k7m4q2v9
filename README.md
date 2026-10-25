# Windline — GB Wind Forecast Desk

> **Retrospective Day-Ahead Wind Forecast Analytics Engine**<br>
> Evaluates Great Britain (GB) day-ahead national wind generation forecasts against outturn actual generation across all 31 delivery days of **January 2026** (2026-01-02 through 2026-02-01).

---

## 1. Project Overview

In GB power system operations and wholesale electricity scheduling, position managers make day-ahead volume commitments before exchange gate closure. Windline reconstructs the exact operational decision context for every day of January 2026 to assess forecast accuracy, systematic bias, and publication vintage evolution:

* **Decision Window**: Decisions taken between **2026-01-01 and 2026-01-31** inclusive.
* **Delivery Window**: Physical power delivery between **2026-01-02 and 2026-02-01** (31 calendar days).
* **Decision Cutoff**: Configurable gate closure cutoff in `Europe/London` (default: **`09:00`**).
* **Strict Anti-Leakage Policy**: Any forecast published after the decision cutoff is strictly excluded from decision metrics.
* **Granularity Alignment**: Aggregates half-hourly outturn generation (`FUELHH`) into hourly means and aligns with hourly forecast intervals (`WINDFOR`) on normalized UTC timestamps.
* **Reproducibility**: Delivers **100% data coverage** (all 744 hourly comparison periods across 31 delivery days) backed by immutable verified raw snapshots.

---

## 2. Key Capabilities

* **Deterministic Vintage Selection**: Filters forecast runs strictly by publication timestamp (`publishTime <= cutoff_utc`) and selects the latest available eligible vintage without mixing data across runs.
* **Completeness Auditing**: Distinguishes between latest publication overall (which may include hindsight), latest eligible vintage at cutoff, and latest complete vintage covering all 24 delivery hours.
* **Zero-Imputation Integrity**: Never replaces missing forecast or unmetered actual intervals with 0.0 MW. Incomplete intervals are flagged explicitly as gaps.
* **Standard Domain Metrics**: Evaluates Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), Signed Mean Bias, and Weighted Absolute Percentage Error (WAPE).
* **Interactive Decision Workspace**: A 5-view React dashboard providing window-level KPIs, daily error trends, 24-hour interval drill-downs, vintage audit comparisons, and methodology documentation.
* **Data Portability**: Full 744-row CSV export endpoint for offline spreadsheet and quantitative analysis.

---

## 3. Architecture and Technology Stack

Windline is designed as a self-contained, deterministic analytical application that packages the analytical REST API and the pre-compiled single-page application into a unified service:

```
┌────────────────────────────────────────────────────────────────────────┐
│                              CLIENT                                    │
│   React 19 + TypeScript + Vite + Vanilla CSS Design System             │
│   5 Core Views: Overview | Explorer | Accuracy | Quality | Methodology │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / REST (/api/*) or Static (/)
┌───────────────────────────────────▼────────────────────────────────────┐
│                  FASTAPI / UVICORN APPLICATION ENGINE                  │
│                                                                        │
│   • app.py: Root ASGI entrypoint serving React SPA at / and assets     │
│   • backend/app/routes.py: 7 deterministic REST endpoints              │
│   • backend/app/engine.py: Cutoff filtering & vintage selection        │
│   • backend/app/metrics.py: MAE, RMSE, Signed Bias, WAPE, Coverage     │
│   • backend/app/loader.py: In-memory snapshot caching (eager load)     │
│   • backend/app/timestamps.py: UTC normalization & interval validation │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                    IMMUTABLE AUDITED DATA SNAPSHOTS                    │
│   • data/audit/fuelhh_full.json: 1,488 verified half-hourly actuals    │
│   • data/audit/windfor_full.json: 18,688 verified forecast records     │
│   • data/provenance.json: Cryptographic hashes, source parameters      │
└────────────────────────────────────────────────────────────────────────┘
```

* **Backend**: Python 3.12 (compatible with 3.11+), FastAPI 0.162+, Pydantic v2, Uvicorn.
* **Frontend**: React 19, TypeScript 5.8+, Vite 8, Lucide React, institutional dark/forest styling.
* **Unified Process**: Single Uvicorn process serves both the backend API and the static React bundle using FastAPI's static asset mounting.

---

## 4. Data Sources and Licence Attribution

All market data originates from the official **Elexon Insights Solution (BMRS) API**:
* **Data Provider**: Elexon Limited (Balancing and Settlement Code company for Great Britain).
* **Base URL**: `https://data.elexon.co.uk/bmrs/api/v1`
* **Actual Generation Dataset**: `/datasets/FUELHH/stream` filtered to `fuelType=WIND`.
* **Forecast Generation Dataset**: `/datasets/WINDFOR/stream` (multi-day forecast horizons).
* **Licence**: Licensed under the official [BMRS Open Data Licence](https://www.elexon.co.uk/bsc/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/).
* **Mandatory Attribution**: *"Contains BMRS data © Elexon Limited copyright and database right 2026."*
* **Non-Endorsement**: Elexon Limited does not endorse, sponsor, or approve Windline or its analytical results.

### Audited Datasets Included:
* `data/audit/fuelhh_full.json`: 1,488 records (31 days × 48 settlement periods, 0 nulls, 0 missing intervals).
* `data/audit/windfor_full.json`: 18,688 forecast records across 256 publication vintages.
* `data/provenance.json`: Metadata documenting endpoint parameters, payload shapes, and verification checksums.

---

## 5. Methodology and Explicit Assumptions

### 5.1 Decision and Delivery Mapping
Decisions taken on calendar date $D$ plan for physical energy delivery on calendar day $D + 1$:
$$\text{Delivery Date} = \text{Decision Date} + 1\text{ day}$$
* January 1 decisions evaluate delivery on January 2; January 31 decisions evaluate delivery on February 1.

### 5.2 Timezone and Decision Cutoff
* The operational decision cutoff is evaluated in `Europe/London` (default: 09:00 local time).
* In January (GMT = UTC+0), 09:00 local time equals 09:00:00 UTC.
* Timezone handling uses Python's standard `zoneinfo.ZoneInfo("Europe/London")` to maintain valid conversions across seasonal clock shifts.
* Any forecast vintage with `publishTime > cutoff_utc` is ineligible and excluded from the decision metrics.

### 5.3 Granularity Normalization
* Actuals (`FUELHH`) arrive on half-hourly settlement periods (SPs 1..48) in MW. Hourly actual generation is computed as the arithmetic mean of the two constituent half-hours (`:00` and `:30`).
* Forecasts (`WINDFOR`) are published on 60-minute intervals in MW.
* Joins are anchored on normalized UTC hour timestamps (`YYYY-MM-DDTHH:00:00Z`).

### 5.4 Error Metrics Definitions
* **MAE (Mean Absolute Error)**: $\frac{1}{n}\sum |f_i - a_i|$ (MW)
* **RMSE (Root Mean Squared Error)**: $\sqrt{\frac{1}{n}\sum (f_i - a_i)^2}$ (MW)
* **Signed Bias**: $\frac{1}{n}\sum (f_i - a_i)$ (MW). Positive = overforecast; Negative = underforecast.
* **WAPE (Weighted Absolute Percentage Error)**: $\frac{\sum |f_i - a_i|}{\sum a_i} \times 100$ (%). Returns `null` if total actual generation is zero.
* **Extreme Discrepancy Event**: An exploratory threshold for hourly errors with $|f_i - a_i| \ge 3{,}000\text{ MW}$.

### 5.5 Domain Boundaries & Limitations
1. **Non-Commercial Scope**: Windline is an analytical evaluation engine. It does not provide trading advice, imbalance settlement forecasting, or financial trading recommendations.
2. **Publication Schedule Discrepancy**: While Elexon's narrative web documentation references forecast publication at 03:30, 05:30, and 08:30, the live BMRS stream records publish timestamps at 02:30, 04:30, and 07:30 UTC. Windline handles this by evaluating recorded `publishTime` timestamps rather than relying on hardcoded schedules.

---

## 6. Local Installation and Running

### 6.1 Prerequisites
* Python 3.12 (or 3.11+)
* Node.js v20+ and npm 10+

### 6.2 Installation & Build
```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Build the React frontend production bundle
cd frontend
npm ci
npm run build
cd ..
```

### 6.3 Running in Unified Production Mode
To start the unified server serving both the React SPA and FastAPI API from port 8000:
```bash
python app.py
```
* **Frontend Application**: Open [http://localhost:8000](http://localhost:8000)
* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 6.4 Independent Local Development Mode
If modifying frontend or backend code independently:
```bash
# Terminal 1: Backend with automatic reload
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: Frontend with Vite HMR
cd frontend
npm run dev
# Vite runs on http://localhost:3000 with proxy to localhost:8000
```

---

## 7. Docker Instructions

A multi-stage `Dockerfile` and `docker-compose.yml` are provided. The build compiles the frontend with Node.js and packages the static assets with the Python runtime into a minimal container.

### 7.1 Docker Compose
```bash
# Validate compose configuration
docker compose config

# Build and start container in detached mode
docker compose up --build -d

# Check container logs
docker compose logs -f

# Stop container
docker compose down
```

### 7.2 Standalone Docker Commands
```bash
# Build Docker image
docker build -t windline:latest .

# Run container binding port 8000:8000
docker run -d --name windline-app -p 8000:8000 windline:latest

# Check container health
docker inspect --format='{{json .State.Health}}' windline-app

# Stop and remove container
docker stop windline-app && docker rm windline-app
```

---

## 8. Tests and Verification Commands

Windline includes backend unit and integration test suites, Python bytecode compilation checks, and live server endpoint verification.

### 8.1 Backend Pytest Suite
```bash
python scripts/run_tests.py
# (33/33 tests passing across domain logic, timestamp arithmetic, metrics, and API contracts)
```

### 8.2 Python Bytecode Compilation Check
```bash
python -m compileall app.py backend scripts
```

### 8.3 Live Endpoint Verification
While the server is running on `http://127.0.0.1:8000`:
```bash
python scripts/verify_live_server.py
```
This script verifies:
1. `GET /api/health` — 200 status and healthy application state.
2. `GET /api/overview?cutoff=09:00` — all 31 delivery days and 744 hourly comparison intervals.
3. `GET /` — React single-page application served at root.
4. Static assets — bundled CSS and JavaScript served with correct MIME types.
5. `GET /api/deliveries/{date}` — vintage selection and hourly interval details.
6. `GET /api/export.csv` — complete 744-row CSV download matching audited data.

### 8.4 Continuous Integration
A GitHub Actions workflow is defined in `.github/workflows/ci.yml` to automatically run tests, build the frontend, build the Docker container, and verify live endpoints on pushes and pull requests.

---

## 9. Deployment Instructions

### 9.1 Vercel Serverless Deployment
Windline is configured for deployment as a Vercel Serverless Function via `vercel.json`:
* **Runtime**: Python 3.12 running FastAPI.
* **Build Command**: `cd frontend && npm ci && npm run build` compiles static assets during build.
* **Entrypoint**: `backend.app.main:app` (configured via `[tool.vercel]` in `pyproject.toml`) points directly to the FastAPI instance.
* **Data Snapshots**: Verified historical snapshots are bundled via `"includeFiles": "data/**"`.

To deploy via the Vercel CLI:
```bash
# 1. Install Vercel CLI
npm install -g vercel

# 2. Deploy
vercel
```

### 9.2 Container Hosting
The application can also be deployed to any container hosting platform (such as Google Cloud Run, AWS ECS, or Azure Container Apps) using the included `Dockerfile`:
```bash
docker build -t windline .
docker run -p 8000:8000 windline
```

---

## 10. AI-Assisted Development Disclosure

In compliance with engineering challenge evaluation guidelines:  
**AI coding assistants (Google Antigravity / Gemini) were utilized during the research, backend architecture, React UI implementation, and Docker/deployment packaging of this project.** All API integrations, statistical metrics, timestamp boundaries, and deployment configurations have been verified with automated test suites and real live API data audits.
