"""Data loader for verified Elexon BMRS snapshot data with validation and in-memory caching."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.app.config import AUDIT_DIR, PROVENANCE_FILE, REPO_ROOT
from backend.app.timestamps import parse_iso_utc, to_utc_iso


@dataclass(frozen=True)
class FuelHHRecord:
    dataset: str
    publish_time: datetime
    start_time: datetime
    settlement_date: str
    settlement_period: int
    fuel_type: str
    generation: float
    start_time_iso: str
    publish_time_iso: str


@dataclass(frozen=True)
class WindforRecord:
    dataset: str
    publish_time: datetime
    start_time: datetime
    generation: float
    start_time_iso: str
    publish_time_iso: str


class DataLoader:
    """Loads, validates, and caches immutable Elexon snapshots in memory."""

    _instance: DataLoader | None = None

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or AUDIT_DIR
        self._fuelhh_by_date: dict[str, list[FuelHHRecord]] = {}
        self._windfor_by_vintage: dict[str, list[WindforRecord]] = {}
        self._sorted_vintages: list[str] = []
        self._validation_report: dict[str, Any] = {}
        self._provenance: dict[str, Any] = {}
        self._is_loaded = False

    @classmethod
    def get_instance(cls, data_dir: Path | None = None) -> DataLoader:
        if cls._instance is None:
            cls._instance = cls(data_dir=data_dir)
            cls._instance.load_all()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful in test isolation)."""
        cls._instance = None

    def load_all(self) -> None:
        """Load and validate all snapshot data."""
        if self._is_loaded:
            return

        self._load_provenance()
        self._load_fuelhh()
        self._load_windfor()
        self._is_loaded = True

    def _load_provenance(self) -> None:
        """Load provenance metadata if present."""
        if PROVENANCE_FILE.exists():
            try:
                with open(PROVENANCE_FILE, "r", encoding="utf-8") as f:
                    self._provenance = json.load(f)
            except Exception:
                self._provenance = {}
        else:
            self._provenance = {}

    def _load_fuelhh(self) -> None:
        """Load and validate FUELHH actual wind generation records."""
        path = self.data_dir / "fuelhh_full.json"
        if not path.exists():
            # Fallback to sample if audit full snapshot is missing
            path = self.data_dir.parent / "sample" / "fuelhh_wind_2026-01-02.json"
            if not path.exists():
                raise FileNotFoundError(f"FUELHH snapshot not found in {self.data_dir} or {self.data_dir.parent / 'sample'}")

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError(f"FUELHH file {path} must contain a JSON array")

        valid_records: list[FuelHHRecord] = []
        by_date: dict[str, list[FuelHHRecord]] = {}
        seen_keys: set[tuple[str, int]] = set()

        total_rows = len(raw_data)
        duplicate_rows = 0
        null_gen_rows = 0
        invalid_type_rows = 0
        wrong_fuel_rows = 0

        for r in raw_data:
            if not isinstance(r, dict):
                invalid_type_rows += 1
                continue

            # Fuel type filter
            fuel_type = r.get("fuelType")
            if fuel_type != "WIND":
                wrong_fuel_rows += 1
                continue

            settlement_date = r.get("settlementDate")
            settlement_period = r.get("settlementPeriod")
            gen_val = r.get("generation")

            if gen_val is None:
                null_gen_rows += 1
                continue

            try:
                gen_float = float(gen_val)
            except (ValueError, TypeError):
                invalid_type_rows += 1
                continue

            try:
                st = parse_iso_utc(r["startTime"])
                pt = parse_iso_utc(r["publishTime"])
                sp_int = int(settlement_period)
            except Exception:
                invalid_type_rows += 1
                continue

            # Check duplicate (settlementDate, settlementPeriod)
            key = (settlement_date, sp_int)
            if key in seen_keys:
                duplicate_rows += 1
                continue
            seen_keys.add(key)

            rec = FuelHHRecord(
                dataset=r.get("dataset", "FUELHH"),
                publish_time=pt,
                start_time=st,
                settlement_date=settlement_date,
                settlement_period=sp_int,
                fuel_type=fuel_type,
                generation=gen_float,
                start_time_iso=to_utc_iso(st),
                publish_time_iso=to_utc_iso(pt),
            )
            valid_records.append(rec)
            by_date.setdefault(settlement_date, []).append(rec)

        # Sort each day's records chronologically by start_time
        for d in by_date:
            by_date[d].sort(key=lambda x: x.start_time)

        self._fuelhh_by_date = by_date
        self._validation_report["fuelhh"] = {
            "source_file": str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path),
            "total_rows_read": total_rows,
            "valid_records": len(valid_records),
            "duplicate_rows": duplicate_rows,
            "null_generation_rows": null_gen_rows,
            "invalid_type_rows": invalid_type_rows,
            "wrong_fuel_rows": wrong_fuel_rows,
            "dates_loaded": sorted(by_date.keys()),
        }

    def _load_windfor(self) -> None:
        """Load and validate WINDFOR forecast records."""
        path = self.data_dir / "windfor_full.json"
        if not path.exists():
            path = self.data_dir.parent / "sample" / "windfor_2026-01-01_pre09.json"
            if not path.exists():
                raise FileNotFoundError(f"WINDFOR snapshot not found in {self.data_dir} or {self.data_dir.parent / 'sample'}")

        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            raise ValueError(f"WINDFOR file {path} must contain a JSON array")

        by_vintage: dict[str, list[WindforRecord]] = {}
        total_rows = len(raw_data)
        duplicate_interval_rows = 0
        null_gen_rows = 0
        invalid_type_rows = 0

        # Track duplicates within each vintage
        seen_per_vintage: dict[str, set[str]] = {}

        for r in raw_data:
            if not isinstance(r, dict):
                invalid_type_rows += 1
                continue

            gen_val = r.get("generation")
            if gen_val is None:
                null_gen_rows += 1
                continue

            try:
                gen_float = float(gen_val)
            except (ValueError, TypeError):
                invalid_type_rows += 1
                continue

            try:
                pt = parse_iso_utc(r["publishTime"])
                st = parse_iso_utc(r["startTime"])
            except Exception:
                invalid_type_rows += 1
                continue

            pt_iso = to_utc_iso(pt)
            st_iso = to_utc_iso(st)

            seen = seen_per_vintage.setdefault(pt_iso, set())
            if st_iso in seen:
                duplicate_interval_rows += 1
                continue
            seen.add(st_iso)

            rec = WindforRecord(
                dataset=r.get("dataset", "WINDFOR"),
                publish_time=pt,
                start_time=st,
                generation=gen_float,
                start_time_iso=st_iso,
                publish_time_iso=pt_iso,
            )
            by_vintage.setdefault(pt_iso, []).append(rec)

        # Sort each vintage by start_time
        for pt_iso in by_vintage:
            by_vintage[pt_iso].sort(key=lambda x: x.start_time)

        sorted_vintages = sorted(by_vintage.keys())

        self._windfor_by_vintage = by_vintage
        self._sorted_vintages = sorted_vintages
        self._validation_report["windfor"] = {
            "source_file": str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path),
            "total_rows_read": total_rows,
            "total_vintages": len(sorted_vintages),
            "duplicate_interval_rows": duplicate_interval_rows,
            "null_generation_rows": null_gen_rows,
            "invalid_type_rows": invalid_type_rows,
            "earliest_publish_time": sorted_vintages[0] if sorted_vintages else None,
            "latest_publish_time": sorted_vintages[-1] if sorted_vintages else None,
        }

    # Public accessors
    def get_actuals_for_date(self, settlement_date: str) -> list[FuelHHRecord]:
        """Return all valid half-hourly FUELHH actual records for a delivery date."""
        self.load_all()
        return self._fuelhh_by_date.get(settlement_date, [])

    def get_all_vintages(self) -> dict[str, list[WindforRecord]]:
        """Return dictionary mapping publish_time_iso to list of WindforRecord."""
        self.load_all()
        return self._windfor_by_vintage

    def get_sorted_vintage_keys(self) -> list[str]:
        """Return all distinct publishTime strings in chronological order."""
        self.load_all()
        return self._sorted_vintages

    def get_validation_report(self) -> dict[str, Any]:
        """Return summary of data validation findings and counts."""
        self.load_all()
        return self._validation_report

    def get_provenance(self) -> dict[str, Any]:
        """Return provenance metadata."""
        self.load_all()
        return self._provenance
