#!/usr/bin/env python3
"""Estende la sorgente vegetation/LAI BioCube fino al 2026 via CDS API.

Il batch BioAnalyst usa `vegetation.NDVI`. Quando il CSV NDVI ufficiale non
copre i mesi richiesti, la pipeline usa una proxy dichiarata da ERA5-Land:
`lai_hv + lai_lv -> NDVI proxy`. Questo script aggiorna proprio la sorgente
`data_stream-moda.nc` usata da quel fallback.

Requisiti:
    pip install cdsapi
    ~/.cdsapirc configurato con URL e API key CDS

Uso:
    python scripts/extend_vegetation_to_2026.py --years 2022 2023 2024 2025 2026
    python scripts/extend_vegetation_to_2026.py --years 2022 --months 1 2 --dry-run
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import pandas as pd
import xarray as xr

from extend_era5_to_2026 import (
    AREA,
    GRID,
    PROJECT_ROOT,
    cleanup_download_artifacts,
    crop_to_model_grid,
    materialize_download_payload,
    normalize_merge_coordinates,
    resolve_biocube_dir,
)


VEGETATION_CONFIG: dict[str, Any] = {
    "dataset": "reanalysis-era5-land-monthly-means",
    "request": {
        "product_type": ["monthly_averaged_reanalysis"],
        "variable": [
            "leaf_area_index_high_vegetation",
            "leaf_area_index_low_vegetation",
        ],
    },
    "output_file": "data_stream-moda.nc",
    "output_dir": "Copernicus/ERA5-monthly/era5-land-vegetation",
}

VARIABLE_RENAME_MAP = {
    "leaf_area_index_high_vegetation": "lai_hv",
    "leaf_area_index_low_vegetation": "lai_lv",
}

REQUIRED_VARS = {"lai_hv", "lai_lv"}


def build_monthly_request(base: dict[str, Any], year: int, months: list[int]) -> dict[str, Any]:
    request = dict(base)
    request["year"] = [str(year)]
    request["month"] = [f"{month:02d}" for month in sorted(months)]
    request["time"] = ["00:00"]
    request["data_format"] = "netcdf"
    request["download_format"] = "unarchived"
    request["area"] = AREA
    request["grid"] = GRID
    return request


def normalize_time_coordinate(ds: xr.Dataset) -> xr.Dataset:
    if "valid_time" not in ds.coords and "time" in ds.coords:
        ds = ds.rename({"time": "valid_time"})
    if "valid_time" in ds.coords:
        ds = ds.assign_coords(valid_time=pd.to_datetime(ds["valid_time"].values))
    return ds


def rename_and_clean(ds: xr.Dataset) -> xr.Dataset:
    rename_map = {old: new for old, new in VARIABLE_RENAME_MAP.items() if old in ds.data_vars}
    if rename_map:
        ds = ds.rename(rename_map)
    return normalize_time_coordinate(ds)


def existing_months(path: Path) -> set[pd.Timestamp]:
    if not path.exists():
        return set()
    with xr.open_dataset(path, engine="netcdf4") as ds:
        if "valid_time" not in ds.coords:
            return set()
        values = pd.to_datetime(ds["valid_time"].values).to_period("M").to_timestamp()
    return {pd.Timestamp(value).to_period("M").to_timestamp() for value in values}


def validate_vegetation_dataset(ds: xr.Dataset, label: str) -> None:
    missing = REQUIRED_VARS.difference(ds.data_vars)
    if missing:
        raise ValueError(f"{label}: variabili vegetation mancanti: {sorted(missing)}")
    for var in sorted(REQUIRED_VARS):
        values = ds[var]
        finite_count = int(values.notnull().sum().item())
        if finite_count == 0:
            raise ValueError(f"{label}: {var} contiene solo NaN")
        max_abs = float(abs(values).max(skipna=True).item())
        if max_abs <= 1e-12:
            print(f"  [warn] {label}: {var} ha segnale nullo sulla griglia selezionata")


def merge_with_existing(existing_path: Path, new_ds: xr.Dataset) -> xr.Dataset:
    print(f"  Fusione con esistente: {existing_path.name}")
    with xr.open_dataset(existing_path, engine="netcdf4") as existing:
        existing = existing.load()

    existing = normalize_merge_coordinates(crop_to_model_grid(rename_and_clean(existing)))
    new_ds = normalize_merge_coordinates(crop_to_model_grid(rename_and_clean(new_ds)).load())
    validate_vegetation_dataset(new_ds, "nuovo download")

    common = sorted(set(existing.data_vars) & set(new_ds.data_vars))
    if not common:
        print("  [warn] Nessuna variabile in comune: salvo solo il nuovo dataset vegetation.")
        return new_ds

    merged = xr.concat(
        [existing[common].compute(), new_ds[common].compute()],
        dim="valid_time",
        coords="minimal",
        compat="override",
    )
    merged = merged.sortby("valid_time")
    time_frame = pd.DataFrame({"valid_time": pd.to_datetime(merged["valid_time"].values), "pos": range(merged.sizes["valid_time"])})
    keep_positions = time_frame.drop_duplicates("valid_time", keep="last")["pos"].to_numpy()
    merged = merged.isel(valid_time=sorted(keep_positions)).sortby("valid_time")

    for var in sorted(set(new_ds.data_vars) - set(common)):
        merged[var] = new_ds[var]
    for var in sorted(set(existing.data_vars) - set(common)):
        merged[var] = existing[var]
    for key, value in existing.attrs.items():
        merged.attrs.setdefault(key, value)
    validate_vegetation_dataset(merged, "dataset vegetation fuso")
    return merged


def write_with_backup(output_path: Path, merged: xr.Dataset) -> None:
    backup = output_path.with_suffix(".nc.bak")
    if not backup.exists():
        print(f"  Backup: {backup}")
        shutil.copy2(output_path, backup)
    print(f"  Scrittura: {output_path}")
    encoding = {var: {"zlib": True, "complevel": 4} for var in merged.data_vars}
    merged.to_netcdf(output_path, encoding=encoding)


def download_and_merge_year(
    client: Any,
    *,
    year: int,
    months: list[int],
    biocube_dir: Path,
    tmp_dir: Path,
    dry_run: bool,
    skip_existing: bool,
) -> None:
    output_dir = biocube_dir / VEGETATION_CONFIG["output_dir"]
    output_path = output_dir / VEGETATION_CONFIG["output_file"]
    if not output_path.exists():
        print(f"  [warn] File vegetation non trovato: {output_path}")
        print("  Skip. Scarica prima il subset BioCube con era5-land-vegetation.")
        return

    requested_months = sorted(months)
    if skip_existing:
        available = existing_months(output_path)
        requested_months = [
            month for month in requested_months
            if pd.Timestamp(year=year, month=month, day=1) not in available
        ]

    if not requested_months:
        print(f"  [{year}] Tutti i mesi richiesti sono gia presenti.")
        return

    label = ", ".join(f"{year}-{month:02d}" for month in requested_months)
    if dry_run:
        print(f"  [dry-run] vegetation_lai: {label}")
        return

    request = build_monthly_request(VEGETATION_CONFIG["request"], year, requested_months)
    dl_path = tmp_dir / f"vegetation_lai_{year}.nc"
    print(f"  [vegetation_lai] Download: {label}")
    client.retrieve(VEGETATION_CONFIG["dataset"], request, str(dl_path))

    payload_path, cleanup_paths = materialize_download_payload(dl_path)
    with xr.open_dataset(payload_path, engine="netcdf4") as raw:
        new_ds = rename_and_clean(raw.load())

    merged = merge_with_existing(output_path, new_ds)
    write_with_backup(output_path, merged)
    cleanup_download_artifacts(cleanup_paths)
    print(f"  Pulizia temp: {dl_path.name}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estende ERA5-Land vegetation LAI fino al 2026 e aggiorna data_stream-moda.nc.",
    )
    parser.add_argument("--years", type=int, nargs="+", default=[2022, 2023, 2024, 2025, 2026])
    parser.add_argument("--months", type=int, nargs="+", default=list(range(1, 13)), help="Mesi da scaricare, 1-12.")
    parser.add_argument("--biocube-dir", type=Path, default=None, help="Override di BIOCUBE_DIR.")
    parser.add_argument("--tmp-dir", type=Path, default=None, help="Cartella temporanea per i download.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra cosa verrebbe fatto senza scaricare.")
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Riscaria anche mesi gia presenti nel file esistente.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    invalid_months = [month for month in args.months if month < 1 or month > 12]
    if invalid_months:
        raise SystemExit(f"Mesi non validi: {invalid_months}. Usa valori 1-12.")

    biocube_dir = resolve_biocube_dir(args.biocube_dir)
    tmp_dir = args.tmp_dir or (PROJECT_ROOT / "outputs" / "era5_downloads")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    print(f"BioCube dir: {biocube_dir}")
    print(f"Anni: {', '.join(str(year) for year in sorted(args.years))}")
    print(f"Mesi: {', '.join(f'{month:02d}' for month in sorted(args.months))}")
    print("Target: vegetation_lai (ERA5-Land monthly means)")
    print()

    if args.dry_run:
        for year in sorted(args.years):
            download_and_merge_year(
                None,
                year=year,
                months=sorted(args.months),
                biocube_dir=biocube_dir,
                tmp_dir=tmp_dir,
                dry_run=True,
                skip_existing=not args.no_skip_existing,
            )
        print("\n=== DRY RUN completato. ===")
        return

    try:
        import cdsapi
    except ImportError:
        raise SystemExit("cdsapi non installato. Run: pip install cdsapi")

    client = cdsapi.Client()
    for year in sorted(args.years):
        print(f"\n{'=' * 60}")
        print(f"Vegetation LAI: {year}")
        print(f"{'=' * 60}")
        download_and_merge_year(
            client,
            year=year,
            months=sorted(args.months),
            biocube_dir=biocube_dir,
            tmp_dir=tmp_dir,
            dry_run=False,
            skip_existing=not args.no_skip_existing,
        )

    print(f"\n{'=' * 60}")
    print("=== Estensione vegetation completata. ===")
    print("Verifica con:")
    print(
        "  python scripts/audit_future_dataset_coverage.py "
        "--input-mode all --forecast-start 2022-01-01 --forecast-end 2026-12-01"
    )


if __name__ == "__main__":
    main()
