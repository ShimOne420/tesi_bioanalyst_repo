#!/usr/bin/env python3
"""Visualizza campioni e metadati delle sorgenti minime di BioCube."""

from __future__ import annotations

import argparse
import calendar
import os
from pathlib import Path

import pandas as pd
import xarray as xr
from dotenv import load_dotenv


# Leggiamo un path dal `.env` e verifichiamo che esista davvero.
def require_path(env_name: str) -> Path:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {env_name}")
    path = Path(value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Percorso non trovato per {env_name}: {path}")
    return path


# Definiamo gli argomenti CLI per scegliere quale sorgente ispezionare.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mostra un campione dei dati minimi usati per i 3 indicatori."
    )
    parser.add_argument(
        "--source",
        choices=["all", "species", "temperature", "precipitation"],
        default="all",
        help="Quale sorgente visualizzare.",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=5,
        help="Numero di righe da stampare per i dati tabellari.",
    )
    return parser


# Mostriamo un estratto tabellare del parquet specie e il suo intervallo temporale.
def show_species_sample(species_path: Path, rows: int) -> None:
    df = pd.read_parquet(species_path)
    print("=== SPECIES ===")
    print(f"file: {species_path}")
    print(f"righe: {len(df)}")
    print(f"colonne: {list(df.columns)}")
    print(f"periodo: {pd.to_datetime(df['Timestamp']).min()} -> {pd.to_datetime(df['Timestamp']).max()}")
    print("\nprime righe:")
    print(df.head(rows).to_string(index=False))
    print()


# Ispezioniamo metadati e primo timestep del dataset di temperatura.
def show_temperature_sample(temperature_path: Path) -> None:
    ds = xr.open_dataset(temperature_path)
    da = ds["t2m"]
    first_time = pd.to_datetime(ds["valid_time"].values[0])
    first_mean_c = float((da.isel(valid_time=0).mean(skipna=True).load().item()) - 273.15)

    print("=== TEMPERATURE ===")
    print(f"file: {temperature_path}")
    print(f"data_vars: {list(ds.data_vars)}")
    print(f"sizes: {dict(ds.sizes)}")
    print(f"prime date: {[str(pd.to_datetime(v).date()) for v in ds['valid_time'].values[:5]]}")
    print(f"prima data: {first_time}")
    print(f"media europea del primo timestep (C): {first_mean_c:.4f}")
    print()
    ds.close()


# Ispezioniamo metadati e primo timestep del dataset di precipitazione.
def show_precipitation_sample(precipitation_path: Path) -> None:
    ds = xr.open_dataset(precipitation_path)
    da = ds["tp"]
    first_time = pd.to_datetime(ds["valid_time"].values[0])
    first_days = calendar.monthrange(first_time.year, first_time.month)[1]
    first_mean_raw = float(da.isel(valid_time=0).mean(skipna=True).load().item())
    first_mean_mm = first_mean_raw * 1000.0
    rate_da = ds["avg_tprate"] if "avg_tprate" in ds.data_vars else None
    first_rate = (
        float(rate_da.isel(valid_time=0).mean(skipna=True).load().item())
        if rate_da is not None
        else None
    )

    print("=== PRECIPITATION ===")
    print(f"file: {precipitation_path}")
    print(f"data_vars: {list(ds.data_vars)}")
    print(f"tp attrs: {dict(da.attrs)}")
    print(f"sizes: {dict(ds.sizes)}")
    print(f"prime date: {[str(pd.to_datetime(v).date()) for v in ds['valid_time'].values[:5]]}")
    print(f"prima data: {first_time}")
    print(f"media europea del primo timestep tp raw (m): {first_mean_raw:.8f}")
    print(f"media europea del primo timestep come mm/giorno: {first_mean_mm:.4f}")
    print(f"media europea del primo timestep come mm/mese: {first_mean_mm * first_days:.4f}")
    if first_rate is not None:
        print(f"media europea avg_tprate raw (kg m-2 s-1): {first_rate:.10f}")
        print(f"media europea da avg_tprate come mm/giorno: {first_rate * 86400.0:.4f}")
        print(f"media europea da avg_tprate come mm/mese: {first_rate * 86400.0 * first_days:.4f}")
    print()
    ds.close()


# Carichiamo i path dal progetto e mostriamo la/le sorgente/i richieste.
def main() -> None:
    args = build_parser().parse_args()
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    biocube_dir = require_path("BIOCUBE_DIR")
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

    if args.source in {"all", "species"}:
        show_species_sample(species_path, args.rows)
    if args.source in {"all", "temperature"}:
        show_temperature_sample(temperature_path)
    if args.source in {"all", "precipitation"}:
        show_precipitation_sample(precipitation_path)


# Rendiamo lo script eseguibile da terminale.
if __name__ == "__main__":
    main()
