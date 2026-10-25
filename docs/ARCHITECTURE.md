# Windline — Architecture & System Design

> **Application**: Windline — Retrospective GB Wind Generation Forecast Analytics<br>
> **Backend Framework**: Python 3.12 (compatible with 3.11+) / FastAPI / Pydantic

---

## 1. Overview & Architectural Goals

Windline is an engineering decision-support tool designed to retrospectively evaluate Great Britain (GB) day-ahead wind generation forecasts against outturn generation. The application supports electricity procurement decisions made between **2026-01-01 and 2026-01-31** for delivery between **2026-01-02 and 2026-02-01**.

### Core Architecture Principles
1. **Deterministic & Reproducible**: All forecast selections, actuals aggregations, and metrics calculations are pure, deterministic functions without synthetic data or random states.
2. **Strict Cutoff Enforcement**: No forecast published after a decision cutoff is ever considered eligible. Future information leakage is mathematically impossible.
3. **No Silent Mutation or Imputation**: Missing forecast or actual intervals are never imputed with zeroes. Incomplete vintages are explicitly flagged with missing interval lists.
4. **Zero Heavy Infrastructure**: Operates purely on immutable verified snapshot data with in-memory caching. No external databases, message queues, AI runtimes, or paid services.

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Verified Snapshot Layer                         │
│  data/audit/fuelhh_full.json  (1,488 half-hourly actual wind records)  │
│  data/audit/windfor_full.json (18,688 hourly forecast records, 256 v.) │
│  data/provenance.json         (Dataset provenance & checksums)         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                        1. Ingestion & Validation
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   backend.app.loader.DataLoader                        │
│  • Parses ISO-8601 strings into timezone-aware UTC datetimes           │
│  • Validates schemas and checks for corrupted or duplicate records     │
│  • Singleton in-memory store: parses raw files once on startup         │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                       2. Pure Domain Functions
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   backend.app.engine.AnalysisEngine                    │
│                                                                        │
│  ┌─────────────────────────┐        ┌───────────────────────────────┐  │
│  │   Actuals Aggregator    │        │  Forecast Vintage Selector    │  │
│  │ Group 2 half-hours      │        │ Filter publishTime <= cutoff  │  │
│  │ into 1 clock hour mean  │        │ Select latest-available       │  │
│  │ Validates uniqueness    │        │ Select latest-complete        │  │
│  └───────────┬─────────────┘        └──────────────┬────────────────┘  │
│              │                                     │                   │
│              └──────────────────┬──────────────────┘                   │
│                                 ▼                                      │
│                  ┌───────────────────────────────┐                     │
│                  │       Interval Alignment      │                     │
│                  │ Join on normalized UTC hour   │                     │
│                  │ 24 intervals per delivery day │                     │
│                  └──────────────┬────────────────┘                     │
│                                 ▼                                      │
│                  ┌───────────────────────────────┐                     │
│                  │    Metrics Calculation Engine │                     │
│                  │ MAE, RMSE, Bias, WAPE, Cov.   │                     │
│                  └───────────────────────────────┘                     │
│                                                                        │
│  In-memory analysis caching keyed by cutoff (e.g. "09:00")             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                        3. REST Presentation Layer
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   backend.app.routes.APIRouter                         │
│  • GET /api/health                                                     │
│  • GET /api/metadata                                                   │
│  • GET /api/overview?cutoff=09:00                                      │
│  • GET /api/deliveries?cutoff=09:00                                    │
│  • GET /api/deliveries/{delivery_date}?cutoff=09:00                    │
│  • GET /api/deliveries/{delivery_date}/vintages?cutoff=09:00           │
│  • GET /api/export.csv?cutoff=09:00                                    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Module Breakdown

| Module | Responsibility | Key Classes / Functions |
| :--- | :--- | :--- |
| [`backend.app.config`](../backend/app/config.py) | System-wide paths, constants, date windows, default parameters | `DECISION_DATE_START`, `DELIVERY_DATE_END`, `DEFAULT_CUTOFF_STR`, `LONDON_TZ` |
| [`backend.app.timestamps`](../backend/app/timestamps.py) | Timezone parsing, aware datetime conversion, cutoff math | `parse_iso_utc()`, `to_utc_iso()`, `make_cutoff_datetime()`, `validate_cutoff_format()` |
| [`backend.app.metrics`](../backend/app/metrics.py) | Mathematical evaluation metrics with zero-denominator safety | `calculate_mae()`, `calculate_rmse()`, `calculate_bias()`, `calculate_wape()`, `compute_metrics_summary()` |
| [`backend.app.models`](../backend/app/models.py) | Strongly typed Pydantic models for REST endpoints | `OverviewResponse`, `DeliveryDayDetailResponse`, `HourlyIntervalComparison`, `VintageInfo` |
| [`backend.app.loader`](../backend/app/loader.py) | Snapshot reader, schema validation, in-memory singleton cache | `DataLoader`, `FuelHHRecord`, `WindforRecord` |
| [`backend.app.engine`](../backend/app/engine.py) | Vintage evaluation, half-hourly aggregation, interval alignment | `AnalysisEngine`, `DeliveryDayAnalysis`, `VintageEvaluation` |
| [`backend.app.routes`](../backend/app/routes.py) | FastAPI route handlers, query parameter validation, CSV export | `router`, `get_overview()`, `get_delivery_detail()`, `export_csv()` |
| [`backend.app.main`](../backend/app/main.py) | FastAPI app factory, CORS middleware, lifespan startup loading | `app`, `lifespan()` |

---

## 4. Domain Logic & Data Policies

### 4.1 Decision vs. Delivery Date Relationship
Day-ahead electricity procurement operates on calendar date $D$ for energy delivered on calendar date $D+1$:
$$\text{Delivery Date} = \text{Decision Date} + 1\text{ day}$$

- Decision window: **2026-01-01 through 2026-01-31** (31 calendar days).
- Delivery window: **2026-01-02 through 2026-02-01** (31 calendar days).

### 4.2 Timezone & Cutoff Construction
- Default cutoff is **09:00 Europe/London**.
- In January, Great Britain operates on Greenwich Mean Time (GMT = UTC+0).
- Timezone logic uses Python's standard `zoneinfo.ZoneInfo("Europe/London")`:
  ```python
  dt_local = datetime(d.year, d.month, d.day, hour, minute, tzinfo=LONDON_TZ)
  cutoff_utc = dt_local.astimezone(timezone.utc)
  ```
- All interval comparisons occur strictly between timezone-aware UTC datetimes.

### 4.3 Forecast Vintage Selection Policy
For each decision date $D$ and configured cutoff:
1. Filter all WINDFOR publication vintages where:
   $$\text{publishTime} \le \text{cutoff}_{\text{utc}}$$
2. Extract all records for delivery date $D+1$ (24 hourly intervals from `00:00:00Z` to `23:00:00Z`).
3. **Primary Selection (`latest_available`)**: The most recent eligible vintage containing records for delivery day $D+1$.
   - If this vintage contains all 24 hours, status is `"complete"`.
   - If this vintage contains fewer than 24 hours, status is `"incomplete"`, gaps are enumerated in `missing_intervals`, and missing hours have `forecast_mw = None`. **It is never silently replaced by an older vintage.**
4. **Comparison Selection (`latest_complete`)**: The most recent eligible vintage that contains all 24 hours (or `None` if no complete vintage exists).
5. **No Mixing Guarantee**: Forecast records from different `publishTime` vintages are never combined.

### 4.4 Actuals Aggregation Policy
- FUELHH records arrive in half-hourly settlement periods (SPs 1..48).
- For each clock hour starting at $T$ (`HH:00:00Z`):
  $$\text{Actual}_{\text{avg}}(T) = \frac{\text{Gen}(T) + \text{Gen}(T + \text{30m})}{2}$$
- Uniqueness is validated before aggregation. Duplicate `startTime` timestamps raise an immediate exception.
- If an actual interval is missing, no zero-imputation is performed; the interval is marked missing.

---

## 5. Metrics Specification

| Metric | Mathematical Definition | Range / Unit | Handling Edge Cases |
| :--- | :--- | :--- | :--- |
| **MAE** | $\frac{1}{n} \sum_{i=1}^n \|f_i - a_i\|$ | $[0, \infty)$ MW | Returns `None` if $n = 0$ |
| **RMSE** | $\sqrt{\frac{1}{n} \sum_{i=1}^n (f_i - a_i)^2}$ | $[0, \infty)$ MW | Returns `None` if $n = 0$ |
| **Signed Bias** | $\frac{1}{n} \sum_{i=1}^n (f_i - a_i)$ | $(-\infty, \infty)$ MW | $>0$ indicates overforecast, $<0$ underforecast. Returns `None` if $n = 0$ |
| **WAPE** | $\frac{\sum_{i=1}^n \|f_i - a_i\|}{\sum_{i=1}^n a_i} \times 100$ | $[0, \infty)$ % | Returns `None` if $\sum a_i = 0$ or $n = 0$. Never returns `Infinity` or `NaN` |
| **Coverage** | $\frac{n}{N_{\text{expected}}}$ | $[0.0, 1.0]$ ratio | $N_{\text{expected}} = 24$ per day, $744$ for the full January window |

---

## 6. REST API Specification

### `GET /api/health`
Returns system status, application name, version, and server UTC timestamp.

### `GET /api/metadata`
Returns data source attribution, date windows, resolutions, default cutoff, selection policies, metric definitions, and snapshot file provenance.

### `GET /api/overview?cutoff=09:00`
Returns summary metrics for the full January window, expected vs. matched intervals, overall coverage, and a list of daily summary cards.

### `GET /api/deliveries?cutoff=09:00`
Returns a lightweight list of all 31 delivery days, their decision dates, selected publication timestamps, completeness status, and daily MAE/RMSE/Bias/WAPE.

### `GET /api/deliveries/{delivery_date}?cutoff=09:00`
Returns the complete 24-hour interval breakdown for a specific delivery date:
- `startTime`: `2026-01-02T00:00:00Z`
- `forecast_mw`, `actual_mw`, `signed_error_mw`, `absolute_error_mw`
- `publish_time`, `cutoff_utc`, `actual_half_hour_count`
- `selected_vintage` and `latest_complete_vintage` metadata
- `missing_intervals` and daily `metrics`

### `GET /api/deliveries/{delivery_date}/vintages?cutoff=09:00`
Returns all eligible forecast vintages published prior to cutoff, showing interval coverage and distinguishing the selected latest vintage from the latest complete vintage.

### `GET /api/export.csv?cutoff=09:00`
Streams a comma-separated values (CSV) export of all 744 hourly comparison intervals across the month with headers:
`deliveryDate,decisionDate,startTime,forecast,actual,signedError,absoluteError,publishTime,cutoff`

---

## 7. Performance & Verification

- **In-Memory Caching**: Raw JSON files (~3.1 MB) are parsed once during application lifespan startup.
- **Fast Response Times**: Endpoints respond in < 5ms since all alignment and evaluation operations execute in memory.
- **Testing**: 33 unit and integration tests under `backend/tests/` verify domain mapping, timestamp arithmetic, forecast selection, edge cases, error codes, and CSV export.
