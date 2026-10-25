# Assumptions & Verified Data Contract

> **Project**: Windline — GB Wind Generation Forecast Analytics  
> **Status**: Full-Window Data Audit Complete (all 31 January 2026 dates verified)  
> **Last Verified**: 2026-10-25 via [`scripts/audit_full_window.py`](file:///d:/WIND/scripts/audit_full_window.py)  
> **Audit Report**: [`docs/DATA_AUDIT.md`](file:///d:/WIND/docs/DATA_AUDIT.md)  
> **Verdict**: ✅ **GO — Production Ready**

---

## 1. Data Source

| Item | Specification | Verified Status |
| :--- | :--- | :--- |
| **API Provider** | Elexon Insights Solution (BMRS) | ✅ Confirmed via live REST calls across all 31 delivery days |
| **API Key / Credentials** | None required (public REST API) | ✅ Confirmed; no auth headers needed |
| **Rate / Payload Limits** | Stream endpoints return unbounded JSON arrays | ✅ 5 multi-day batches fetched 1,488 actuals; 32 batches fetched 18,688 forecasts |
| **Base URL** | `https://data.elexon.co.uk/bmrs/api/v1` | ✅ Official documented endpoint base |

---

## 2. Datasets & Empirical Contracts

### 2.1 FUELHH — Half-Hourly Actual Wind Generation

| Item | Contract | Empirical Evidence Across January 2026 |
| :--- | :--- | :--- |
| **Endpoint** | `/datasets/FUELHH/stream` | ✅ 5 of 5 HTTP batches returned 200 OK |
| **Filter Parameters** | `settlementDateFrom`, `settlementDateTo` (`YYYY-MM-DD`), `fuelType=WIND` | ✅ Filtered cleanly to GB wind generation only |
| **Total Rows** | 1,488 expected ($31 \text{ days} \times 48 \text{ SPs}$) | ✅ **Exactly 1,488 rows returned (100.0% complete)** |
| **Fields Verified** | `dataset`, `publishTime`, `startTime`, `settlementDate`, `settlementPeriod`, `fuelType`, `generation` | ✅ 7 fields confirmed across all 1,488 records |
| **Timestamp Format** | ISO 8601 UTC with `Z` suffix (e.g. `2026-01-02T23:30:00Z`) | ✅ Strictly UTC timestamps |
| **Settlement Periods** | Integers 1 to 48 per delivery day | ✅ All 31 delivery days contain complete SP 1–48 sequences |
| **Generation Unit** | MW (integer) | ✅ Values range from 1,695 MW to 17,805 MW (mean: 11,284 MW) |
| **Duplicates / Revisions** | Zero duplicate `startTime` timestamps | ✅ Exactly 1,488 unique `startTime` values (0 duplicates, 0 nulls, 0 revisions) |

### 2.2 WINDFOR — Wind Generation Forecast

| Item | Contract | Empirical Evidence Across January 2026 |
| :--- | :--- | :--- |
| **Endpoint** | `/datasets/WINDFOR/stream` | ✅ 32 of 32 daily HTTP batches returned 200 OK |
| **Filter Parameters** | `publishDateTimeFrom`, `publishDateTimeTo` (ISO datetime with `Z`) | ✅ Clean time-bounded publication queries |
| **Total Records** | ~18,000 expected | ✅ **18,688 rows returned** across 256 vintages |
| **Vintage Structure** | Exactly 8 publication vintages per calendar day | ✅ 256 vintages ($32 \text{ days} \times 8 \text{ vintages/day}$) |
| **Intervals per Vintage** | 73 hourly intervals ($T-3\text{h}$ to $T+70\text{h}$) | ✅ Every single one of the 256 vintages has exactly 73 hourly intervals |
| **Publication Times** | Regular schedule: 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC | ✅ Verified on 31/32 days; 1 day observed jitter at 12:25 UTC |
| **Granularity** | 1 hour (consecutive `startTime` values differ by 3600 seconds) | ✅ Strictly hourly intervals starting at `HH:00:00Z` |
| **Quality** | Zero nulls, zero duplicates within any vintage | ✅ 100% complete records across all 256 vintages |

---

## 3. Decision Framework & Vintage Selection

| Item | Rule | Empirical Finding & Rationale |
| :--- | :--- | :--- |
| **Decision Date ($D$)** | Calendar date on which day-ahead procurement occurs | In-scope: 2026-01-01 through 2026-01-31 (31 dates) |
| **Delivery Date ($D+1$)** | Calendar date for which power is procured | In-scope: 2026-01-02 through 2026-02-01 (31 dates) |
| **Decision Cutoff** | **09:00 Europe/London** (default assumption, configurable) | In January, Europe/London is GMT (UTC+0). 09:00 local = 09:00:00 UTC. |
| **Eligible Forecast Vintages** | Any vintage where $\text{publishTime} \le \text{cutoff\_utc}$ | ✅ On every single January day, exactly 3 vintages (`02:30`, `04:30`, `07:30` UTC) are eligible |
| **Completeness Requirement** | Must contain all 24 clock-hour intervals of delivery date $D+1$ | Prior-day vintages (e.g. $D-1\text{ 22:30 UTC}$) only cover 22/24 hours of $D+1$. Morning-of vintages cover 24/24. |
| **Selected Default Vintage** | Latest complete eligible vintage prior to cutoff | ✅ **07:30:00Z vintage** selected deterministically on all 31 decision dates |
| **No Mixing Rule** | Never mix intervals from different vintages; never fill missing intervals with 0 | Enforced strictly in alignment logic |

---

## 4. Alignment & Comparison Methodology

| Item | Specification | Empirical Audit Result |
| :--- | :--- | :--- |
| **Granularity Difference** | FUELHH is half-hourly (30 min); WINDFOR is hourly (60 min) | Resolution ratio = 2:1 |
| **Hourly Aggregation Formula** | $\text{Actual\_Avg}(H) = \frac{\text{Gen}(H\text{:00}) + \text{Gen}(H\text{:30})}{2}$ | Standard GB power market convention for hourly settlement comparisons |
| **Timestamp Anchoring** | Matching on timezone-aware UTC hour boundaries (`YYYY-MM-DDTHH:00:00Z`) | Eliminates ambiguity from settlement period indices |
| **Alignment Yield** | 744 expected comparisons ($31 \text{ days} \times 24 \text{ hours}$) | ✅ **744 of 744 comparisons produced (100.0%)** |
| **Missing Hours / Gaps** | 0 expected | ✅ **0 missing actual hours, 0 missing forecast hours** |
| **Duplicate Joins** | 0 duplicate joins | ✅ **0 duplicate joins** across the entire window |

---

## 5. Scope Boundaries & Anti-Assumptions

These points are explicitly **not** assumed and remain parameterized or monitored:

1. **Configurable Gate Closure**: The 09:00 Europe/London cutoff is an assumed illustrative day-ahead gate closure, not a statutory market-wide constant. The production architecture must support user-selected cutoffs.
2. **Alternative Vintages**: While the latest-before-cutoff (07:30 UTC) is the primary default, the UI and API will expose all eligible morning vintages (`02:30`, `04:30`, `07:30`) to allow forecast evolution analysis.
3. **No Hardcoded Timestamps & Unresolved Schedule Discrepancy**: While the Elexon narrative web documentation mentions updates at nominal times 03:30, 05:30, and 08:30 (without an explicit timezone label in the documentation), the real API consistently returns 02:30, 04:30, and 07:30 UTC (with explicit trailing 'Z'). In January, Great Britain operates on GMT (UTC+0). This 1-hour discrepancy between documentation and API reality is documented as an unresolved schedule discrepancy. The code must never hardcode times and must evaluate each recorded `publishTime` as a timezone-aware timestamp against the cutoff.
4. **No BST Clock Transitions**: January 2026 is entirely within Greenwich Mean Time (UTC+0). Daylight saving shifts (23-hour or 25-hour days in March/October) do not affect this dataset, but all code uses standard `zoneinfo` objects to guarantee compatibility.
5. **Zero External Infrastructure Dependencies**: No databases, paid APIs, Redis instances, or AI tokens are required. Caching is purely local file-based / in-memory.

