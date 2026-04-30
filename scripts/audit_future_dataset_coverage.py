#!/usr/bin/env python3
"""Audit standalone della copertura temporale BioCube per inferenza futura.

Produce un report leggibile per capire:
- quali file sorgente sono presenti;
- che copertura temporale hanno;
- se la milestone V1 (luglio 2020 -> dicembre 2021) è fattibile;
- quali sorgenti bloccano input e confronto osservato.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODEL_SURFACE_VARS = ["t2m", "msl", "slt", "z", "u10", "v10", "lsm"]
MODEL_EDAPHIC_VARS = ["swvl1", "swvl2", "stl1", "stl2"]
MODEL_ATMOS_VARS = ["z", "t", "u", "v", "q"]
MODEL_VEGETATION_VARS = ["NDVI"]
MODEL_AGRICULTURE_VARS = ["Agriculture", "Arable", "Cropland"]
MODEL_FOREST_VARS = ["Forest"]
MODEL_SPECIES_VARS = [
    "1340361",
    "1340503",
    "1536449",
    "1898286",
    "1920506",
    "2430567",
    "2431885",
    "2433433",
    "2434779",
    "2435240",
    "2435261",
    "2437394",
    "2441454",
    "2473958",
    "2491534",
    "2891770",
    "3034825",
    "4408498",
    "5218786",
    "5219073",
    "5219173",
    "5219219",
    "5844449",
    "8002952",
    "8077224",
    "8894817",
    "8909809",
    "9809229",
]

MODEL_SOURCE_FILES = {
    "surface": ("Copernicus/ERA5-monthly/era5-single/era5_single.nc", MODEL_SURFACE_VARS),
    "edaphic": ("Copernicus/ERA5-monthly/era5-edaphic/era5-edaphic-0.nc", MODEL_EDAPHIC_VARS),
    "atmos": ("Copernicus/ERA5-monthly/era5-pressure/era5_pressure.nc", MODEL_ATMOS_VARS),
    "climate_a": (
        "Copernicus/ERA5-monthly/era5-climate-energy-moisture/era5-climate-energy-moisture-0.nc",
        ["smlt", "tp", "csfr", "avg_sdswrf", "avg_snswrf", "avg_snlwrf", "avg_tprate", "avg_sdswrfcs"],
    ),
    "climate_b": (
        "Copernicus/ERA5-monthly/era5-climate-energy-moisture/era5-climate-energy-moisture-1.nc",
        ["sd", "t2m", "d2m"],
    ),
    "species": ("Species/europe_species.parquet", MODEL_SPECIES_VARS),
    "land_ndvi_csv": ("Land/Europe_ndvi_monthly_un_025.csv", MODEL_VEGETATION_VARS),
    "land_vegetation_dynamic": ("Copernicus/ERA5-monthly/era5-land-vegetation/data_stream-moda.nc", []),
    "land_vegetation_cover_high": ("Copernicus/ERA5-monthly/era5-land-vegetation/cvh.nc", []),
    "land_vegetation_cover_low": ("Copernicus/ERA5-monthly/era5-land-vegetation/cvl.nc", []),
    "land_vegetation_type_high": ("Copernicus/ERA5-monthly/era5-land-vegetation/tvh.nc", []),
    "land_vegetation_type_low": ("Copernicus/ERA5-monthly/era5-land-vegetation/tvl.nc", []),
    "agriculture_csv": ("Agriculture/Europe_combined_agriculture_data.csv", MODEL_AGRICULTURE_VARS),
    "forest_csv": ("Forest/Europe_forest_data.csv", MODEL_FOREST_VARS),
}

OPTIONAL_MODEL_SOURCE_KEYS = {
    "land_vegetation_dynamic",
    "land_ndvi_csv",
    "land_vegetation_cover_high",
    "land_vegetation_cover_low",
    "land_vegetation_type_high",
    "land_vegetation_type_low",
    "agriculture_csv",
    "forest_csv",
}


def load_project_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def require_path(env_name: str, create: bool = False) -> Path:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {env_name}")
    path = Path(value).expanduser()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    elif not path.exists():
        raise FileNotFoundError(f"Percorso non trovato per {env_name}: {path}")
    return path


def normalize_input_mode(input_mode: str) -> str:
    value = (input_mode or "all").strip().lower()
    if value not in {"clean", "all"}:
        raise ValueError(f"input_mode non valido: {input_mode}. Usa 'clean' oppure 'all'.")
    return value


def to_month_start(value: str | pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(value).to_period("M").to_timestamp()


def shift_month(value: pd.Timestamp, months: int) -> pd.Timestamp:
    return to_month_start(value) + pd.DateOffset(months=months)


def resolve_source_paths(biocube_dir: Path) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    for key, (relative_path, _) in MODEL_SOURCE_FILES.items():
        path = biocube_dir / relative_path
        if not path.exists():
            if key in OPTIONAL_MODEL_SOURCE_KEYS:
                continue
            raise FileNotFoundError(f"Sorgente mancante per {key}: {path}")
        resolved[key] = path
    return resolved


def month_number_from_value(value: Any) -> int:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("Valore mese vuoto")
    if isinstance(value, str):
        clean = value.strip()
        if clean.isdigit():
            month_int = int(clean)
            if 1 <= month_int <= 12:
                return month_int
        month_candidate = pd.to_datetime(clean, errors="coerce")
        if pd.notna(month_candidate):
            return int(month_candidate.month)
        normalized = clean.lower()
        month_lookup = {
            "jan": 1,
            "january": 1,
            "gen": 1,
            "gennaio": 1,
            "feb": 2,
            "february": 2,
            "febbraio": 2,
            "mar": 3,
            "march": 3,
            "marzo": 3,
            "apr": 4,
            "april": 4,
            "aprile": 4,
            "may": 5,
            "maggio": 5,
            "jun": 6,
            "june": 6,
            "giu": 6,
            "giugno": 6,
            "jul": 7,
            "july": 7,
            "lug": 7,
            "luglio": 7,
            "aug": 8,
            "august": 8,
            "ago": 8,
            "agosto": 8,
            "sep": 9,
            "sept": 9,
            "september": 9,
            "set": 9,
            "settembre": 9,
            "oct": 10,
            "october": 10,
            "ott": 10,
            "ottobre": 10,
            "nov": 11,
            "november": 11,
            "novembre": 11,
            "dec": 12,
            "december": 12,
            "dic": 12,
            "dicembre": 12,
        }
        if normalized in month_lookup:
            return month_lookup[normalized]
    month_candidate = pd.to_datetime(value, errors="coerce")
    if pd.notna(month_candidate):
        return int(month_candidate.month)
    raise ValueError(f"Impossibile interpretare il mese NDVI: {value}")


def scan_netcdf_month_coverage(path: Path) -> dict[str, Any]:
    with xr.open_dataset(path, engine="netcdf4") as ds:
        if "valid_time" not in ds.coords:
            return {
                "kind": "static_or_non_temporal_netcdf",
                "available_months": set(),
                "min_month": None,
                "max_month": None,
            }
        months = pd.to_datetime(ds["valid_time"].values).to_period("M").to_timestamp()
    month_set = {to_month_start(month) for month in months}
    return {
        "kind": "monthly_netcdf",
        "available_months": month_set,
        "min_month": min(month_set) if month_set else None,
        "max_month": max(month_set) if month_set else None,
    }


def scan_species_month_coverage(path: Path) -> dict[str, Any]:
    species_df = pd.read_parquet(path, columns=["Timestamp"])
    months = pd.to_datetime(species_df["Timestamp"]).dt.to_period("M").dt.to_timestamp()
    month_set = {to_month_start(month) for month in months.dropna().tolist()}
    return {
        "kind": "monthly_species_parquet",
        "available_months": month_set,
        "min_month": min(month_set) if month_set else None,
        "max_month": max(month_set) if month_set else None,
    }


def scan_forest_year_coverage(path: Path) -> dict[str, Any]:
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    years = sorted({int(match.group(1)) for name in columns if (match := re.match(r"Forest_(\d{4})$", str(name)))})
    return {
        "kind": "annual_forest_csv",
        "available_years": years,
        "min_month": pd.Timestamp(f"{years[0]}-01-01") if years else None,
        "max_month": pd.Timestamp(f"{years[-1]}-12-01") if years else None,
    }


def scan_agriculture_year_coverage(path: Path) -> dict[str, Any]:
    columns = pd.read_csv(path, nrows=0).columns.tolist()
    years = sorted({int(match.group(1)) for name in columns if (match := re.match(r"Agri_(\d{4})$", str(name)))})
    return {
        "kind": "annual_agriculture_csv",
        "available_years": years,
        "min_month": pd.Timestamp(f"{years[0]}-01-01") if years else None,
        "max_month": pd.Timestamp(f"{years[-1]}-12-01") if years else None,
    }


def scan_ndvi_month_coverage(path: Path) -> dict[str, Any]:
    ndvi_frame = pd.read_csv(path)
    date_column = next(
        (name for name in ("Timestamp", "timestamp", "Date", "date", "MonthDate", "month_date", "valid_time") if name in ndvi_frame.columns),
        None,
    )
    year_column = next((name for name in ("Year", "year", "YEAR", "Anno", "anno") if name in ndvi_frame.columns), None)
    month_column = next((name for name in ("Month", "month", "MONTH", "Mese", "mese") if name in ndvi_frame.columns), None)

    month_set: set[pd.Timestamp] = set()
    if year_column and month_column:
        years = pd.to_numeric(ndvi_frame[year_column], errors="coerce")
        month_numbers = ndvi_frame[month_column].map(month_number_from_value)
        for year_value, month_value in zip(years, month_numbers):
            if pd.isna(year_value):
                continue
            month_set.add(pd.Timestamp(year=int(year_value), month=int(month_value), day=1))
    elif date_column:
        months = pd.to_datetime(ndvi_frame[date_column], errors="coerce").dropna().dt.to_period("M").dt.to_timestamp()
        month_set = {to_month_start(month) for month in months.tolist()}
    else:
        columns = ndvi_frame.columns.tolist()
        month_pattern = re.compile(r"(20\d{2})[-_]?([01]?\d)")
        for name in columns:
            match = month_pattern.search(str(name))
            if match is None:
                continue
            month_int = int(match.group(2))
            if 1 <= month_int <= 12:
                month_set.add(pd.Timestamp(year=int(match.group(1)), month=month_int, day=1))

    return {
        "kind": "monthly_ndvi_csv",
        "available_months": month_set,
        "min_month": min(month_set) if month_set else None,
        "max_month": max(month_set) if month_set else None,
    }


def scan_source_time_coverage(source_key: str, path: Path) -> dict[str, Any]:
    if source_key in {"surface", "edaphic", "atmos", "climate_a", "climate_b", "land_vegetation_dynamic"}:
        return scan_netcdf_month_coverage(path)
    if source_key == "species":
        return scan_species_month_coverage(path)
    if source_key == "forest_csv":
        return scan_forest_year_coverage(path)
    if source_key == "agriculture_csv":
        return scan_agriculture_year_coverage(path)
    if source_key == "land_ndvi_csv":
        return scan_ndvi_month_coverage(path)
    return {
        "kind": "static_or_auxiliary_file",
        "available_months": set(),
        "min_month": None,
        "max_month": None,
    }


def months_missing_from_coverage(coverage: dict[str, Any], months: list[pd.Timestamp]) -> list[pd.Timestamp]:
    if "available_years" in coverage:
        available_years = set(int(year) for year in coverage["available_years"])
        return [month for month in months if int(month.year) not in available_years]
    available_months = coverage.get("available_months", set())
    return [month for month in months if to_month_start(month) not in available_months]


def required_future_source_checks(source_paths: dict[str, Path], input_mode: str = "all") -> list[dict[str, Any]]:
    input_mode = normalize_input_mode(input_mode)
    checks = [
        {"label": "surface", "source_key": "surface", "required": True},
        {"label": "edaphic", "source_key": "edaphic", "required": True},
        {"label": "atmospheric", "source_key": "atmos", "required": True},
        {"label": "climate_a", "source_key": "climate_a", "required": True},
        {"label": "climate_b", "source_key": "climate_b", "required": True},
    ]
    if input_mode == "all":
        vegetation_key = "land_ndvi_csv" if "land_ndvi_csv" in source_paths else "land_vegetation_dynamic"
        checks.extend(
            [
                {"label": "vegetation", "source_key": vegetation_key, "required": True},
                {"label": "agriculture", "source_key": "agriculture_csv", "required": True},
                {"label": "forest", "source_key": "forest_csv", "required": True},
            ]
        )
    return checks


def assess_future_inference_availability(
    source_paths: dict[str, Path],
    *,
    input_prev: pd.Timestamp,
    input_last: pd.Timestamp,
    forecast_month: pd.Timestamp,
    input_mode: str = "all",
) -> dict[str, Any]:
    checks = required_future_source_checks(source_paths, input_mode=input_mode)
    input_months = [to_month_start(input_prev), to_month_start(input_last)]
    compare_months = [to_month_start(input_last), to_month_start(forecast_month)]
    source_reports = []
    missing_input: list[str] = []
    missing_compare: list[str] = []

    for check in checks:
        source_key = check["source_key"]
        path = source_paths.get(source_key)
        if path is None or not path.exists():
            source_reports.append(
                {
                    "label": check["label"],
                    "source_key": source_key,
                    "path": None if path is None else str(path),
                    "exists": False,
                    "input_missing_months": [month.strftime("%Y-%m") for month in input_months],
                    "compare_missing_months": [month.strftime("%Y-%m") for month in compare_months],
                }
            )
            missing_input.append(f"{check['label']} ({source_key})")
            missing_compare.append(f"{check['label']} ({source_key})")
            continue

        coverage = scan_source_time_coverage(source_key, path)
        input_missing_months = months_missing_from_coverage(coverage, input_months)
        compare_missing_months = months_missing_from_coverage(coverage, compare_months)
        source_reports.append(
            {
                "label": check["label"],
                "source_key": source_key,
                "path": str(path),
                "exists": True,
                "kind": coverage.get("kind"),
                "min_month": None if coverage.get("min_month") is None else str(coverage["min_month"].date()),
                "max_month": None if coverage.get("max_month") is None else str(coverage["max_month"].date()),
                "input_missing_months": [month.strftime("%Y-%m") for month in input_missing_months],
                "compare_missing_months": [month.strftime("%Y-%m") for month in compare_missing_months],
            }
        )
        if input_missing_months:
            missing_input.append(f"{check['label']} ({source_key}): {', '.join(month.strftime('%Y-%m') for month in input_missing_months)}")
        if compare_missing_months:
            missing_compare.append(f"{check['label']} ({source_key}): {', '.join(month.strftime('%Y-%m') for month in compare_missing_months)}")

    return {
        "input_mode": normalize_input_mode(input_mode),
        "input_months": [month.strftime("%Y-%m") for month in input_months],
        "forecast_month": forecast_month.strftime("%Y-%m"),
        "forecast_allowed": len(missing_input) == 0,
        "compare_available": len(missing_compare) == 0,
        "missing_input_sources": missing_input,
        "missing_compare_sources": missing_compare,
        "source_reports": source_reports,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit sorgenti BioCube per forecast BioAnalyst oltre il 2020.")
    parser.add_argument("--biocube-dir", type=Path, default=None, help="Override di BIOCUBE_DIR.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Cartella report. Se omessa usa outputs/dataset_audit.")
    parser.add_argument("--input-mode", choices=["clean", "all"], default="all")
    parser.add_argument("--forecast-start", default="2020-07-01", help="Primo mese da validare come forecast future-aware.")
    parser.add_argument("--forecast-end", default="2021-12-01", help="Ultimo mese da validare come forecast future-aware.")
    return parser


def resolve_biocube_dir(cli_path: Path | None) -> Path:
    if cli_path is not None:
        return cli_path.expanduser().resolve()
    load_project_env()
    return require_path("BIOCUBE_DIR")


def source_inventory_frame(biocube_dir: Path) -> pd.DataFrame:
    rows = []
    for source_key, (relative_path, variables) in MODEL_SOURCE_FILES.items():
        path = biocube_dir / relative_path
        exists = path.exists()
        coverage = scan_source_time_coverage(source_key, path) if exists else {}
        rows.append(
            {
                "source_key": source_key,
                "relative_path": relative_path,
                "exists": exists,
                "is_optional": source_key in OPTIONAL_MODEL_SOURCE_KEYS,
                "variable_count": len(variables),
                "variables": ", ".join(variables) if variables else "",
                "coverage_kind": coverage.get("kind"),
                "min_month": None if coverage.get("min_month") is None else coverage["min_month"].strftime("%Y-%m"),
                "max_month": None if coverage.get("max_month") is None else coverage["max_month"].strftime("%Y-%m"),
                "available_years": ", ".join(str(year) for year in coverage.get("available_years", [])),
                "absolute_path": str(path),
            }
        )
    frame = pd.DataFrame(rows)
    return frame.sort_values(["exists", "source_key"], ascending=[False, True]).reset_index(drop=True)


def month_windows(start: str, end: str) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    start_month = to_month_start(start)
    end_month = to_month_start(end)
    forecast_months = pd.period_range(start=start_month, end=end_month, freq="M").to_timestamp()
    windows = []
    for forecast_month in forecast_months:
        input_last = shift_month(forecast_month, -1)
        input_prev = shift_month(forecast_month, -2)
        windows.append((input_prev, input_last, forecast_month))
    return windows


def feasibility_frame(source_paths: dict[str, Path], start: str, end: str, input_mode: str) -> pd.DataFrame:
    rows = []
    for input_prev, input_last, forecast_month in month_windows(start, end):
        report = assess_future_inference_availability(
            source_paths,
            input_prev=input_prev,
            input_last=input_last,
            forecast_month=forecast_month,
            input_mode=input_mode,
        )
        rows.append(
            {
                "forecast_month": forecast_month.strftime("%Y-%m"),
                "input_prev": input_prev.strftime("%Y-%m"),
                "input_last": input_last.strftime("%Y-%m"),
                "input_mode": normalize_input_mode(input_mode),
                "forecast_allowed": report["forecast_allowed"],
                "compare_available": report["compare_available"],
                "missing_input_sources": " | ".join(report["missing_input_sources"]),
                "missing_compare_sources": " | ".join(report["missing_compare_sources"]),
            }
        )
    return pd.DataFrame(rows)


def summary_frame(feasibility: pd.DataFrame) -> pd.DataFrame:
    if feasibility.empty:
        return pd.DataFrame(columns=["metric", "value"])
    rows = [
        {"metric": "forecast_months_tested", "value": int(len(feasibility))},
        {"metric": "forecast_allowed_count", "value": int(feasibility["forecast_allowed"].sum())},
        {"metric": "compare_available_count", "value": int(feasibility["compare_available"].sum())},
        {"metric": "first_forecast_month", "value": feasibility["forecast_month"].min()},
        {"metric": "last_forecast_month", "value": feasibility["forecast_month"].max()},
    ]
    return pd.DataFrame(rows)


def timestamped_fallback(path: Path) -> Path:
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{stamp}{path.suffix}")


def write_excel_with_fallback(path: Path, sheets: dict[str, pd.DataFrame]) -> Path:
    target = path
    try:
        with pd.ExcelWriter(target) as writer:
            for sheet_name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=sheet_name, index=False)
        return target
    except PermissionError:
        fallback = timestamped_fallback(path)
        with pd.ExcelWriter(fallback) as writer:
            for sheet_name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=sheet_name, index=False)
        return fallback


def write_csv_with_fallback(path: Path, frame: pd.DataFrame) -> Path:
    try:
        frame.to_csv(path, index=False, encoding="utf-8-sig", sep=";", decimal=",")
        return path
    except PermissionError:
        fallback = timestamped_fallback(path)
        frame.to_csv(fallback, index=False, encoding="utf-8-sig", sep=";", decimal=",")
        return fallback


def main() -> None:
    args = build_parser().parse_args()
    biocube_dir = resolve_biocube_dir(args.biocube_dir)
    output_dir = (args.output_dir or (PROJECT_ROOT / "outputs" / "dataset_audit")).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    source_paths = resolve_source_paths(biocube_dir)
    inventory = source_inventory_frame(biocube_dir)
    feasibility = feasibility_frame(source_paths, args.forecast_start, args.forecast_end, args.input_mode)
    summary = summary_frame(feasibility)

    workbook_path = output_dir / f"biocube_future_coverage_{args.forecast_start[:4]}_{args.forecast_end[:4]}.xlsx"
    workbook_path = write_excel_with_fallback(
        workbook_path,
        {
            "summary": summary,
            "sources": inventory,
            "forecast_feasibility": feasibility,
        },
    )

    inventory_csv = output_dir / "biocube_source_inventory.csv"
    feasibility_csv = output_dir / "biocube_forecast_feasibility.csv"
    summary_csv = output_dir / "biocube_future_coverage_summary.csv"
    inventory_csv = write_csv_with_fallback(inventory_csv, inventory)
    feasibility_csv = write_csv_with_fallback(feasibility_csv, feasibility)
    summary_csv = write_csv_with_fallback(summary_csv, summary)

    result = {
        "biocube_dir": str(biocube_dir),
        "workbook": str(workbook_path),
        "inventory_csv": str(inventory_csv),
        "feasibility_csv": str(feasibility_csv),
        "summary_csv": str(summary_csv),
        "tested_forecast_start": args.forecast_start,
        "tested_forecast_end": args.forecast_end,
        "input_mode": args.input_mode,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
