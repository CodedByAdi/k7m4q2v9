# Implementation Plan

> **Project**: Windline — GB Wind Generation Forecast Analytics
> **Prerequisite**: [ASSUMPTIONS.md](file:///d:/WIND/docs/ASSUMPTIONS.md) reviewed and accepted
> **GO / NO-GO**: ✅ **GO** — confirmed by live API tests on 2026-10-25

---

## 0. Feasibility Summary

| Check | Result |
|-------|--------|
| FUELHH stream endpoint reachable | ✅ HTTP 200, 48 rows for 2026-01-02 |
| WINDFOR stream endpoint reachable | ✅ HTTP 200, 219 rows (3 vintages) for 2026-01-01 pre-09:00 |
| API key required | ❌ No — public API |
| Pagination / row limits | None on stream endpoints |
| Fields and types match documented contract | ✅ Verified via live response inspection |
| Forecast → actual alignment feasible | ✅ 24/24 delivery-day hours joinable |
| Complete forecast vintages available | ✅ 73 hourly intervals per vintage |

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                        React Frontend                     │
│  • Decision-date selector (calendar, 2026-01-01..31)     │
│  • Cutoff time selector (default 09:00 Europe/London)    │
│  • Forecast vs actual comparison chart                    │
│  • Error metrics dashboard (MAE, RMSE, bias)             │
│  • Vintage evolution view                                 │
└───────────────────────┬──────────────────────────────────┘
                        │ REST / JSON
┌───────────────────────┴──────────────────────────────────┐
│                    Python Backend (FastAPI)                │
│  • /api/decision-dates          — list available dates    │
│  • /api/forecast/{date}         — eligible forecast(s)    │
│  • /api/actual/{date}           — actual generation       │
│  • /api/comparison/{date}       — aligned forecast+actual │
│  • /api/metrics/{date}          — error statistics        │
│  Upstream: Elexon BMRS API (read-only, no key)           │
└──────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Backend | Python 3.11+ / FastAPI | Async HTTP, fast JSON, type hints |
| HTTP client | `httpx` (async) | Connection pooling, timeout control |
| Datetime handling | `zoneinfo` (stdlib) + `datetime` | No pytz dependency |
| Frontend | React (Vite) | Modern DX, fast HMR |
| Charts | Recharts or Plotly.js | Good time-series support |
| Caching | In-memory LRU or file-based | Avoid hammering Elexon on repeated queries |
| Testing | pytest + pytest-asyncio | Backend unit/integration tests |

### External Dependencies

- **Elexon BMRS API** — free, public, no key, no subscription
- No database required (data fetched on demand, optionally cached)
- No AI/ML service
- No paid third-party APIs

---

## 2. Core Concepts

### 2.1 Decision Date vs Delivery Date

```
Decision Date (D)          Delivery Date (D+1)
────────────────           ────────────────────
2026-01-01         →       2026-01-02
2026-01-02         →       2026-01-03
  ...                        ...
2026-01-31         →       2026-02-01
```

A **decision** is made on date D to procure energy for delivery on D+1.
The forecast used must have been **published before** the decision cutoff on D.

### 2.2 Decision Cutoff

- **Default**: 09:00 Europe/London (= 09:00 UTC in January)
- **Nature**: Configurable assumption, not a fixed market rule
- **Implementation**: The cutoff is a `time` + `timezone` pair applied to the decision date to produce a UTC `datetime` threshold
- **Rule**: A WINDFOR vintage is eligible if `publishTime <= cutoff_datetime_utc`

### 2.3 Forecast Vintage Selection

For a given decision date D and cutoff time T:

1. Query WINDFOR with `publishDateTimeFrom` = start of D, `publishDateTimeTo` = T (in UTC)
2. Group returned rows by `publishTime` — each group is a **vintage**
3. Select the **latest** vintage (highest `publishTime` ≤ T)
4. Extract the rows where `startTime` falls within the delivery day D+1 (00:00–23:00 UTC for January)

> **Open question**: Should the user be able to select earlier vintages
> for comparison? → Yes, expose all eligible vintages in the API response.

### 2.4 Interval Alignment

| Dataset | Granularity | Intervals per day |
|---------|------------|-------------------|
| WINDFOR | 1 hour | 24 (00:00–23:00 UTC) |
| FUELHH | 30 min | 48 (SP 1–48, 00:00–23:30 UTC) |

**Alignment strategy**:

```python
# For each clock hour H on the delivery day:
#   actual_mw = mean(FUELHH[H:00], FUELHH[H:30])
#   forecast_mw = WINDFOR[H:00]
#   error_mw = forecast_mw - actual_mw
```

This produces 24 aligned (forecast, actual) pairs per delivery day.

---

## 3. API Design

### 3.1 Endpoints

#### `GET /api/decision-dates`

Returns the list of valid decision dates in scope.

```json
{
  "dates": ["2026-01-01", "2026-01-02", ..., "2026-01-31"],
  "deliveryDates": ["2026-01-02", "2026-01-03", ..., "2026-02-01"]
}
```

#### `GET /api/forecast/{decision_date}`

Query params: `cutoff` (optional, default `09:00`), `tz` (optional, default `Europe/London`)

Returns all eligible forecast vintages and their hourly values for the delivery day.

```json
{
  "decisionDate": "2026-01-01",
  "deliveryDate": "2026-01-02",
  "cutoffUtc": "2026-01-01T09:00:00Z",
  "vintages": [
    {
      "publishTime": "2026-01-01T07:30:00Z",
      "selected": true,
      "intervals": [
        {"startTime": "2026-01-02T00:00:00Z", "forecastMw": 18781},
        ...
      ]
    },
    ...
  ]
}
```

#### `GET /api/actual/{delivery_date}`

Returns half-hourly actuals and hourly aggregation for the delivery day.

```json
{
  "deliveryDate": "2026-01-02",
  "halfHourly": [...],
  "hourly": [
    {"startTime": "2026-01-02T00:00:00Z", "actualMw": 15367},
    ...
  ]
}
```

#### `GET /api/comparison/{decision_date}`

Returns aligned forecast vs actual with per-interval errors.

```json
{
  "decisionDate": "2026-01-01",
  "deliveryDate": "2026-01-02",
  "selectedVintage": "2026-01-01T07:30:00Z",
  "intervals": [
    {
      "startTime": "2026-01-02T00:00:00Z",
      "forecastMw": 18781,
      "actualMw": 15367,
      "errorMw": 3414,
      "errorPct": 22.2
    },
    ...
  ],
  "metrics": {
    "mae": 1234.5,
    "rmse": 1567.8,
    "bias": 456.7,
    "count": 24
  }
}
```

### 3.2 Error Handling

| Scenario | Handling |
|----------|---------|
| No forecast vintage available before cutoff | Return empty `vintages` array with explanatory message |
| Missing forecast intervals for delivery day | Include gap list in response; partial metrics still computed |
| Missing actual intervals | Flag incomplete hours; exclude from error metrics |
| Elexon API timeout / error | Return 502 with upstream error details |
| Date outside scope | Return 400 with valid date range |

---

## 4. Handling Edge Cases

### 4.1 Missing Forecast Intervals

Observed: Each WINDFOR vintage covers ~73 hourly intervals spanning ~3 calendar days. For a delivery day of 24 hours, we expect all 24 to be present.

**If any are missing**: Report the gap count and compute metrics only on available pairs.

### 4.2 Actual-Generation Revisions

Observed: FUELHH returns one row per settlement period with no duplicates. If future data shows revisions (multiple rows per SP), the implementation should:

1. Prefer the row with the **latest** `publishTime`
2. Log when revisions are detected

### 4.3 Forecast Vintage Completeness

Observed: All 3 vintages in the test window had exactly 73 intervals and no duplicates. The system should still verify completeness per vintage and flag anomalies.

### 4.4 Settlement Day Boundary

GB settlement days run midnight-to-midnight UTC in winter (GMT). Settlement period 1 starts at 00:00 UTC. This aligns cleanly with WINDFOR hourly boundaries.

> **Note**: During BST (late March–late October), settlement days start at 23:00 UTC the previous day. This is out of scope for January but should be accounted for in a general implementation.

---

## 5. Implementation Phases

### Phase 1: Backend Core (Current focus after GO)

- [ ] Python project structure with FastAPI
- [ ] Elexon API client module (`elexon.py`)
  - `fetch_fuelhh(settlement_date, fuel_type="WIND")`
  - `fetch_windfor(publish_from, publish_to)`
- [ ] Domain logic module (`domain.py`)
  - `get_eligible_vintages(decision_date, cutoff_time, tz)`
  - `select_latest_vintage(vintages)`
  - `align_forecast_actual(forecast, actual)`
  - `compute_metrics(aligned)`
- [ ] API routes (`routes.py`)
- [ ] Response caching (LRU or file-based)
- [ ] Unit tests with recorded/mocked API responses

### Phase 2: Frontend

- [ ] Vite + React project setup
- [ ] Decision date picker component
- [ ] Forecast vs actual time-series chart
- [ ] Error metrics panel
- [ ] Vintage selector (dropdown for comparing vintages)
- [ ] Responsive layout

### Phase 3: Polish

- [ ] Loading states and error boundaries
- [ ] Docker Compose for full-stack local dev
- [ ] README with setup instructions
- [ ] Optional: batch analysis view across all 31 decision dates

---

## 6. Directory Structure (Proposed)

```
WIND/
├── docs/
│   ├── ASSUMPTIONS.md
│   └── IMPLEMENTATION_PLAN.md
├── scripts/
│   └── inspect_elexon.py          # This feasibility test
├── data/
│   └── sample/                    # Saved API responses
│       ├── fuelhh_wind_2026-01-02.json
│       └── windfor_2026-01-01_pre09.json
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app
│   │   ├── config.py              # Settings, cutoff defaults
│   │   ├── elexon.py              # Elexon API client
│   │   ├── domain.py              # Business logic
│   │   ├── routes.py              # API endpoints
│   │   └── models.py              # Pydantic response models
│   ├── tests/
│   │   ├── fixtures/              # Recorded API responses
│   │   ├── test_elexon.py
│   │   ├── test_domain.py
│   │   └── test_routes.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.js
└── README.md
```

---

## 7. Key Verified Facts (from feasibility test)

| Fact | Value |
|------|-------|
| FUELHH fields | `dataset`, `publishTime`, `startTime`, `settlementDate`, `settlementPeriod`, `fuelType`, `generation` |
| WINDFOR fields | `dataset`, `publishTime`, `startTime`, `generation` |
| FUELHH per day | 48 half-hourly rows (SP 1–48) |
| WINDFOR per vintage | 73 hourly intervals (~3 days ahead) |
| WINDFOR vintages in 9h window | 3 (at ~2.5h intervals) |
| Generation unit | MW (integer) |
| Timestamp format | ISO 8601 UTC, `Z`-terminated |
| FUELHH `settlementDate` format | `YYYY-MM-DD` |
| API authentication | None required |
| Stream endpoint limits | None (unlimited rows) |
| Joinable hours (test) | 24/24 delivery-day hours aligned |
