# Windline — January 2026 Full-Window Data Audit Report

> **Project**: Windline — Retrospective Wind Forecast Analytics (GB Power Market)  
> **Target Decision Window**: 2026-01-01 through 2026-01-31 (31 decision dates)  
> **Target Delivery Window**: 2026-01-02 through 2026-02-01 (31 delivery dates)  
> **Audit Execution Date**: 2026-10-25  
> **Auditing Script**: [`scripts/audit_full_window.py`](file:///d:/WIND/scripts/audit_full_window.py)  
> **Raw Datasets & Artifacts**: [`data/audit/`](file:///d:/WIND/data/audit)  
> **Audit Status**: ✅ **GO — Full-Window Production Readiness Verified**

---

## Executive Summary

A comprehensive, non-sampled data audit was conducted across the entire target operating window for Windline. Unlike earlier single-day feasibility tests, this audit retrieved and evaluated all raw records from the official Elexon Insights Solution (BMRS) API for every settlement period and forecast publication relevant to January 2026 procurement decisions.

### Key Audit Metrics

| Metric | Target / Expected | Audited / Observed | Completeness | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Delivery Dates Audited** | 31 days (2026-01-02 .. 2026-02-01) | 31 days | 100.0% | ✅ Complete |
| **FUELHH Raw Records (WIND)** | 1,488 (31 days × 48 SPs) | **1,488** | 100.0% | ✅ Zero missing |
| **FUELHH Duplicates / Revisions** | 0 duplicates | **0 duplicates / 0 revisions** | 100.0% | ✅ Pristine |
| **Decision Dates Audited** | 31 days (2026-01-01 .. 2026-01-31) | 31 days | 100.0% | ✅ Complete |
| **WINDFOR Forecast Vintages** | ≥ 1 per decision cutoff | **256 vintages** (8 / day) | 100.0% | ✅ Rich history |
| **WINDFOR Total Forecast Rows** | ~18,000 | **18,688 rows** (73 / vintage) | 100.0% | ✅ Consistent |
| **Pre-Cutoff (≤ 09:00) Vintages** | ≥ 1 per decision date | **3 vintages** on all 31 dates | 100.0% | ✅ Always 3 |
| **Dates with Complete Eligible Forecast** | 31 days | **31 days** (100%) | 100.0% | ✅ Deterministic |
| **Aligned Hourly Comparisons** | 744 hours (31 days × 24 hrs) | **744 comparisons** | **100.0%** | ✅ Perfect join |
| **Comparison Discrepancies / Gaps** | 0 gaps | **0 gaps / 0 nulls** | 100.0% | ✅ No data holes |

---

## 1. Actual Generation Audit (FUELHH)

### 1.1 Query Parameters & HTTP Requests
- **Base Endpoint**: `https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`
- **Authentication**: None required (public REST API)
- **Batching Strategy**: 5 weekly batches (7 days per batch, final batch 3 days) to respect network efficiency:
  - Batch 1: `settlementDateFrom=2026-01-02&settlementDateTo=2026-01-08&fuelType=WIND` (HTTP 200, 336 rows)
  - Batch 2: `settlementDateFrom=2026-01-09&settlementDateTo=2026-01-15&fuelType=WIND` (HTTP 200, 336 rows)
  - Batch 3: `settlementDateFrom=2026-01-16&settlementDateTo=2026-01-22&fuelType=WIND` (HTTP 200, 336 rows)
  - Batch 4: `settlementDateFrom=2026-01-23&settlementDateTo=2026-01-29&fuelType=WIND` (HTTP 200, 336 rows)
  - Batch 5: `settlementDateFrom=2026-01-30&settlementDateTo=2026-02-01&fuelType=WIND` (HTTP 200, 144 rows)
- **Total Rows Returned**: **1,488 rows**

### 1.2 Schema & Record Integrity
Each row contains exactly 7 fields matching the Elexon BMRS OpenAPI schema:
- `dataset`: `"FUELHH"` (string)
- `publishTime`: ISO 8601 UTC timestamp string with `Z` suffix (e.g. `"2026-01-02T00:30:00Z"`)
- `startTime`: ISO 8601 UTC timestamp string with `Z` suffix (e.g. `"2026-01-02T00:00:00Z"`)
- `settlementDate`: `"YYYY-MM-DD"` string
- `settlementPeriod`: integer (1 to 48)
- `fuelType`: `"WIND"` (string)
- `generation`: integer (MW)

### 1.3 Data Quality Findings
- **Interval Completeness**: All 31 delivery days have exactly 48 settlement periods (SPs 1 through 48 present without any gaps).
- **Duplicate startTimes**: **0**. There are exactly 1,488 unique `startTime` timestamps across the 1,488 returned records.
- **Null / Negative Values**: **0** null values, **0** negative generation values.
- **Generation Outturn Range**:
  - Minimum: **1,695 MW**
  - Maximum: **17,805 MW**
  - Mean: **11,284 MW**
- **Revision Patterns**: Each half-hour interval has exactly one record and one `publishTime`. Elexon publishes initial outturns promptly at the close of the settlement period without duplicate superseded rows appearing in the stream endpoint.

---

## 2. Forecast History Audit (WINDFOR)

### 2.1 Query Parameters & HTTP Requests
- **Base Endpoint**: `https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`
- **Batching Strategy**: 32 daily batches covering publication dates `2025-12-31` through `2026-01-31`.
  - Inclusive window: `publishDateTimeFrom={YYYY-MM-DD}T00:00:00Z&publishDateTimeTo={YYYY-MM-DD}T23:59:59Z`
  - All 32 HTTP requests returned HTTP 200.
- **Total Rows Returned**: **18,688 rows**
- **Total Distinct Vintages**: **256 distinct `publishTime` timestamps** (exactly 8 vintages per calendar day).

### 2.2 Schema & Structure per Vintage
Each row contains 4 fields:
- `dataset`: `"WINDFOR"` (string)
- `publishTime`: ISO 8601 UTC timestamp with `Z` suffix
- `startTime`: ISO 8601 UTC timestamp with `Z` suffix
- `generation`: integer (forecast generation in MW)

Every single one of the 256 vintages contains:
- **Exactly 73 hourly intervals** (`startTime` separated by 60 minutes).
- **Zero duplicate startTimes** within any vintage.
- **Zero null or negative generation values**.
- **Horizon**: Spans from $D-1\text{ 21:00 UTC}$ to $D+2\text{ 21:00 UTC}$ (~72–73 hours ahead).

---

## 3. Publication-Time Behaviour & Investigation

### 3.1 Observed Publication Times (Empirical Evidence)
Across the 32 days monitored (2025-12-31 to 2026-01-31), the distribution of publication times was audited:

| Observed UTC Time | Europe/London Local | Occurrence Frequency | Pre-09:00 Cutoff? | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **02:30 UTC** | 02:30 GMT | 32 of 32 days (100%) | ✅ Eligible | Early morning run |
| **04:30 UTC** | 04:30 GMT | 32 of 32 days (100%) | ✅ Eligible | Morning update |
| **07:30 UTC** | 07:30 GMT | 32 of 32 days (100%) | ✅ Eligible | **Latest pre-09:00 vintage** |
| **09:30 UTC** | 09:30 GMT | 32 of 32 days (100%) | ❌ Post-cutoff | Published after 09:00 gate |
| **11:30 UTC** | 11:30 GMT | 31 of 32 days (96.9%) | ❌ Post-cutoff | Standard midday run |
| **12:25 UTC** | 12:25 GMT | 1 of 32 days (3.1%) | ❌ Post-cutoff | Delayed midday publication (on 1 day) |
| **15:30 UTC** | 15:30 GMT | 32 of 32 days (100%) | ❌ Post-cutoff | Afternoon run |
| **18:30 UTC** | 18:30 GMT | 32 of 32 days (100%) | ❌ Post-cutoff | Evening run |
| **22:30 UTC** | 22:30 GMT | 32 of 32 days (100%) | ❌ Post-cutoff | Night run |

### 3.2 Analysis of Documented Schedule vs. Observed Timestamps
Elexon's public wind generation documentation references scheduled updates at nominal times 03:30, 05:30, and 08:30 (the source documentation does not explicitly label a timezone for these update times). In contrast, the live API across January consistently returns forecast publications at 02:30, 04:30, and 07:30 UTC.

1. **Local Time Analysis**: In January, Great Britain operates on Greenwich Mean Time (GMT = UTC+0). Therefore, `02:30Z` represents `02:30` local time in January, not an offset from local time.
2. **Unresolved Schedule Discrepancy**: The 1-hour offset between the published documentation (03:30, 05:30, 08:30) and the observed API timestamps (02:30, 04:30, 07:30) remains an **unresolved schedule discrepancy** between Elexon's narrative web documentation and the actual BMRS API pipeline. (While the documented times match what British Summer Time [BST = UTC+1] nominal clocks would show, without official confirmation of whether documentation reflects summer time or ESO submission vs. BMRS publish lag, this cannot be definitively assumed).
3. **Operational Jitter**: On one occasion (2026-01-20), the midday run was published at 12:25 UTC rather than 11:30 UTC.
4. **Architectural Mandate**: **Never hardcode a publication schedule or expected timestamps.** The system must rely strictly on the recorded `publishTime` from the dataset, performing dynamic timezone-aware comparisons:
   $$\text{publishTime}_{\text{aware}} \le \text{cutoff}_{\text{aware}}$$


---

## 4. Decision-Date Audit & Vintage Selection Policy

### 4.1 Decision vs Delivery Date Relationship
- **Decision Date ($D$)**: Day on which trading / procurement decisions take place (2026-01-01 to 2026-01-31).
- **Delivery Date ($D+1$)**: Calendar day on which power is delivered (2026-01-02 to 2026-02-01).
- **Illustrative Decision Cutoff**: **09:00 Europe/London** (= 09:00:00 UTC in January).

### 4.2 Horizon & Completeness Analysis
To be considered complete for delivery day $D+1$, a forecast vintage must contain all 24 clock-hour intervals from `00:00:00Z` to `23:00:00Z` of delivery day $D+1$.

- **Prior-Day Vintages ($D-1$)**:
  - The latest prior-day vintage (e.g. $D-1\text{ 22:30 UTC}$) extends only until $D+1\text{ 21:00 UTC}$.
  - It covers only **22 of the 24 hours** for delivery day $D+1$ (missing 22:00Z and 23:00Z).
  - Therefore, prior-day vintages are **incomplete** for whole-day procurement decisions.
- **Decision-Day Pre-Cutoff Vintages ($D$)**:
  - Every decision date in January had exactly 3 vintages published prior to 09:00 UTC:
    1. `02:30:00Z` — covers 24/24 delivery hours (plus beyond).
    2. `04:30:00Z` — covers 24/24 delivery hours (plus beyond).
    3. `07:30:00Z` — covers 24/24 delivery hours (plus beyond).

### 4.3 Deterministic Selection Policy
1. Filter all available vintages where $\text{publishTime} \le \text{cutoff\_utc}$.
2. Require that the vintage contains all 24 hourly timestamps for delivery date $D+1$.
3. Select the vintage with the latest `publishTime` satisfying this condition.
4. **Empirical Result**: For **all 31 decision dates**, the latest complete eligible forecast vintage was deterministically and consistently the **`07:30:00Z` vintage**.
5. **No Data Mixing**: The application selects a single coherent physical forecast vintage per decision day. It never mixes intervals across multiple publications and never fills missing intervals with zeroes.

---

## 5. Hourly Alignment & Validation

### 5.1 Alignment Methodology
- **FUELHH Granularity**: 30 minutes (48 settlement periods per day, numbered 1..48).
- **WINDFOR Granularity**: 60 minutes (24 clock hours per day, starting at HH:00:00Z).
- **Aggregation Formula**:
  For clock hour starting at $T$ (e.g. `2026-01-02T14:00:00Z`):
  $$\text{Actual\_Avg}(T) = \frac{\text{Gen}(T) + \text{Gen}(T + \text{30m})}{2}$$
  Where:
  - $\text{Gen}(T)$ corresponds to settlement period $2h + 1$.
  - $\text{Gen}(T + \text{30m})$ corresponds to settlement period $2h + 2$.
  - Interval validation is strictly anchored on timezone-aware UTC ISO timestamps, matching exact hour boundaries.

### 5.2 Alignment Verification Results
- **Delivery Days Aligned**: 31 of 31 days (2026-01-02 to 2026-02-01).
- **Raw Half-Hourly Records Processed**: 1,488 records.
- **Hourly Aggregated Actuals Formed**: 744 hours.
- **Selected Forecast Intervals Matched**: 744 hours.
- **Total Valid Comparisons Produced**: **744 of 744 (100.0%)**.
- **Missing Actual Hours**: **0**.
- **Missing Forecast Hours**: **0**.
- **Duplicate Joins**: **0**.

---

## 6. Audit Artifacts & Reproducibility

All audit artifacts have been persisted in the repository under [`data/audit/`](file:///d:/WIND/data/audit) for permanent reference and automated testing:

1. [`fuelhh_analysis.json`](file:///d:/WIND/data/audit/fuelhh_analysis.json): Per-date record counts, settlement period verification, generation statistics.
2. [`fuelhh_full.json`](file:///d:/WIND/data/audit/fuelhh_full.json): Raw 1,488 actual records for reproducible offline testing.
3. [`windfor_analysis.json`](file:///d:/WIND/data/audit/windfor_analysis.json): Detailed inventory of all 256 vintages and their start/end ranges.
4. [`windfor_full.json`](file:///d:/WIND/data/audit/windfor_full.json): Raw 18,688 forecast records covering the full January decision history.
5. [`publication_time_analysis.json`](file:///d:/WIND/data/audit/publication_time_analysis.json): Statistical breakdown of publication schedules and jitter.
6. [`decision_date_audit.json`](file:///d:/WIND/data/audit/decision_date_audit.json): Decision-by-decision audit showing eligible vintages, candidate selection, and coverage.
7. [`alignment_results.json`](file:///d:/WIND/data/audit/alignment_results.json): Hourly comparison outputs for all 744 hours in scope.
8. [`go_nogo.json`](file:///d:/WIND/data/audit/go_nogo.json): Machine-readable GO/NO-GO audit verdict.

The audit script can be re-run at any time via:
```bash
python scripts/audit_full_window.py
```

---

## 7. Discrepancies, Risks & Explicit Caveats

1. **Configurable Gate Closure Assumption**:
   - The 09:00 Europe/London cutoff is an assumed illustrative day-ahead gate closure.
   - Real market participants may operate against 10:00 (EPEX Day-Ahead auction deadline) or 11:00 (Nord Pool Day-Ahead auction deadline).
   - *Design Implication*: The backend API and frontend UI must support user-configurable cutoffs rather than hardcoding 09:00.
2. **Network Resilience & Latency**:
   - The Elexon API is public and responsive, but upstream maintenance or network spikes can cause occasional timeouts.
   - *Design Implication*: The backend service layer must implement retry with exponential backoff and persistent disk caching for historical windows.
3. **Daylight Saving Time (DST)**:
   - January 2026 is entirely within UTC+0 (GMT). No 23-hour or 25-hour clock-change days occur in January.
   - *Design Implication*: Datetime logic must use standard Python `zoneinfo.ZoneInfo("Europe/London")` to guarantee future extensibility to summer months without regression.

---

## 8. Definitive GO / NO-GO Assessment

| Criterion | Requirement | Result |
| :--- | :--- | :--- |
| **API Availability & Access** | Public Elexon BMRS API reachable without keys or fees | ✅ **PASS** |
| **Dataset Completeness** | 100% January actuals and forecast history available | ✅ **PASS** (1,488 actuals, 256 vintages) |
| **Deterministic Selection** | Clear, uncompromised rule for latest pre-cutoff forecast | ✅ **PASS** (07:30 UTC vintage across all 31 days) |
| **Interval Alignment** | Exact join between half-hourly actuals and hourly forecasts | ✅ **PASS** (744 / 744 hours aligned, 0 gaps) |
| **Data Quality** | Zero nulls, zero duplicates, realistic MW generation | ✅ **PASS** |

### **Final Verdict**: **✅ GO FOR BACKEND IMPLEMENTATION**
The source data contract is fully verified. We have proven that deterministic day-ahead forecast analysis can be built on real Elexon data without synthetic data or artificial assumptions.
