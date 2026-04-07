#!/usr/bin/env python3
"""Calcola i tre indicatori minimi per un'area selezionata e un periodo.

Questo è lo script unico pensato come backend del progetto:

- accetta una città europea predefinita
- oppure un punto con finestra spaziale
- oppure un bounding box selezionato manualmente sulla mappa

Produce due livelli di output:

- risultati mensili aggregati sull'area selezionata
- dataset `cella + mese` limitato alla sola area scelta
"""

from __future__ import annotations

import argparse
import math
import os
import re
from pathlib import Path

import pandas as pd
import xarray as xr
from dotenv import load_dotenv

from minimum_indicator_utils import (
    build_bbox_from_point,
    build_land_mask,
    filter_dataframe_month_range,
    filter_dataset_month_range,
    resolve_output_base_dir,
    snap_coordinates_to_grid,
    subset_bbox,
    subset_europe,
    write_tabular_outputs,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Manteniamo un piccolo catalogo locale di città europee utili per la futura interfaccia.
CITY_PRESETS = {
    "amsterdam": {"lat": 52.3676, "lon": 4.9041},
    "barcellona": {"lat": 41.3851, "lon": 2.1734},
    "barcelona": {"lat": 41.3851, "lon": 2.1734},
    "berlino": {"lat": 52.52, "lon": 13.405},
    "berlin": {"lat": 52.52, "lon": 13.405},
    "lisbona": {"lat": 38.7223, "lon": -9.1393},
    "lisbon": {"lat": 38.7223, "lon": -9.1393},
    "madrid": {"lat": 40.4168, "lon": -3.7038},
    "milan": {"lat": 45.4642, "lon": 9.19},
    "milano": {"lat": 45.4642, "lon": 9.19},
    "parigi": {"lat": 48.8566, "lon": 2.3522},
    "paris": {"lat": 48.8566, "lon": 2.3522},
    "roma": {"lat": 41.9028, "lon": 12.4964},
    "rome": {"lat": 41.9028, "lon": 12.4964},
    "varsavia": {"lat": 52.2297, "lon": 21.0122},
    "warsaw": {"lat": 52.2297, "lon": 21.0122},
    "vienna": {"lat": 48.2082, "lon": 16.3738},
}


# Leggiamo un path dal `.env` e verifichiamo che esista davvero.
def require_path(env_name: str) -> Path:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {env_name}")
    path = Path(value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Percorso non trovato per {env_name}: {path}")
    return path


# Convertiamo una label arbitraria in uno slug adatto ai nomi file.
def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return normalized.strip("_") or "selected_area"


# Definiamo gli argomenti CLI per selezionare area, periodo e formato di output.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Calcola gli indicatori minimi per una città o un'area europea in un dato periodo."
    )
    parser.add_argument("--start", help="Data iniziale, es. 2000-01-01")
    parser.add_argument("--end", help="Data finale, es. 2000-12-01")
    parser.add_argument("--label", default=None, help="Etichetta manuale dell'analisi.")
    parser.add_argument(
        "--output-mode",
        choices=["area", "cells", "both"],
        default="both",
        help="Se esportare solo l'area aggregata, solo le celle o entrambi.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Numero massimo di mesi da processare per un test veloce.",
    )
    parser.add_argument(
        "--list-cities",
        action="store_true",
        help="Stampa le città disponibili e termina.",
    )
    parser.add_argument("--city", help="Città europea predefinita, es. milano o paris.")
    parser.add_argument("--lat", type=float, help="Latitudine del punto di interesse.")
    parser.add_argument("--lon", type=float, help="Longitudine del punto di interesse.")
    parser.add_argument(
        "--half-window-deg",
        type=float,
        default=0.5,
        help="Semiampiezza del rettangolo attorno a una città o a un punto.",
    )
    parser.add_argument("--min-lat", type=float, help="Limite sud del bounding box.")
    parser.add_argument("--max-lat", type=float, help="Limite nord del bounding box.")
    parser.add_argument("--min-lon", type=float, help="Limite ovest del bounding box.")
    parser.add_argument("--max-lon", type=float, help="Limite est del bounding box.")
    return parser


# Stampiamo le città disponibili in modo leggibile.
def print_available_cities() -> None:
    print("Citta disponibili:")
    for city in sorted(CITY_PRESETS):
        coords = CITY_PRESETS[city]
        print(f"- {city}: lat={coords['lat']}, lon={coords['lon']}")


# Risolviamo l'area selezionata a partire da città, punto o bounding box.
def resolve_selection(args: argparse.Namespace) -> tuple[str, dict[str, float], str]:
    has_city = args.city is not None
    has_point = args.lat is not None and args.lon is not None
    has_bbox = None not in (args.min_lat, args.max_lat, args.min_lon, args.max_lon)

    selection_count = sum([has_city, has_point, has_bbox])
    if selection_count != 1:
        raise SystemExit(
            "Specifica esattamente una modalità di selezione: `--city`, `--lat --lon` oppure un bounding box completo."
        )

    if not args.start or not args.end:
        raise SystemExit("Devi specificare sia `--start` sia `--end`.")

    if has_city:
        city_key = args.city.strip().lower()
        if city_key not in CITY_PRESETS:
            raise SystemExit(f"Città non disponibile: {args.city}. Usa `--list-cities` per vedere le opzioni.")
        preset = CITY_PRESETS[city_key]
        bounds = build_bbox_from_point(
            lat=preset["lat"],
            lon=preset["lon"],
            half_window_deg=args.half_window_deg,
        )
        label = args.label or city_key
        return "city", bounds, label

    if has_point:
        bounds = build_bbox_from_point(
            lat=args.lat,
            lon=args.lon,
            half_window_deg=args.half_window_deg,
        )
        label = args.label or f"point_{args.lat}_{args.lon}"
        return "point", bounds, label

    bounds = {
        "min_lat": args.min_lat,
        "max_lat": args.max_lat,
        "min_lon": args.min_lon,
        "max_lon": args.max_lon,
    }
    label = args.label or "selected_bbox"
    return "bbox", bounds, label


# Carichiamo i tre file sorgente fondamentali direttamente da BioCube.
def resolve_source_paths(biocube_dir: Path) -> dict[str, Path]:
    return {
        "species": biocube_dir / "Species" / "europe_species.parquet",
        "temperature": (
            biocube_dir
            / "Copernicus"
            / "ERA5-monthly"
            / "era5-single"
            / "era5_single.nc"
        ),
        "precipitation": (
            biocube_dir
            / "Copernicus"
            / "ERA5-monthly"
            / "era5-climate-energy-moisture"
            / "era5-climate-energy-moisture-0.nc"
        ),
    }


# Calcoliamo le specie osservate per ogni cella e mese nell'area selezionata.
def compute_species_cell_month(
    species_path: Path,
    bounds: dict[str, float],
    start: str,
    end: str,
    max_steps: int | None = None,
) -> pd.DataFrame:
    df = pd.read_parquet(
        species_path,
        columns=["Species", "Latitude", "Longitude", "Timestamp"],
    )
    df = df.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})

    # Allineiamo le osservazioni specie alla griglia ERA5 0.25° prima del filtro e del merge.
    df["latitude"] = snap_coordinates_to_grid(df["latitude"])
    df["longitude"] = snap_coordinates_to_grid(df["longitude"])

    # Filtriamo solo le osservazioni che, una volta snapate, ricadono nell'area selezionata.
    df = df[
        (df["latitude"] >= bounds["min_lat"])
        & (df["latitude"] <= bounds["max_lat"])
        & (df["longitude"] >= bounds["min_lon"])
        & (df["longitude"] <= bounds["max_lon"])
    ].copy()
    df["month"] = pd.to_datetime(df["Timestamp"]).dt.to_period("M").dt.to_timestamp()
    df = filter_dataframe_month_range(
        df=df,
        month_column="month",
        start=start,
        end=end,
        max_steps=max_steps,
    )

    grouped = (
        df.groupby(["month", "latitude", "longitude"])["Species"]
        .nunique()
        .reset_index(name="species_count_observed_cell")
        .sort_values(["month", "latitude", "longitude"])
    )
    grouped["latitude"] = grouped["latitude"].round(2)
    grouped["longitude"] = grouped["longitude"].round(2)
    grouped["species_count_observed_cell"] = grouped["species_count_observed_cell"].astype("Int64")
    return grouped


# Calcoliamo le specie osservate per mese su tutta l'area, senza passare dal merge cella-per-cella.
def compute_species_area_monthly(
    species_path: Path,
    bounds: dict[str, float],
    start: str,
    end: str,
    max_steps: int | None = None,
) -> pd.DataFrame:
    df = pd.read_parquet(
        species_path,
        columns=["Species", "Latitude", "Longitude", "Timestamp"],
    )
    df["month"] = pd.to_datetime(df["Timestamp"]).dt.to_period("M").dt.to_timestamp()
    df = df[
        (df["Latitude"] >= bounds["min_lat"])
        & (df["Latitude"] <= bounds["max_lat"])
        & (df["Longitude"] >= bounds["min_lon"])
        & (df["Longitude"] <= bounds["max_lon"])
    ].copy()
    df = filter_dataframe_month_range(
        df=df,
        month_column="month",
        start=start,
        end=end,
        max_steps=max_steps,
    )

    grouped = (
        df.groupby("month")["Species"]
        .nunique()
        .reset_index(name="species_count_observed_area")
        .sort_values("month")
    )
    grouped["month"] = grouped["month"].dt.strftime("%Y-%m-%d")
    grouped["species_count_observed_area"] = grouped["species_count_observed_area"].astype("Int64")
    return grouped


# Creiamo il frame `cella + mese` dell'area selezionata, combinando clima e specie sulla stessa griglia.
def build_selected_cell_month_frame(
    ds_temp: xr.Dataset,
    ds_prec: xr.Dataset,
    land_mask: xr.DataArray,
    species_lookup: dict[str, pd.DataFrame],
    time_index: int,
) -> pd.DataFrame:
    month_ts = pd.to_datetime(ds_temp["valid_time"].values[time_index]).to_period("M").to_timestamp()
    month_key = str(month_ts.date())

    month_ds = xr.Dataset(
        {
            "temperature_mean_c": ds_temp["t2m"].isel(valid_time=time_index).where(land_mask) - 273.15,
            "precipitation_mean_mm": ds_prec["tp"].isel(valid_time=time_index).where(land_mask) * 1000.0,
        }
    )
    frame = month_ds.to_dataframe().reset_index()
    frame = frame.dropna(subset=["temperature_mean_c", "precipitation_mean_mm"], how="all")
    frame = frame[["latitude", "longitude", "temperature_mean_c", "precipitation_mean_mm"]].copy()
    frame["latitude"] = frame["latitude"].round(2)
    frame["longitude"] = frame["longitude"].round(2)
    frame["month"] = month_ts
    frame["cell_id"] = frame["latitude"].map(lambda v: f"{v:.2f}") + "_" + frame["longitude"].map(
        lambda v: f"{v:.2f}"
    )
    frame["latitude_weight"] = frame["latitude"].map(lambda value: math.cos(math.radians(value)))

    species_month = species_lookup.get(month_key)
    if species_month is None:
        frame["species_count_observed_cell"] = pd.Series([pd.NA] * len(frame), dtype="Int64")
    else:
        frame = frame.merge(species_month, on=["latitude", "longitude"], how="left")
        frame["species_count_observed_cell"] = frame["species_count_observed_cell"].astype("Int64")

    return frame[
        [
            "month",
            "latitude",
            "longitude",
            "cell_id",
            "latitude_weight",
            "species_count_observed_cell",
            "temperature_mean_c",
            "precipitation_mean_mm",
        ]
    ]


# Aggreghiamo il dataset `cella + mese` in una tabella mensile dell'area selezionata.
def compute_area_climate_monthly(cell_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, float | int | str]] = []

    for month, frame in cell_df.groupby("month", sort=True):
        weights = frame["latitude_weight"]
        records.append(
            {
                "month": str(pd.Timestamp(month).date()),
                "temperature_mean_area_c": float(
                    (frame["temperature_mean_c"] * weights).sum() / weights.sum()
                ),
                "precipitation_mean_area_mm": float(
                    (frame["precipitation_mean_mm"] * weights).sum() / weights.sum()
                ),
                "cell_count_land": int(len(frame)),
                "cells_with_species_records": int(frame["species_count_observed_cell"].notna().sum()),
            }
        )

    return pd.DataFrame.from_records(records)


# Prepariamo i dataset climatici già ritagliati su Europa, periodo e bounding box selezionato.
def load_climate_datasets(
    source_paths: dict[str, Path],
    bounds: dict[str, float],
    start: str,
    end: str,
    max_steps: int | None,
) -> tuple[xr.Dataset, xr.Dataset, xr.DataArray]:
    # Apriamo, normalizziamo, filtriamo nel tempo e ritagliamo il dataset temperatura.
    ds_temp = subset_bbox(
        filter_dataset_month_range(
            subset_europe(xr.open_dataset(source_paths["temperature"])),
            start=start,
            end=end,
            max_steps=max_steps,
        ),
        bounds=bounds,
    )

    # Applichiamo la stessa pipeline a precipitazione per mantenere le due griglie allineate.
    ds_prec = subset_bbox(
        filter_dataset_month_range(
            subset_europe(xr.open_dataset(source_paths["precipitation"])),
            start=start,
            end=end,
            max_steps=max_steps,
        ),
        bounds=bounds,
    )

    if ds_temp.sizes.get("latitude", 0) == 0 or ds_temp.sizes.get("longitude", 0) == 0:
        raise SystemExit("Il bounding box selezionato non interseca celle climatiche valide in Europa.")

    land_mask = build_land_mask(ds_temp)
    return ds_temp, ds_prec, land_mask


# Eseguiamo l'intera pipeline: selezione area, costruzione celle, aggregazione e salvataggio output.
def main() -> None:
    args = build_parser().parse_args()
    if args.list_cities:
        print_available_cities()
        return

    load_dotenv(PROJECT_ROOT / ".env")

    biocube_dir = require_path("BIOCUBE_DIR")
    output_dir = require_path("PROJECT_OUTPUT_DIR")
    source_paths = resolve_source_paths(biocube_dir)

    selection_mode, bounds, label = resolve_selection(args)
    stem_base = f"selected_{slugify(label)}"

    species_cell = compute_species_cell_month(
        species_path=source_paths["species"],
        bounds=bounds,
        start=args.start,
        end=args.end,
        max_steps=args.max_steps,
    )
    species_lookup = {
        str(month.date()): frame[["latitude", "longitude", "species_count_observed_cell"]]
        for month, frame in species_cell.groupby("month")
    }
    species_area_monthly = compute_species_area_monthly(
        species_path=source_paths["species"],
        bounds=bounds,
        start=args.start,
        end=args.end,
        max_steps=args.max_steps,
    )

    ds_temp, ds_prec, land_mask = load_climate_datasets(
        source_paths=source_paths,
        bounds=bounds,
        start=args.start,
        end=args.end,
        max_steps=args.max_steps,
    )

    try:
        cell_frames = []
        for idx in range(ds_temp.sizes["valid_time"]):
            cell_frames.append(
                build_selected_cell_month_frame(
                    ds_temp=ds_temp,
                    ds_prec=ds_prec,
                    land_mask=land_mask,
                    species_lookup=species_lookup,
                    time_index=idx,
                )
            )
    finally:
        ds_temp.close()
        ds_prec.close()

    if not cell_frames:
        raise SystemExit("Nessun timestep disponibile nel periodo selezionato.")

    cell_df = pd.concat(cell_frames, ignore_index=True)
    area_climate_monthly = compute_area_climate_monthly(cell_df)
    area_monthly = (
        area_climate_monthly
        .merge(species_area_monthly, on="month", how="outer")
        .sort_values("month")
    )

    base_dir, used_fallback = resolve_output_base_dir(output_dir, PROJECT_ROOT)
    cell_parquet_path: Path | None = None
    area_output_paths: dict[str, Path] = {}

    if args.output_mode in {"cells", "both"}:
        cell_parquet_path = base_dir / f"{stem_base}_cells.parquet"
        cell_df.to_parquet(cell_parquet_path, index=False)

    summary = {
        "mode": "selected_area_indicators",
        "selection_mode": selection_mode,
        "label": label,
        "bounds": bounds,
        "start": args.start,
        "end": args.end,
        "time_steps": int(area_monthly["month"].nunique()),
        "cell_rows": int(len(cell_df)),
        "cell_output_parquet": str(cell_parquet_path) if cell_parquet_path else None,
        "species_months_with_records": int(area_monthly["species_count_observed_area"].notna().sum()),
        "species_semantics_area": "species_count_observed_area = numero di specie osservate nell'area selezionata per mese",
        "species_semantics_cells": "species_count_observed_cell = numero di specie osservate nella singola cella e mese",
        "species_note": "NaN sulle specie significa che nel dataset non risultano osservazioni per quella cella o area e in quel mese",
        "temperature_source": str(source_paths["temperature"]),
        "precipitation_source": str(source_paths["precipitation"]),
        "species_source": str(source_paths["species"]),
    }

    if args.output_mode in {"area", "both"}:
        area_output_paths, fallback_from_writer = write_tabular_outputs(
            summary=summary,
            table_df=area_monthly,
            stem=f"{stem_base}_area_monthly",
            output_dir=base_dir,
            project_root=PROJECT_ROOT,
        )
        used_fallback = used_fallback or fallback_from_writer
    else:
        summary_path = base_dir / f"{stem_base}_cells_summary.json"
        summary_path.write_text(pd.Series(summary).to_json(force_ascii=False, indent=2))
        area_output_paths = {"summary": summary_path}

    print("Selezione area/periodo completata.")
    print(pd.Series(summary).to_json(force_ascii=False, indent=2))
    print(f"\nSummary: {area_output_paths['summary']}")
    if "csv" in area_output_paths:
        print(f"CSV: {area_output_paths['csv']}")
        print(f"CSV Excel: {area_output_paths['excel_csv']}")
        print(f"XLSX: {area_output_paths['xlsx']}")
    if cell_parquet_path is not None:
        print(f"Parquet celle: {cell_parquet_path}")
    if used_fallback:
        print(
            "\nNota: ho usato la cartella locale del repo perché il path esterno non era "
            "scrivibile in questo ambiente."
        )


# Rendiamo lo script eseguibile da terminale.
if __name__ == "__main__":
    main()
