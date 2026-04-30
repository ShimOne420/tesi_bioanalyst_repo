#!/usr/bin/env python3
"""Scarica ERA5 mensili 2021+ via CDS API e li fonde ai file BioCube esistenti.

Requisiti:
    pip install cdsapi
    ~/.cdsapirc configurato con URL e API key CDS

Uso:
    source scripts/activate_bioanalyst_model.sh
    python scripts/extend_era5_to_2026.py --years 2021 2022 2023 2024
    python scripts/extend_era5_to_2026.py --years 2021 --target surface
    python scripts/extend_era5_to_2026.py --years 2021 2022 --dry-run

Nota sui file climate:
    climate_b (era5-climate-energy-moisture-1.nc): d2m, sd, t2m
    -> disponibili via monthly-means, scaricati direttamente.

    climate_a (era5-climate-energy-moisture-0.nc): smlt, tp, csfr, radiazioni
    -> variabili accumulation/forecast NON disponibili in monthly-means.
    Richiedono hourly + aggregazione mensile. Scaricali con:
        python scripts/extend_era5_to_2026.py --years 2021 --target climate_a_hourly
    Oppure usa bfm-data per la pipeline ufficiale.
"""

from __future__ import annotations

import argparse
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xarray as xr
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Area Europa allineata a MODEL_BOUNDS con margine per la griglia 0.25°
AREA = [72.0, -25.0, 32.0, 45.0]  # North, West, South, East
GRID = [0.25, 0.25]

ERA5_DOWNLOAD_CONFIG: dict[str, dict[str, Any]] = {
    "surface": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "2m_temperature",
                "mean_sea_level_pressure",
                "soil_type",
                "geopotential",
                "10m_u_component_of_wind",
                "10m_v_component_of_wind",
                "land_sea_mask",
            ],
        },
        "output_file": "era5_single.nc",
        "output_dir": "Copernicus/ERA5-monthly/era5-single",
    },
    "edaphic": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "volumetric_soil_water_layer_1",
                "volumetric_soil_water_layer_2",
                "soil_temperature_level_1",
                "soil_temperature_level_2",
            ],
        },
        "output_file": "era5-edaphic-0.nc",
        "output_dir": "Copernicus/ERA5-monthly/era5-edaphic",
    },
    "atmospheric": {
        "dataset": "reanalysis-era5-pressure-levels-monthly-means",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "geopotential",
                "temperature",
                "u_component_of_wind",
                "v_component_of_wind",
                "specific_humidity",
            ],
            "pressure_level": [
                "1000", "925", "850", "700", "600", "500",
                "400", "300", "250", "200", "150", "100", "50",
            ],
        },
        "output_file": "era5_pressure.nc",
        "output_dir": "Copernicus/ERA5-monthly/era5-pressure",
    },
    "climate_b": {
        "dataset": "reanalysis-era5-single-levels-monthly-means",
        "request": {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": [
                "2m_temperature",
                "2m_dewpoint_temperature",
                "snow_depth",
            ],
        },
        "output_file": "era5-climate-energy-moisture-1.nc",
        "output_dir": "Copernicus/ERA5-monthly/era5-climate-energy-moisture",
    },
}

CLIMATE_A_HOURLY_CONFIG: dict[str, Any] = {
    "dataset": "reanalysis-era5-single-levels",
    "request": {
        "product_type": ["reanalysis"],
        "variable": [
            "snowmelt",
            "total_precipitation",
            "convective_snowfall",
            "surface_solar_radiation_downwards",
            "surface_net_solar_radiation",
            "surface_net_thermal_radiation",
            "mean_total_precipitation_rate",
            "surface_solar_radiation_downwards_clear_sky",
        ],
    },
    "output_file": "era5-climate-energy-moisture-0.nc",
    "output_dir": "Copernicus/ERA5-monthly/era5-climate-energy-moisture",
}

CLIMATE_A_HOURLY_SUBREQUESTS: dict[str, list[str]] = {
    "bulk": [
        "snowmelt",
        "total_precipitation",
        "convective_snowfall",
        "surface_solar_radiation_downwards",
        "surface_net_solar_radiation",
        "surface_net_thermal_radiation",
        "surface_solar_radiation_downwards_clear_sky",
    ],
    # Workaround ufficiale CDS: `mean_total_precipitation_rate` scaricato da solo.
    "avg_tprate": [
        "mean_total_precipitation_rate",
    ],
}

MONTHLY_CHUNK_SIZE = 6

VARIABLE_RENAME_MAP: dict[str, dict[str, str]] = {
    "surface": {
        "2m_temperature": "t2m",
        "mean_sea_level_pressure": "msl",
        "soil_type": "slt",
        "geopotential": "z",
        "10m_u_component_of_wind": "u10",
        "10m_v_component_of_wind": "v10",
        "land_sea_mask": "lsm",
    },
    "edaphic": {
        "volumetric_soil_water_layer_1": "swvl1",
        "volumetric_soil_water_layer_2": "swvl2",
        "soil_temperature_level_1": "stl1",
        "soil_temperature_level_2": "stl2",
    },
    "atmospheric": {
        "geopotential": "z",
        "temperature": "t",
        "u_component_of_wind": "u",
        "v_component_of_wind": "v",
        "specific_humidity": "q",
    },
    "climate_b": {
        "2m_temperature": "t2m",
        "2m_dewpoint_temperature": "d2m",
        "snow_depth": "sd",
    },
    "climate_a_hourly": {
        "snowmelt": "smlt",
        "smlt": "smlt",
        "total_precipitation": "tp",
        "tp": "tp",
        "convective_snowfall": "csfr",
        "csf": "csfr",
        "csfr": "csfr",
        "surface_solar_radiation_downwards": "avg_sdswrf",
        "ssrd": "avg_sdswrf",
        "surface_net_solar_radiation": "avg_snswrf",
        "ssr": "avg_snswrf",
        "surface_net_thermal_radiation": "avg_snlwrf",
        "str": "avg_snlwrf",
        "mean_total_precipitation_rate": "avg_tprate",
        "mtpr": "avg_tprate",
        "surface_solar_radiation_downwards_clear_sky": "avg_sdswrfcs",
        "ssrdc": "avg_sdswrfcs",
    },
}


def resolve_biocube_dir(cli_path: Path | None) -> Path:
    if cli_path is not None:
        return cli_path.expanduser().resolve()
    load_dotenv(PROJECT_ROOT / ".env")
    value = os.getenv("BIOCUBE_DIR")
    if not value:
        raise SystemExit("BIOCUBE_DIR non impostata in .env e nessun --biocube-dir fornito.")
    return Path(value).expanduser().resolve()


def chunk_year_months(year_months: list[tuple[int, int]], max_size: int) -> list[list[tuple[int, int]]]:
    chunks: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    for ym in sorted(year_months):
        current.append(ym)
        if len(current) >= max_size:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def build_monthly_request(base: dict[str, Any], year_months: list[tuple[int, int]]) -> dict[str, Any]:
    request = dict(base)
    request["year"] = sorted({str(y) for y, _ in year_months})
    request["month"] = [f"{m:02d}" for _, m in sorted(year_months, key=lambda x: (x[0], x[1]))]
    request["time"] = ["00:00"]
    request["data_format"] = "netcdf"
    request["download_format"] = "unarchived"
    request["area"] = AREA
    request["grid"] = GRID
    return request


def build_hourly_request(base: dict[str, Any], year_months: list[tuple[int, int]]) -> dict[str, Any]:
    request = dict(base)
    date_parts: list[str] = []
    for year, month in sorted(year_months):
        days = pd.Timestamp(year, month, 1).days_in_month
        date_parts.append(f"{year}-{month:02d}-01/{year}-{month:02d}-{days:02d}")
    request["date"] = date_parts
    request["time"] = [f"{h:02d}:00" for h in range(0, 24)]
    request["data_format"] = "netcdf"
    request["download_format"] = "unarchived"
    request["area"] = AREA
    request["grid"] = GRID
    return request


def materialize_download_payload(dl_path: Path) -> tuple[Path, list[Path]]:
    """Rende leggibile l'output CDS anche se arriva archivato come zip."""
    if not zipfile.is_zipfile(dl_path):
        return dl_path, [dl_path]

    extracted_dir = dl_path.parent / f"{dl_path.stem}_unzipped"
    if extracted_dir.exists():
        shutil.rmtree(extracted_dir)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(dl_path) as archive:
        archive.extractall(extracted_dir)
        members = [member for member in archive.namelist() if not member.endswith("/")]

    payload_candidates = [extracted_dir / member for member in members]
    preferred = next((path for path in payload_candidates if path.suffix.lower() == ".nc"), None)
    if preferred is None:
        preferred = payload_candidates[0] if payload_candidates else None
    if preferred is None or not preferred.exists():
        raise FileNotFoundError(f"Archivio CDS senza file leggibili: {dl_path}")

    print(f"  Archivio zip CDS rilevato, uso payload: {preferred.name}")
    return preferred, [dl_path, extracted_dir]


def cleanup_download_artifacts(paths: list[Path]) -> None:
    for path in paths:
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def rename_and_clean(ds: xr.Dataset, target_name: str) -> xr.Dataset:
    rename_map = VARIABLE_RENAME_MAP.get(target_name, {})
    to_rename = {old: new for old, new in rename_map.items() if old in ds.data_vars}
    if to_rename:
        ds = ds.rename(to_rename)
    if "valid_time" in ds.coords:
        ds = ds.assign_coords(valid_time=pd.to_datetime(ds["valid_time"].values))
    return ds


def aggregate_hourly_to_monthly(hourly_path: Path, target_name: str) -> xr.Dataset:
    print(f"  Aggregazione hourly -> monthly: {hourly_path.name}")
    with xr.open_dataset(hourly_path, engine="netcdf4") as ds:
        ds = rename_and_clean(ds, target_name)
        time_values = pd.to_datetime(ds["valid_time"].values)
        month_starts = pd.Series(time_values).dt.to_period("M").dt.to_timestamp()
        monthly_parts: list[xr.Dataset] = []
        for month_time in pd.Index(month_starts).drop_duplicates().sort_values():
            positions = np.where(month_starts == month_time)[0]
            group = ds.isel(valid_time=positions)
            agg: dict[str, xr.DataArray] = {}
            for var in group.data_vars:
                if var in {"tp", "csfr", "smlt"}:
                    agg[var] = group[var].sum(dim="valid_time", keep_attrs=True)
                else:
                    agg[var] = group[var].mean(dim="valid_time", keep_attrs=True)
            month_ds = xr.Dataset(
                agg,
                coords={
                    "valid_time": [month_time],
                    "latitude": group["latitude"],
                    "longitude": group["longitude"],
                },
            )
            monthly_parts.append(month_ds)
        return xr.concat(monthly_parts, dim="valid_time")


MODEL_CROP_BOUNDS = {
    "lat_min": 32.0,
    "lat_max": 72.0,
    "lon_min": -25.0,
    "lon_max": 45.0,
}


def crop_to_model_grid(new_ds: xr.Dataset) -> xr.Dataset:
    lat_min = MODEL_CROP_BOUNDS["lat_min"]
    lat_max = MODEL_CROP_BOUNDS["lat_max"]
    lon_min = MODEL_CROP_BOUNDS["lon_min"]
    lon_max = MODEL_CROP_BOUNDS["lon_max"]
    print(f"  Ritaglio a griglia modello: lat [{lat_min}, {lat_max}] lon [{lon_min}, {lon_max}]")
    if "latitude" in new_ds.dims:
        new_ds = new_ds.sel(latitude=slice(lat_max, lat_min))
    if "longitude" in new_ds.dims:
        lon_vals = new_ds["longitude"].values
        if lon_vals.max() > 180:
            new_ds = new_ds.assign_coords(longitude=((lon_vals + 180) % 360 - 180))
            new_ds = new_ds.sortby("longitude")
        new_ds = new_ds.sel(longitude=slice(lon_min, lon_max))
    return new_ds


def normalize_merge_coordinates(ds: xr.Dataset) -> xr.Dataset:
    """Rimuove coordinate ausiliarie ERA5 che non devono bloccare la concat."""
    drop_coord_names = [name for name in ("expver", "number") if name in ds.coords and name not in ds.dims]
    if drop_coord_names:
        ds = ds.drop_vars(drop_coord_names)
    return ds


def merge_with_existing(existing_path: Path, new_ds: xr.Dataset, target_name: str) -> xr.Dataset:
    print(f"  Fusione con esistente: {existing_path.name}")
    with xr.open_dataset(existing_path, engine="netcdf4") as existing:
        existing = existing.load()
    new_ds = normalize_merge_coordinates(crop_to_model_grid(new_ds).load())
    existing = normalize_merge_coordinates(crop_to_model_grid(existing))
    common = set(existing.data_vars) & set(new_ds.data_vars)
    if not common:
        print(f"  [warn] Nessuna variabile in comune per {target_name}, salvo solo i nuovi dati.")
        return new_ds
    existing_common = existing[list(common)].compute()
    new_common = new_ds[list(common)].compute()
    merged_time = xr.concat([existing_common, new_common], dim="valid_time", coords="minimal", compat="override")
    merged_time = merged_time.sortby("valid_time")
    extra_vars = set(new_ds.data_vars) - set(existing.data_vars)
    merged = merged_time
    for var in extra_vars:
        merged[var] = new_ds[var]
    existing_extra = set(existing.data_vars) - common
    for var in existing_extra:
        merged[var] = existing[var]
    for attr in existing.attrs:
        if attr not in merged.attrs:
            merged.attrs[attr] = existing.attrs[attr]
    return merged


def download_and_merge_monthly(
    client,
    target_name: str,
    year_months: list[tuple[int, int]],
    biocube_dir: Path,
    dry_run: bool,
    tmp_dir: Path,
) -> None:
    config = ERA5_DOWNLOAD_CONFIG[target_name]
    output_dir = biocube_dir / config["output_dir"]
    output_path = output_dir / config["output_file"]
    existing = output_path.exists()

    if not existing:
        print(f"  [warn] File non trovato: {output_path}")
        print(f"  Skip. Esegui prima il download base di BioCube.")
        return

    chunks = chunk_year_months(year_months, MONTHLY_CHUNK_SIZE)
    print(f"  {len(chunks)} chunk(s), {len(year_months)} mesi totali")

    for chunk in chunks:
        label = ", ".join(f"{y}-{m:02d}" for y, m in chunk)
        if dry_run:
            print(f"  [dry-run] {target_name}: {label}")
            continue

        request = build_monthly_request(config["request"], chunk)
        dl_path = tmp_dir / f"{target_name}_{'-'.join(f'{y}{m:02d}' for y, m in chunk[:1])}.nc"
        print(f"  [{target_name}] Download: {label}")
        client.retrieve(config["dataset"], request, str(dl_path))

        payload_path, cleanup_paths = materialize_download_payload(dl_path)
        with xr.open_dataset(payload_path, engine="netcdf4") as raw:
            new_ds = rename_and_clean(raw.load(), target_name)

        merged = merge_with_existing(output_path, new_ds, target_name)
        backup = output_path.with_suffix(".nc.bak")
        if not backup.exists():
            print(f"  Backup: {backup}")
            shutil.copy2(output_path, backup)
        print(f"  Scrittura: {output_path}")
        encoding = {var: {"zlib": True, "complevel": 4} for var in merged.data_vars}
        merged.to_netcdf(output_path, encoding=encoding)
        cleanup_download_artifacts(cleanup_paths)
        print(f"  Pulizia temp: {dl_path.name}")

    print(f"  [{target_name}] Completato.")


def download_and_merge_hourly(
    client,
    target_name: str,
    year_months: list[tuple[int, int]],
    biocube_dir: Path,
    dry_run: bool,
    tmp_dir: Path,
) -> None:
    config = CLIMATE_A_HOURLY_CONFIG
    output_dir = biocube_dir / config["output_dir"]
    output_path = output_dir / config["output_file"]
    existing = output_path.exists()

    if not existing:
        print(f"  [warn] File non trovato: {output_path}")
        print(f"  Skip. Esegui prima il download base di BioCube.")
        return

    # Hourly e' pesante: 1 mese per chunk
    chunks = chunk_year_months(year_months, max_size=1)
    print(f"  {len(chunks)} chunk(s) hourly (1 mese/chunk per limiti CDS)")

    for chunk in chunks:
        year, month = chunk[0]
        if dry_run:
            print(f"  [dry-run] {target_name}: {year}-{month:02d}")
            continue

        print(f"  [{target_name}] Download hourly: {year}-{month:02d}")
        monthly_parts: list[xr.Dataset] = []
        cleanup_targets: list[Path] = []

        for subset_name, subset_variables in CLIMATE_A_HOURLY_SUBREQUESTS.items():
            request = build_hourly_request(config["request"], chunk)
            request["variable"] = subset_variables
            dl_path = tmp_dir / f"{target_name}_{year}{month:02d}_{subset_name}.nc"
            print(f"    subset {subset_name}: {', '.join(subset_variables)}")
            client.retrieve(config["dataset"], request, str(dl_path))
            payload_path, cleanup_paths = materialize_download_payload(dl_path)
            cleanup_targets.extend(cleanup_paths)
            monthly_parts.append(aggregate_hourly_to_monthly(payload_path, "climate_a_hourly"))

        new_ds = xr.merge(monthly_parts, compat="override")
        merged = merge_with_existing(output_path, new_ds, target_name)
        backup = output_path.with_suffix(".nc.bak")
        if not backup.exists():
            print(f"  Backup: {backup}")
            shutil.copy2(output_path, backup)
        print(f"  Scrittura: {output_path}")
        encoding = {var: {"zlib": True, "complevel": 4} for var in merged.data_vars}
        merged.to_netcdf(output_path, encoding=encoding)
        cleanup_download_artifacts(cleanup_targets)
        print(f"  Pulizia temp: climate_a_hourly_{year}{month:02d}_*.nc")

    print(f"  [{target_name}] Completato.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scarica ERA5 mensili 2021+ e li fonde ai file BioCube esistenti.",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2021, 2022, 2023, 2024],
        help="Anni da scaricare.",
    )
    parser.add_argument(
        "--target",
        choices=["surface", "edaphic", "atmospheric", "climate_b", "climate_a_hourly", "all_monthly", "all"],
        default="all_monthly",
        help="Quale sorgente ERA5 scaricare.",
    )
    parser.add_argument("--biocube-dir", type=Path, default=None, help="Override di BIOCUBE_DIR.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe fatto senza scaricare.")
    parser.add_argument("--tmp-dir", type=Path, default=None, help="Cartella temporanea per i download.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    biocube_dir = resolve_biocube_dir(args.biocube_dir)
    tmp_dir = args.tmp_dir or (PROJECT_ROOT / "outputs" / "era5_downloads")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    year_months = [(y, m) for y in args.years for m in range(1, 13)]
    years_label = ", ".join(str(y) for y in sorted(args.years))
    print(f"BioCube dir: {biocube_dir}")
    print(f"Anni: {years_label} ({len(year_months)} mesi)")
    print(f"Target: {args.target}")
    print()

    if args.dry_run:
        print("=== DRY RUN ===")
        targets_map = {
            "all_monthly": [("surface", "monthly"), ("edaphic", "monthly"), ("atmospheric", "monthly"), ("climate_b", "monthly")],
            "all": [("surface", "monthly"), ("edaphic", "monthly"), ("atmospheric", "monthly"), ("climate_b", "monthly"), ("climate_a_hourly", "hourly")],
        }
        plan = targets_map.get(args.target, [(args.target, "hourly" if args.target.endswith("_hourly") else "monthly")])
        for t, mode in plan:
            print(f"  [{mode}] {t}: {years_label}")
        print("\n=== DRY RUN completato. ===")
        return

    try:
        import cdsapi
    except ImportError:
        raise SystemExit("cdsapi non installato. Run: pip install cdsapi")

    client = cdsapi.Client()

    targets_map = {
        "all_monthly": [("surface", "monthly"), ("edaphic", "monthly"), ("atmospheric", "monthly"), ("climate_b", "monthly")],
        "all": [
            ("surface", "monthly"),
            ("edaphic", "monthly"),
            ("atmospheric", "monthly"),
            ("climate_b", "monthly"),
            ("climate_a_hourly", "hourly"),
        ],
    }

    plan = targets_map.get(args.target, [(args.target, "hourly" if args.target.endswith("_hourly") else "monthly")])

    for target_name, mode in plan:
        print(f"\n{'='*60}")
        print(f"Target: {target_name} ({mode})")
        print(f"{'='*60}")
        if mode == "monthly":
            download_and_merge_monthly(client, target_name, year_months, biocube_dir, args.dry_run, tmp_dir)
        else:
            download_and_merge_hourly(client, target_name, year_months, biocube_dir, args.dry_run, tmp_dir)

    print(f"\n{'='*60}")
    print("=== Estensione ERA5 completata. ===")
    print("Verifica con:")
    print(f"  python scripts/audit_future_dataset_coverage.py --input-mode clean --forecast-start 2021-01-01 --forecast-end 2025-12-01")


if __name__ == "__main__":
    main()
