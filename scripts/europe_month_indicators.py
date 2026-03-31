#!/usr/bin/env python3
"""Calcola i 3 indicatori minimi nel formato Europa intera per mese."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd
import xarray as xr
from dotenv import load_dotenv

from minimum_indicator_utils import (
    build_land_mask,
    compute_weighted_land_mean_series,
    subset_europe,
    write_tabular_outputs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require_path(env_name: str) -> Path:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {env_name}")
    path = Path(value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Percorso non trovato per {env_name}: {path}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calcola i 3 indicatori minimi in formato Europa intera per mese."
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Numero massimo di mesi da processare per un test veloce.",
    )
    return parser


def compute_species_monthly(species_path: Path, max_steps: int | None = None) -> pd.DataFrame:
    df = pd.read_parquet(species_path, columns=["Species", "Timestamp"])
    df["month"] = pd.to_datetime(df["Timestamp"]).dt.to_period("M").dt.to_timestamp()
    monthly = (
        df.groupby("month")["Species"]
        .nunique()
        .reset_index(name="species_count_europe")
        .sort_values("month")
    )
    if max_steps is not None:
        monthly = monthly.head(max_steps)
    monthly["month"] = monthly["month"].dt.strftime("%Y-%m-%d")
    return monthly


def main() -> None:
    args = build_parser().parse_args()
    load_dotenv(PROJECT_ROOT / ".env")

    biocube_dir = require_path("BIOCUBE_DIR")
    output_dir = require_path("PROJECT_OUTPUT_DIR")

    species_path = biocube_dir / "Species" / "europe_species.parquet"
    temperature_path = (
        biocube_dir
        / "Copernicus"
        / "ERA5-monthly"
        / "era5-single"
        / "era5_single.nc"
    )
    precipitation_path = (
        biocube_dir
        / "Copernicus"
        / "ERA5-monthly"
        / "era5-climate-energy-moisture"
        / "era5-climate-energy-moisture-0.nc"
    )

    species_monthly = compute_species_monthly(species_path, max_steps=args.max_steps)

    ds_temp = subset_europe(xr.open_dataset(temperature_path))
    ds_prec = subset_europe(xr.open_dataset(precipitation_path))
    land_mask = build_land_mask(ds_temp)

    temperature_monthly = compute_weighted_land_mean_series(
        ds=ds_temp,
        var_name="t2m",
        output_column="temperature_mean_europe_c",
        land_mask=land_mask,
        transform=lambda value: value - 273.15,
        max_steps=args.max_steps,
    )

    precipitation_monthly = compute_weighted_land_mean_series(
        ds=ds_prec,
        var_name="tp",
        output_column="precipitation_mean_europe_mm",
        land_mask=land_mask,
        transform=lambda value: value * 1000.0,
        max_steps=args.max_steps,
    )

    ds_temp.close()
    ds_prec.close()

    final_df = (
        species_monthly
        .merge(temperature_monthly, on="month", how="inner")
        .merge(precipitation_monthly, on="month", how="inner")
        .sort_values("month")
    )

    summary = {
        "mode": "europe_per_month",
        "aggregation_region": "Europe bbox lat 30..75, lon -25..45, land-only, latitude-weighted",
        "rows": int(len(final_df)),
        "time_start": str(final_df["month"].min()),
        "time_end": str(final_df["month"].max()),
        "species_source": str(species_path),
        "temperature_source": str(temperature_path),
        "precipitation_source": str(precipitation_path),
        "species_count_min": int(final_df["species_count_europe"].min()),
        "species_count_max": int(final_df["species_count_europe"].max()),
        "temperature_mean_c_global_mean": float(final_df["temperature_mean_europe_c"].mean()),
        "precipitation_mean_mm_global_mean": float(final_df["precipitation_mean_europe_mm"].mean()),
    }

    output_paths, used_fallback = write_tabular_outputs(
        summary=summary,
        table_df=final_df,
        stem="europe_month_indicators",
        output_dir=output_dir,
        project_root=PROJECT_ROOT,
    )

    print("Pipeline Europa intera per mese completata.")
    print(pd.Series(summary).to_json(force_ascii=False, indent=2))
    print(f"\nSummary: {output_paths['summary']}")
    print(f"CSV: {output_paths['csv']}")
    print(f"CSV Excel: {output_paths['excel_csv']}")
    print(f"XLSX: {output_paths['xlsx']}")
    if used_fallback:
        print(
            "\nNota: ho usato la cartella locale del repo perché il path esterno non era "
            "scrivibile in questo ambiente."
        )


if __name__ == "__main__":
    main()
