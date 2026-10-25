# Implementation Specification

> **Project**: Windline — GB Wind Generation Forecast Analytics<br>
> **Reference**: [ASSUMPTIONS.md](ASSUMPTIONS.md) and [ARCHITECTURE.md](ARCHITECTURE.md)<br>
> **Feasibility Status**: Verified against official Elexon Insights Solution (BMRS) data

---

## 1. Feasibility Summary

The feasibility of retrospective wind generation forecast evaluation across January 2026 was empirically verified against the official Elexon BMRS API:

| Check | Result |
|-------|--------|
| FUELHH stream endpoint reachable | Verified HTTP 200, 48 rows per day for GB wind generation |
| WINDFOR stream endpoint reachable | Verified HTTP 200, exactly 73 hourly intervals per vintage |
| API key required | Public API, no key or subscription required |
| Rate & pagination constraints | Unbounded stream queries supported for historical windows |
| Schema & field types | Verified exact match against documented OpenAPI contract |
| Forecast to actual alignment | 100% of delivery-day hours (744 / 744) joinable on UTC timestamps |
| Forecast vintages | Regular publication history (8 vintages per day across 32 days) |

---

## 2. System Architecture

Windline is packaged as a unified application where FastAPI serves both the deterministic analytical API and the pre-built React single-page application:

```
┌──────────────────────────────────────────────────────────┐
│                   React 19 Frontend SPA                  │
│  • Overview: 31-day KPI metrics, daily trend charts      │
│  • Explorer: Per-day 24h interval review, vintage modal  │
│  • Accuracy: Metric definitions, residual distribution   │
│  • Quality: Vintage audit, zero-imputation guarantees    │
│  • Methodology: Mathematical formulas, BMRS licensing    │
└───────────────────────────┬──────────────────────────────┘
                            │ REST / JSON (/api/*)
┌───────────────────────────▼──────────────────────────────┐
│                  FastAPI Application Core                │
│  • /api/health                                           │
│  • /api/metadata                                         │
│  • /api/overview?cutoff=09:00                            │
│  • /api/deliveries?cutoff=09:00                          │
│  • /api/deliveries/{date}?cutoff=09:00                   │
│  • /api/deliveries/{date}/vintages?cutoff=09:00          │
│  • /api/export.csv?cutoff=09:00                          │
└───────────────────────────┬──────────────────────────────┘
                            │ In-Memory Eager Loading
┌───────────────────────────▼──────────────────────────────┐
│              Audited Historical Data Snapshots           │
│  • data/audit/fuelhh_full.json  (1,488 actual records)   │
│  • data/audit/windfor_full.json (18,688 forecast records)│
│  • data/provenance.json         (Checksums & metadata)   │
└──────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Runtime | Python 3.12 (3.11+ compatible) | Modern standard library typing and `zoneinfo` support |
| Web Framework | FastAPI 0.162+ | High performance ASGI framework with automatic OpenAPI docs |
| Validation | Pydantic v2 | Strict request/response validation and serialization |
| Frontend | React 19 + TypeScript + Vite | Type-safe, reactive single-page dashboard |
| Styling | Vanilla CSS Design System | Curated institutional color tokens and tabular typography |
| Testing | pytest + httpx TestClient | Portably testing domain logic, metrics, and API contracts |

---

## 3. Core Domain Concepts

### 3.1 Decision Date vs. Delivery Date

Day-ahead wholesale electricity procurement commits volume on decision date $D$ for physical delivery on calendar day $D+1$:

```
Decision Date (D)          Delivery Date (D+1)
────────────────           ────────────────────
2026-01-01         →       2026-01-02
2026-01-02         →       2026-01-03
  ...                        ...
2026-01-31         →       2026-02-01
```

- Target decision window: **2026-01-01 through 2026-01-31** (31 decision dates).
- Target delivery window: **2026-01-02 through 2026-02-01** (31 delivery dates).

### 3.2 Decision Cutoff & Anti-Leakage Policy

- Default cutoff: **09:00 Europe/London** (= 09:00 UTC in January).
- A WINDFOR vintage is eligible for decision date $D$ if and only if:
  $$\text{publishTime}_{\text{utc}} \le \text{cutoff}_{\text{utc}}$$
- Any forecast published after cutoff is strictly excluded to prevent hindsight leakage.

### 3.3 Forecast Vintage Selection

For a target delivery date $D+1$ and decision cutoff:
1. Filter all vintages published at or before the decision cutoff.
2. Identify vintages covering delivery day $D+1$ (intervals `00:00:00Z` to `23:00:00Z`).
3. Select the latest eligible vintage as primary. If all 24 delivery hours are present, it is marked `complete`.
4. If the latest eligible vintage covers fewer than 24 hours, it is marked `incomplete`, missing hours are reported with `forecast_mw = None`, and the system does not silently replace or fabricate values.

### 3.4 Interval Alignment & Aggregation

| Dataset | Granularity | Intervals per Day |
|---------|-------------|-------------------|
| WINDFOR | 1 hour | 24 clock hours (00:00 to 23:00 UTC) |
| FUELHH | 30 minutes | 48 settlement periods (SPs 1 to 48) |

For each clock hour $H$ (`YYYY-MM-DDTHH:00:00Z`):
$$\text{Actual}_{\text{avg}}(H) = \frac{\text{Gen}(H\text{:00}) + \text{Gen}(H\text{:30})}{2}$$
$$\text{Signed Error}(H) = \text{Forecast}(H) - \text{Actual}_{\text{avg}}(H)$$
$$\text{Absolute Error}(H) = |\text{Signed Error}(H)|$$

---

## 4. API Endpoints

| Method | Endpoint | Query Parameters | Description |
|--------|----------|------------------|-------------|
| `GET` | `/api/health` | None | Service status, application version, and UTC timestamp |
| `GET` | `/api/metadata` | None | Data provider attribution, date windows, metric definitions |
| `GET` | `/api/overview` | `cutoff` (default: `09:00`) | Aggregate 31-day summary metrics and daily summary cards |
| `GET` | `/api/deliveries` | `cutoff` (default: `09:00`) | List of all 31 delivery days with selected vintages |
| `GET` | `/api/deliveries/{date}` | `cutoff` (default: `09:00`) | 24 hourly intervals with forecast, actual, and errors |
| `GET` | `/api/deliveries/{date}/vintages` | `cutoff` (default: `09:00`) | All eligible publication vintages for the decision date |
| `GET` | `/api/export.csv` | `cutoff` (default: `09:00`) | CSV stream of all 744 hourly comparison intervals |

---

## 5. Directory Structure

```
.
├── .github/workflows/ci.yml       # GitHub Actions CI workflow
├── app.py                         # Unified entrypoint (FastAPI + React bundle)
├── backend/
│   ├── app/
│   │   ├── config.py              # System configuration and constants
│   │   ├── engine.py              # Vintage selection and aggregation engine
│   │   ├── loader.py              # In-memory snapshot loader
│   │   ├── main.py                # FastAPI application definition
│   │   ├── metrics.py             # MAE, RMSE, Signed Bias, WAPE formulas
│   │   ├── models.py              # Pydantic v2 schemas
│   │   ├── routes.py              # REST API endpoints
│   │   └── timestamps.py          # UTC normalization and cutoff construction
│   └── tests/                     # 33 unit and integration tests
├── data/
│   ├── audit/                     # Verified 31-day historical snapshots
│   └── provenance.json            # Dataset provenance and licence metadata
├── docs/
│   ├── ARCHITECTURE.md            # Detailed system design
│   ├── ASSUMPTIONS.md             # Empirical data contract and domain rules
│   ├── DATA_AUDIT.md              # Full-window audit report
│   └── IMPLEMENTATION_PLAN.md     # Engineering specification
├── frontend/                      # React 19 TypeScript application
├── scripts/
│   ├── audit_full_window.py       # Full-window audit script
│   ├── run_tests.py               # Test runner
│   ├── smoke_test.py              # Acceptance checks
│   └── verify_live_server.py      # Live server endpoint verification
├── Dockerfile                     # Multi-stage production container build
├── docker-compose.yml             # Local compose orchestration
├── requirements.txt               # Pinned Python dependencies
└── vercel.json                    # Serverless deployment configuration
```
