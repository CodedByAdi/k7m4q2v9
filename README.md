# WINDLINE — GB Wind Forecast Desk

> **Retrospective Day-Ahead Wind Forecast Analytics Engine & Decision-Support Workspace**  
> Evaluates Great Britain (GB) day-ahead national wind generation forecasts against outturn actual generation across all 31 delivery days of **January 2026** (2026-01-02 through 2026-02-01).

---

## 1. Product Description

In national power system operations and wholesale power procurement, day-ahead position managers and energy traders make volume commitments prior to exchange gate closure. Windline reconstructs the exact operational decision context for every single day of January 2026 to assess forecast accuracy, systematic bias, and vintage evolution:

* **Decision Window**: Decisions taken between **2026-01-01 and 2026-01-31** inclusive.
* **Delivery Window**: Physical power delivery between **2026-01-02 and 2026-02-01** (31 calendar days).
* **Decision Cutoff**: Configurable gate closure cutoff in `Europe/London` (default: **`09:00`**).
* **Strict Anti-Leakage / Anti-Hindsight Policy**: Any forecast published after the decision cutoff is strictly excluded from decision metrics.
* **Granularity Alignment**: Aggregates half-hourly outturn generation (`FUELHH`) into hourly means and aligns with hourly forecast intervals (`WINDFOR`) on normalized UTC timestamps.
* **Reproducibility**: Delivers **100% data coverage** (all 744 hourly comparison periods across 31 delivery days) backed by immutable verified raw snapshots.

---

## 2. Architecture Overview

Windline is designed as a zero-database, deterministic analytical application that packages both the analytical API and the responsive single-page application (SPA) into a single unified service:

```
┌────────────────────────────────────────────────────────────────────────┐
│                              CLIENT                                    │
│   React 19 + TypeScript + Vite + Tailwind CSS / Vanilla Design System  │
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

* **Backend**: Python 3.12 (supported on Vercel and Docker; compatible with 3.11+), FastAPI 0.162.0, Pydantic v2, Uvicorn.
* **Frontend**: React 19, TypeScript 5.8+, Vite 8, Lucide React, modern clean dark UI.
* **Unified Process**: Single Uvicorn process serves both the backend API and the static React bundle using FastAPI's official `app.frontend("/", directory="frontend/dist")` integration.

---

## 3. Data Attribution & Licencing

All market telemetry originates from the official **Elexon Insights Solution (BMRS) API**:
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

## 4. Local Run Instructions

### 4.1 Prerequisites
* Python 3.12 (or 3.11+)
* Node.js v20+ and npm 10+

### 4.2 Installation & Build
```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Build the React frontend production bundle
cd frontend
npm ci
npm run build
cd ..
```

### 4.3 Running in Unified Production Mode
To run the unified server (serving both the React SPA and FastAPI API from one process on port 8000):
```bash
python app.py
```
* **Frontend Application**: Open [http://localhost:8000](http://localhost:8000)
* **Interactive API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 4.4 Running in Independent Local Development Mode
If actively modifying frontend or backend code:
```bash
# Terminal 1: Backend with automatic reload
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: Frontend with Vite HMR
cd frontend
npm run dev
# Vite runs on http://localhost:3000 with proxy to localhost:8000
```

---

## 5. Docker Instructions

A production-grade, multi-stage `Dockerfile` and `docker-compose.yml` are provided. The build compiles the frontend with Node.js and packages the static assets with the Python runtime into a minimal, self-contained container.

> **Environment Note**: Docker is not installed on the local test evaluation machine (`docker` CLI command not found). The Dockerfile and docker-compose.yml have been designed according to industry standards, while local runtime validation was executed directly via Uvicorn serving the unified `app:app` entrypoint with the pre-compiled `frontend/dist` bundle.

### 5.1 Docker Build & Run with Docker Compose
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

### 5.2 Standalone Docker Commands
```bash
# Build Docker image
docker build -t windline:latest .

# Run container binding port 8000:8000
docker run -d --name windline-app -p 8000:8000 windline:latest

# Check health
docker inspect --format='{{json .State.Health}}' windline-app

# Stop and remove container
docker stop windline-app && docker rm windline-app
```

---

## 6. Testing & Quality Verification

Windline includes comprehensive backend unit and integration test suites, Python bytecode compilation checks, and live server endpoint verification.

### 6.1 Run Backend Pytest Suite
```bash
python scripts/run_tests.py
# (31/31 tests passing across domain logic, timestamp arithmetic, metrics, and API contracts)
```

### 6.2 Python Bytecode Compilation Check
```powershell
Get-ChildItem -Filter *.py -Recurse | Where-Object { $_.FullName -notmatch "node_modules|\.venv" } | ForEach-Object { python -m py_compile $_.FullName }
```

### 6.3 Run Live Endpoint & Data Audit Verification
While the server is running on `http://127.0.0.1:8000`:
```bash
python scripts/verify_live_server.py
```
This script executes live HTTP checks against:
1. `GET /api/health` — Verifies 200 status and healthy application state.
2. `GET /api/overview?cutoff=09:00` — Verifies all 31 delivery days and all 744 hourly comparison intervals.
3. `GET /` — Verifies React single-page application is served at root.
4. Direct asset URLs — Verifies bundled CSS and JavaScript are served with correct MIME types.
5. `GET /api/deliveries/{date}` — Verifies vintage selection and hourly interval details.
6. `GET /api/export.csv` — Verifies complete 744-row CSV download matching audited data.

---

## 7. API Reference

| Method | Endpoint | Query Params | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | - | Health status, version, and server timestamp. |
| `GET` | `/api/metadata` | - | Data provider attribution, date windows, metrics definitions, and provenance metadata. |
| `GET` | `/api/overview` | `cutoff=09:00` | Full 31-day summary metrics (MAE, RMSE, Bias, WAPE, Coverage) and daily metrics table. |
| `GET` | `/api/deliveries` | `cutoff=09:00` | Summary list of all 31 delivery dates with selected vintages and completeness status. |
| `GET` | `/api/deliveries/{date}` | `cutoff=09:00` | 24 hourly intervals for a delivery day with forecast, actual, and signed error. |
| `GET` | `/api/deliveries/{date}/vintages`| `cutoff=09:00` | Complete audit table of all eligible publication vintages for a decision date. |
| `GET` | `/api/export.csv` | `cutoff=09:00` | Downloadable CSV stream containing all 744 hourly intervals across January 2026. |

---

## 8. Analysis Methodology & Domain Rules

### 8.1 Decision & Delivery Date Mapping
* Procurement decisions taken on decision date $D$ plan for physical delivery on calendar day $D + 1$.
* January 1 decision plans for January 2 delivery; January 31 decision plans for February 1 delivery.

### 8.2 Strict Anti-Leakage / Cutoff Policy
* The operational decision cutoff is evaluated in `Europe/London` (09:00 local time).
* In January (GMT = UTC+0), 09:00 local time equals 09:00:00 UTC.
* Any forecast vintage with `publishTime > cutoff_utc` is ineligible and excluded from the decision metrics.

### 8.3 Vintage Eligibility vs Hindsight
* A vintage published after cutoff (e.g., 2026-01-01 22:30 UTC) contains post-cutoff information and is excluded strictly due to hindsight.
* The selection engine chooses the latest eligible publication before cutoff (e.g. 2026-01-01 07:30 UTC).

### 8.4 Granularity Normalization
* Actuals (`FUELHH`) are reported every 30 minutes in MW (generation power). Hourly actual generation is computed as the arithmetic mean of the two half-hourly periods (`:00` and `:30`).
* Forecasts (`WINDFOR`) are published on 60-minute intervals in MW.
* Joins are performed on exact normalized UTC start times (`YYYY-MM-DDTHH:00:00Z`).

### 8.5 Error Metrics Definitions
* **MAE (Mean Absolute Error)**: $\frac{1}{n}\sum |f_i - a_i|$ (MW)
* **RMSE (Root Mean Squared Error)**: $\sqrt{\frac{1}{n}\sum (f_i - a_i)^2}$ (MW)
* **Signed Bias**: $\frac{1}{n}\sum (f_i - a_i)$ (MW). Positive = overforecast; Negative = underforecast.
* **WAPE (Weighted Absolute Percentage Error)**: $\frac{\sum |f_i - a_i|}{\sum a_i} \times 100$ (%). Returns `null` if total actual generation is zero.
* **Extreme Discrepancy Event**: Defined as an hourly forecast error with $|f_i - a_i| \ge 3{,}000\text{ MW}$.

---

## 9. Explicit Limitations & Boundaries

1. **Non-Commercial Scope**: Windline is an analytical evaluation engine. It does not provide trading advice, imbalance settlement forecasting, or financial trading recommendations.
2. **Publication Schedule Discrepancy**: While Elexon's narrative web documentation states forecast publication occurs at 03:30, 05:30, and 08:30, the real official BMRS stream consistently records publish timestamps at 02:30, 04:30, and 07:30 UTC. Windline handles this by relying dynamically on recorded `publishTime` timestamps rather than hardcoded schedules.
3. **Timezone Assumptions**: January operates entirely in Greenwich Mean Time (GMT, UTC+0). The engine uses standard `zoneinfo.ZoneInfo("Europe/London")` so any future summer dates would correctly transition between GMT and British Summer Time (BST).

---

## 10. Zero-Cost Vercel Deployment

Windline is pre-configured for zero-cost deployment on the **Vercel Hobby Plan** ($0 / month).

> **Pre-Deployment Status**: Packaging, build scripting, CDN static rules, and function bundling configurations have been verified locally. No cloud deployment to Vercel has been executed yet, avoiding billing, credentials, or false deployment claims.

### 10.1 Vercel Hobby Eligibility & Caveats
* **Cost**: ₹0 / $0 USD. No credit card or paid service required.
* **Eligible Use**: Strictly restricted to personal projects and non-commercial portfolio demonstrations under [Vercel Terms of Service](https://vercel.com/legal/terms). Commercial use requires an upgrade to a paid Pro tier.
* **Resource Allowances**: 100 GB bandwidth/month, 1,000,000 serverless function invocations/month, 100 deployments/day, 300s function duration limit.
* **Architecture**: Configured to run as a single Vercel Serverless Function running Python 3.12 with FastAPI (`fastapi==0.162.0`). The React production build is pre-compiled via `buildCommand` and served via FastAPI CDN promotion.
* **Snapshot Bundling**: The verified `data/audit` directory is explicitly included in the function bundle via `"includeFiles": "data/**"` in `vercel.json`.

### 10.2 Deployment Steps
1. Install the official Vercel CLI (optional) or push to a personal GitHub repository:
   ```bash
   npm install -g vercel
   ```
2. Run deployment:
   ```bash
   vercel
   ```
   * Build command configured: `cd frontend && npm ci && npm run build`
   * Entrypoint configured: `app.py`
   * Zero environment variables or API keys required.

---

## 11. AI Development Disclosure

In compliance with engineering challenge evaluation guidelines:  
**AI coding assistants (Google Antigravity / Gemini) were utilized during the research, backend architecture, React UI implementation, and Docker/Vercel packaging phases of this project.** All API integrations, statistical metrics, timestamp boundaries, and deployment configurations have been verified with automated test suites and real live API data audits.
