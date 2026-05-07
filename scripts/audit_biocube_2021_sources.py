#!/usr/bin/env python3
"""Diagnostica rapida delle sorgenti BioCube necessarie per un run 2021 reale."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bioanalyst_model_utils import (  # noqa: E402
    climate_last_available_month,
    latest_monthly_column,
    load_project_env,
    ndvi_source_score,
    parse_month_from_column_name,
    read_ndvi_columns,
    resolve_source_paths,
    shift_month,
    to_month_start,
    vegetation_dynamic_source_score,
)


def build_months(start: str, end: str, include_forecast: bool) -> list[pd.Timestamp]:
    start_month = to_month_start(start)
    end_month = to_month_start(end)
    months = list(pd.period_range(start=start_month, end=end_month, freq="M").to_timestamp())
    if include_forecast:
        months.append(shift_month(end_month, 1))
    return months


def format_months(months: list[pd.Timestamp]) -> str:
    return ", ".join(month.strftime("%Y-%m") for month in months)


def unique_existing_roots(paths: list[Path]) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        try:
            resolved = str(path.expanduser().resolve())
        except OSError:
            resolved = str(path.expanduser())
        if resolved in seen or not path.expanduser().exists():
            continue
        seen.add(resolved)
        roots.append(path.expanduser())
    return roots


def scan_files(root: Path, patterns: tuple[str, ...], suffixes: set[str]) -> list[Path]:
    matches: list[Path] = []
    for pattern in patterns:
        try:
            matches.extend(
                path
                for path in root.rglob(pattern)
                if path.is_file() and path.suffix.casefold() in suffixes
            )
        except OSError as exc:
            print(f"[warn] Non riesco a scansionare {root}: {exc}")
    return sorted(set(matches))


def month_columns_by_date(columns: list[str]) -> dict[pd.Timestamp, str]:
    mapping: dict[pd.Timestamp, str] = {}
    for column in columns:
        parsed = parse_month_from_column_name(str(column), "NDVI")
        if parsed is not None:
            mapping[parsed] = str(column)
    return mapping


def summarize_ndvi_table(path: Path, months: list[pd.Timestamp]) -> bool:
    print("\n[NDVI CSV]")
    print(f"path: {path}")
    if not path.exists():
        print("status: MANCANTE")
        return False

    columns = read_ndvi_columns(path)
    latest = latest_monthly_column(columns, "NDVI")
    print(f"size: {path.stat().st_size:,} bytes")
    print(f"columns: {len(columns)}")
    print(f"latest_ndvi_month: {latest.strftime('%Y-%m') if latest is not None else 'non trovato'}")
    month_columns = month_columns_by_date(columns)

    required_columns = [month_columns.get(to_month_start(month)) for month in months]
    all_present = all(column is not None for column in required_columns)
    for month, column in zip(months, required_columns, strict=True):
        print(f"  {month:%Y-%m}: {column or 'MANCANTE'}")

    if not all_present:
        return False

    try:
        if path.suffix.casefold() == ".csv":
            frame = pd.read_csv(path, usecols=sorted(set(required_columns)))
        else:
            frame = pd.read_excel(path, usecols=sorted(set(required_columns)))
    except Exception as exc:
        print(f"[warn] Colonne presenti, ma non riesco a leggere i valori NDVI: {exc}")
        return False

    has_signal = True
    for month, column in zip(months, required_columns, strict=True):
        values = pd.to_numeric(frame[column], errors="coerce")
        finite = values[np.isfinite(values)]
        non_zero = finite[finite.abs() > 1e-8]
        print(
            f"  signal {month:%Y-%m}: count={len(non_zero)} "
            f"min={non_zero.min() if len(non_zero) else 'n/a'} "
            f"mean={non_zero.mean() if len(non_zero) else 'n/a'} "
            f"max={non_zero.max() if len(non_zero) else 'n/a'}"
        )
        has_signal = has_signal and len(non_zero) > 0
    return has_signal


def summarize_vegetation_netcdf(path: Path, months: list[pd.Timestamp]) -> bool:
    print("\n[Vegetation NetCDF / LAI]")
    print(f"path: {path}")
    if not path.exists():
        print("status: MANCANTE")
        return False

    try:
        with xr.open_dataset(path, engine="netcdf4") as ds:
            variables = list(ds.data_vars)
            print(f"size: {path.stat().st_size:,} bytes")
            print(f"variables: {variables}")
            if "valid_time" not in ds:
                print("valid_time: MANCANTE")
                return False

            times = pd.to_datetime(ds["valid_time"].values)
            time_months = pd.Series(times).dt.to_period("M").dt.to_timestamp()
            print(f"valid_time_min: {time_months.min():%Y-%m}")
            print(f"valid_time_max: {time_months.max():%Y-%m}")

            ndvi_var = next((name for name in ("NDVI", "ndvi") if name in ds.data_vars), None)
            use_lai = {"lai_hv", "lai_lv"}.issubset(ds.data_vars)
            if ndvi_var is None and not use_lai:
                print("signal: niente NDVI e niente lai_hv/lai_lv")
                return False

            ok = True
            for month in months:
                month = to_month_start(month)
                positions = np.flatnonzero(time_months.to_numpy() == month)
                if len(positions) == 0:
                    print(f"  {month:%Y-%m}: MANCANTE")
                    ok = False
                    continue

                index = int(positions[0])
                if ndvi_var is not None:
                    array = ds[ndvi_var].isel(valid_time=index).load()
                    label = ndvi_var
                else:
                    array = (ds["lai_hv"].isel(valid_time=index) + ds["lai_lv"].isel(valid_time=index)).load()
                    label = "lai_hv + lai_lv"
                values = np.asarray(array.values, dtype="float64")
                finite = values[np.isfinite(values)]
                non_zero = finite[np.abs(finite) > 1e-8]
                print(
                    f"  signal {month:%Y-%m} ({label}): count={len(non_zero)} "
                    f"min={non_zero.min() if len(non_zero) else 'n/a'} "
                    f"mean={non_zero.mean() if len(non_zero) else 'n/a'} "
                    f"max={non_zero.max() if len(non_zero) else 'n/a'}"
                )
                ok = ok and len(non_zero) > 0
            return ok
    except Exception as exc:
        print(f"status: ERRORE LETTURA ({exc})")
        return False


def find_ndvi_candidates(roots: list[Path]) -> list[tuple[tuple[pd.Timestamp, int], Path]]:
    candidates: list[tuple[tuple[pd.Timestamp, int], Path]] = []
    seen: set[Path] = set()
    for root in roots:
        for path in scan_files(root, ("Europe*ndvi*", "*ndvi_monthly*"), {".csv", ".xlsx", ".xls"}):
            if path in seen:
                continue
            seen.add(path)
            score = ndvi_source_score(path)
            if score is not None:
                candidates.append((score, path))
    return sorted(candidates, key=lambda item: item[0], reverse=True)


def find_vegetation_candidates(roots: list[Path]) -> list[tuple[tuple[int, pd.Timestamp, int], Path]]:
    candidates: list[tuple[tuple[int, pd.Timestamp, int], Path]] = []
    seen: set[Path] = set()
    for root in roots:
        for path in scan_files(root, ("data_stream*.nc*",), {".nc", ".bak"}):
            if path in seen:
                continue
            seen.add(path)
            score = vegetation_dynamic_source_score(path)
            if score is not None:
                candidates.append((score, path))
    return sorted(candidates, key=lambda item: item[0], reverse=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit sorgenti BioCube per run native 2021.")
    parser.add_argument("--start", default="2021-04-01")
    parser.add_argument("--end", default="2021-05-01")
    parser.add_argument("--no-forecast-month", action="store_true")
    parser.add_argument("--search-root", action="append", default=[], help="Root extra da scansionare, es. F:\\biomap_store")
    args = parser.parse_args()

    load_project_env()
    months = build_months(args.start, args.end, include_forecast=not args.no_forecast_month)
    print(f"[audit] mesi richiesti: {format_months(months)}")

    biocube_raw = os.getenv("BIOCUBE_DIR")
    output_raw = os.getenv("PROJECT_OUTPUT_DIR")
    biocube_dir = Path(biocube_raw).expanduser() if biocube_raw else None
    project_output_dir = Path(output_raw).expanduser() if output_raw else None
    print(f"BIOCUBE_DIR={biocube_dir if biocube_dir is not None else 'non impostato'}")
    print(f"PROJECT_OUTPUT_DIR={project_output_dir if project_output_dir is not None else 'non impostato'}")
    for env_name in ("BIOCUBE_NDVI_PATH", "BIOCUBE_VEGETATION_DYNAMIC_PATH", "BIOCUBE_SEARCH_ROOTS"):
        print(f"{env_name}={os.getenv(env_name) or 'non impostato'}")

    source_paths = {}
    if biocube_dir is not None and biocube_dir.exists():
        source_paths = resolve_source_paths(biocube_dir)
        print("\n[Sorgenti risolte dal codice]")
        for key in ("land_ndvi_csv", "land_vegetation_dynamic", "surface", "climate_a", "climate_b"):
            print(f"{key}: {source_paths.get(key, 'non trovata')}")
        try:
            print(f"climate_last_available: {climate_last_available_month(source_paths):%Y-%m}")
        except Exception as exc:
            print(f"climate_last_available: ERRORE ({exc})")

    ndvi_ok = False
    vegetation_ok = False
    if "land_ndvi_csv" in source_paths:
        ndvi_ok = summarize_ndvi_table(source_paths["land_ndvi_csv"], months)
    if "land_vegetation_dynamic" in source_paths:
        vegetation_ok = summarize_vegetation_netcdf(source_paths["land_vegetation_dynamic"], months)

    search_roots = [Path(value).expanduser() for value in args.search_root]
    if biocube_dir is not None:
        search_roots.append(biocube_dir)
    if project_output_dir is not None:
        search_roots.extend([project_output_dir.parent, project_output_dir.parent / "data" / "biocube"])
    search_roots = unique_existing_roots(search_roots)

    if search_roots:
        print("\n[Candidate trovate nelle root di ricerca]")
        print("roots:", "; ".join(str(root) for root in search_roots))

        ndvi_candidates = find_ndvi_candidates(search_roots)[:5]
        print("NDVI candidates:")
        for (latest, size), path in ndvi_candidates:
            print(f"  latest={latest:%Y-%m} size={size:,} path={path}")

        vegetation_candidates = find_vegetation_candidates(search_roots)[:5]
        print("Vegetation candidates:")
        for (signal_score, latest, size), path in vegetation_candidates:
            kind = "NDVI" if signal_score == 2 else "LAI proxy"
            print(f"  kind={kind} latest={latest:%Y-%m} size={size:,} path={path}")

    print("\n[Verdetto]")
    if ndvi_ok:
        print("OK: il CSV NDVI risolto dal codice copre i mesi richiesti con segnale reale.")
    elif vegetation_ok:
        print("OK: il NetCDF vegetation risolto dal codice copre i mesi richiesti con segnale reale.")
    else:
        print("NON OK: il codice non sta vedendo vegetation/NDVI reale per tutti i mesi richiesti.")
        print("Se una candidate su F: ha latest>=2021-06, impostala con:")
        print("  $env:BIOCUBE_NDVI_PATH = 'F:\\\\...\\\\Europe_ndvi_monthly_un_025.csv'")
        print("oppure:")
        print("  $env:BIOCUBE_VEGETATION_DYNAMIC_PATH = 'F:\\\\...\\\\data_stream-moda.nc'")
        print("Poi rilancia questo audit prima del run GPU.")


if __name__ == "__main__":
    main()
