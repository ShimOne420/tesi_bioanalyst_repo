#!/usr/bin/env python3
"""Calcola gli indicatori osservativi BIOMAP per un'area selezionata e un periodo.

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

import numpy as np
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
        description="Calcola gli indicatori osservativi BIOMAP per una città o un'area europea in un dato periodo."
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


# Carichiamo i file sorgente fondamentali direttamente da BioCube.
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
        "edaphic": (
            biocube_dir
            / "Copernicus"
            / "ERA5-monthly"
            / "era5-edaphic"
            / "era5-edaphic-0.nc"
        ),
        "ndvi_csv": biocube_dir / "Land" / "Europe_ndvi_monthly_un_025.csv",
        "vegetation_dynamic": (
            biocube_dir
            / "Copernicus"
            / "ERA5-monthly"
            / "era5-land-vegetation"
            / "data_stream-moda.nc"
        ),
        "agriculture": biocube_dir / "Agriculture" / "Europe_combined_agriculture_data.csv",
    }


def month_number_from_value(value: object) -> int:
    """Converte valori mese numerici o testuali in 1..12."""
    if pd.isna(value):
        raise ValueError("Mese mancante.")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        month_number = int(value)
        if 1 <= month_number <= 12:
            return month_number

    text = str(value).strip()
    if text.isdigit():
        month_number = int(text)
        if 1 <= month_number <= 12:
            return month_number

    lookup = {
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
    normalized = re.sub(r"[^a-zA-Z]+", "", text).casefold()
    if normalized in lookup:
        return lookup[normalized]

    parsed = pd.to_datetime(text, errors="coerce")
    if not pd.isna(parsed):
        return int(parsed.month)

    raise ValueError(f"Mese non riconosciuto: {value}")


def find_value_column(columns: list[str], variable_name: str) -> str:
    candidates = [
        variable_name,
        variable_name.lower(),
        variable_name.upper(),
        "value",
        "Value",
        "mean",
        "Mean",
        "mean_value",
        "Mean_Value",
        f"{variable_name}_value",
        f"{variable_name}_mean",
        f"mean_{variable_name}",
    ]
    lookup = {str(column).casefold(): str(column) for column in columns}
    for candidate in candidates:
        match = lookup.get(candidate.casefold())
        if match is not None:
            return match

    ignored = {
        "country",
        "latitude",
        "longitude",
        "lat",
        "lon",
        "year",
        "month",
        "date",
        "timestamp",
        "valid_time",
        "variable",
    }
    for column in columns:
        column_text = str(column)
        if column_text.casefold() not in ignored:
            return column_text

    raise KeyError(f"Nessuna colonna valore trovata per {variable_name}.")


def find_monthly_column(columns: list[str], variable_name: str, month: pd.Timestamp) -> str:
    month = pd.Timestamp(month).to_period("M").to_timestamp()
    month_number = int(month.month)
    candidates = [
        f"{variable_name}_{month:%Y_%m}",
        f"{variable_name}_{month:%Y-%m}",
        f"{variable_name}_{month:%Y%m}",
        f"{variable_name}_{month:%Y-%m-%d}",
        f"{variable_name}_{month.year}_{month_number}",
        f"{variable_name}_{month.year}-{month_number}",
        f"{month:%Y_%m}_{variable_name}",
        f"{month:%Y-%m}_{variable_name}",
        f"{month:%Y_%m}",
        f"{month:%Y-%m}",
        f"{month:%Y%m}",
        f"{month:%Y-%m-%d}",
        f"{month.year}_{month_number}",
        f"{month.year}-{month_number}",
    ]
    lookup = {str(column).casefold(): str(column) for column in columns}
    for candidate in candidates:
        match = lookup.get(candidate.casefold())
        if match is not None:
            return match

    month_tokens = {
        f"{month_number}",
        f"{month_number:02d}",
        month.strftime("%b").lower(),
        month.strftime("%B").lower(),
    }
    regex_matches = []
    for column in columns:
        column_text = str(column)
        normalized = re.sub(r"[^a-zA-Z0-9]+", " ", column_text).casefold()
        tokens = set(normalized.split())
        if str(month.year) in tokens and tokens.intersection(month_tokens):
            regex_matches.append(column_text)

    if regex_matches:
        with_variable_name = [name for name in regex_matches if variable_name.casefold() in name.casefold()]
        return with_variable_name[0] if with_variable_name else regex_matches[0]

    raise KeyError(f"Colonna mensile {variable_name} non trovata per {month:%Y-%m}.")


def prepare_grid_frame(frame: pd.DataFrame, bounds: dict[str, float]) -> pd.DataFrame:
    lat_column = next((name for name in ("Latitude", "latitude", "lat", "LAT") if name in frame.columns), None)
    lon_column = next((name for name in ("Longitude", "longitude", "lon", "LON") if name in frame.columns), None)
    if lat_column is None or lon_column is None:
        raise KeyError("Colonne latitudine/longitudine mancanti nel CSV.")

    prepared = frame.rename(columns={lat_column: "latitude", lon_column: "longitude"}).copy()
    prepared["latitude"] = snap_coordinates_to_grid(prepared["latitude"])
    prepared["longitude"] = snap_coordinates_to_grid(prepared["longitude"])
    return prepared[
        (prepared["latitude"] >= bounds["min_lat"])
        & (prepared["latitude"] <= bounds["max_lat"])
        & (prepared["longitude"] >= bounds["min_lon"])
        & (prepared["longitude"] <= bounds["max_lon"])
    ].copy()


def frame_lookup_by_month(frame: pd.DataFrame, value_column: str) -> dict[str, pd.DataFrame]:
    if frame.empty:
        return {}

    useful = frame[["month", "latitude", "longitude", value_column]].copy()
    useful[value_column] = pd.to_numeric(useful[value_column], errors="coerce")
    useful = useful.dropna(subset=[value_column])
    useful = (
        useful.groupby(["month", "latitude", "longitude"], as_index=False)[value_column]
        .mean()
        .sort_values(["month", "latitude", "longitude"])
    )
    useful["month"] = pd.to_datetime(useful["month"]).dt.to_period("M").dt.to_timestamp()
    return {
        str(month.date()): month_frame[["latitude", "longitude", value_column]]
        for month, month_frame in useful.groupby("month")
    }


def build_ndvi_from_csv(
    ndvi_path: Path,
    bounds: dict[str, float],
    months: list[pd.Timestamp],
) -> tuple[dict[str, pd.DataFrame], str]:
    ndvi_frame = prepare_grid_frame(pd.read_csv(ndvi_path), bounds)
    if ndvi_frame.empty:
        return {}, "NDVI CSV presente ma senza celle nell'area selezionata."

    date_column = next(
        (name for name in ("Timestamp", "timestamp", "Date", "date", "Month", "month", "valid_time") if name in ndvi_frame.columns),
        None,
    )
    year_column = next((name for name in ("Year", "year", "YEAR", "Anno", "anno") if name in ndvi_frame.columns), None)
    month_column = next((name for name in ("Month", "month", "MONTH", "Mese", "mese") if name in ndvi_frame.columns), None)
    ndvi_column = next((name for name in ("NDVI", "ndvi") if name in ndvi_frame.columns), None)

    if year_column and month_column:
        value_column = ndvi_column or find_value_column(ndvi_frame.columns.tolist(), "NDVI")
        dated = ndvi_frame.copy()
        dated["_year"] = pd.to_numeric(dated[year_column], errors="coerce").astype("Int64")
        dated["_month_number"] = dated[month_column].map(month_number_from_value)
        dated["month"] = pd.to_datetime(
            {
                "year": dated["_year"].astype("Int64"),
                "month": dated["_month_number"],
                "day": 1,
            },
            errors="coerce",
        )
        dated["ndvi"] = dated[value_column]
        return frame_lookup_by_month(dated, "ndvi"), "NDVI da CSV BioCube ufficiale."

    if date_column:
        value_column = ndvi_column or find_value_column(ndvi_frame.columns.tolist(), "NDVI")
        dated = ndvi_frame.copy()
        dated["month"] = pd.to_datetime(dated[date_column]).dt.to_period("M").dt.to_timestamp()
        dated["ndvi"] = dated[value_column]
        return frame_lookup_by_month(dated, "ndvi"), "NDVI da CSV BioCube ufficiale."

    monthly_frames = []
    for month in months:
        column_name = find_monthly_column(ndvi_frame.columns.tolist(), "NDVI", month)
        month_frame = ndvi_frame[["latitude", "longitude", column_name]].copy()
        month_frame = month_frame.rename(columns={column_name: "ndvi"})
        month_frame["month"] = month
        monthly_frames.append(month_frame)

    merged = pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame()
    return frame_lookup_by_month(merged, "ndvi"), "NDVI da CSV BioCube ufficiale."


def build_ndvi_from_vegetation_proxy(
    vegetation_path: Path,
    bounds: dict[str, float],
    start: str,
    end: str,
    max_steps: int | None,
) -> tuple[dict[str, pd.DataFrame], str]:
    with xr.open_dataset(vegetation_path) as ds_raw:
        ds = subset_bbox(
            filter_dataset_month_range(
                subset_europe(ds_raw),
                start=start,
                end=end,
                max_steps=max_steps,
            ),
            bounds=bounds,
        )

        ndvi_var = next((name for name in ("NDVI", "ndvi") if name in ds.data_vars), None)
        if ndvi_var is not None:
            ndvi = ds[ndvi_var]
            note = "NDVI da dataset vegetation NetCDF."
        elif {"lai_hv", "lai_lv"}.issubset(ds.data_vars):
            total_lai = ds["lai_hv"].fillna(0.0) + ds["lai_lv"].fillna(0.0)
            ndvi = (1.0 - np.exp(-0.5 * total_lai)).clip(min=0.0, max=0.92)
            note = "NDVI proxy stimato da LAI (`lai_hv + lai_lv`), non NDVI osservato puro."
        else:
            raise KeyError("Dataset vegetation senza NDVI e senza lai_hv/lai_lv.")

        frame = ndvi.to_dataset(name="ndvi").to_dataframe().reset_index()

    frame = frame.rename(columns={"valid_time": "month"})
    frame["month"] = pd.to_datetime(frame["month"]).dt.to_period("M").dt.to_timestamp()
    frame["latitude"] = frame["latitude"].round(2)
    frame["longitude"] = frame["longitude"].round(2)
    return frame_lookup_by_month(frame, "ndvi"), note


def load_ndvi_lookup(
    source_paths: dict[str, Path],
    bounds: dict[str, float],
    start: str,
    end: str,
    max_steps: int | None,
    months: list[pd.Timestamp],
) -> tuple[dict[str, pd.DataFrame], str]:
    ndvi_path = source_paths["ndvi_csv"]
    if ndvi_path.exists():
        try:
            lookup, note = build_ndvi_from_csv(ndvi_path, bounds, months)
            if lookup:
                return lookup, note
        except Exception as exc:
            csv_error = f"NDVI CSV non utilizzabile ({exc})."
        else:
            csv_error = "NDVI CSV senza valori utili per l'area selezionata."
    else:
        csv_error = "NDVI CSV BioCube non trovato."

    vegetation_path = source_paths["vegetation_dynamic"]
    if vegetation_path.exists():
        try:
            lookup, note = build_ndvi_from_vegetation_proxy(
                vegetation_path=vegetation_path,
                bounds=bounds,
                start=start,
                end=end,
                max_steps=max_steps,
            )
            return lookup, f"{csv_error} Fallback attivo: {note}"
        except Exception as exc:
            return {}, f"{csv_error} Fallback LAI non utilizzabile ({exc}). NDVI non disponibile."

    return {}, f"{csv_error} Dataset vegetation fallback non trovato. NDVI non disponibile."


def find_agriculture_year_column(columns: list[str], year: int) -> tuple[str, str | None]:
    exact = f"Agri_{year}"
    lookup = {str(column).casefold(): str(column) for column in columns}
    if exact.casefold() in lookup:
        return lookup[exact.casefold()], None

    year_columns = []
    for column in columns:
        match = re.fullmatch(r"Agri[_\-\s]?(\d{4})", str(column), flags=re.IGNORECASE)
        if match:
            year_columns.append((int(match.group(1)), str(column)))

    if not year_columns:
        raise KeyError("Nessuna colonna annuale `Agri_YYYY` trovata nel CSV agriculture.")

    year_columns.sort()
    previous = [item for item in year_columns if item[0] <= year]
    chosen_year, chosen_column = previous[-1] if previous else year_columns[-1]
    return chosen_column, f"Cropland usa `Agri_{chosen_year}` come layer annuale/statico per {year}."


def load_cropland_lookup(
    agriculture_path: Path,
    bounds: dict[str, float],
    months: list[pd.Timestamp],
) -> tuple[dict[str, pd.DataFrame], str]:
    if not agriculture_path.exists():
        return {}, "CSV Agriculture non trovato. Cropland non disponibile."

    agriculture = prepare_grid_frame(pd.read_csv(agriculture_path), bounds)
    if agriculture.empty:
        return {}, "CSV Agriculture presente ma senza celle nell'area selezionata."

    if "Variable" in agriculture.columns:
        variable_frame = agriculture[
            agriculture["Variable"].astype(str).str.casefold() == "cropland"
        ].copy()
        if variable_frame.empty:
            return {}, "Variabile `Cropland` non trovata nel CSV Agriculture."
    else:
        variable_frame = agriculture.copy()

    monthly_frames = []
    fallback_notes: set[str] = set()
    for month in months:
        year = int(pd.Timestamp(month).year)
        column_name, fallback_note = find_agriculture_year_column(variable_frame.columns.tolist(), year)
        if fallback_note:
            fallback_notes.add(fallback_note)

        month_frame = variable_frame[["latitude", "longitude", column_name]].copy()
        month_frame = month_frame.rename(columns={column_name: "cropland"})
        month_frame["month"] = month
        monthly_frames.append(month_frame)

    merged = pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame()
    note = "Cropland da CSV Agriculture europeo."
    if fallback_notes:
        note = f"{note} " + " ".join(sorted(fallback_notes))
    return frame_lookup_by_month(merged, "cropland"), note


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
    ds_edaphic: xr.Dataset | None,
    land_mask: xr.DataArray,
    species_lookup: dict[str, pd.DataFrame],
    ndvi_lookup: dict[str, pd.DataFrame],
    cropland_lookup: dict[str, pd.DataFrame],
    time_index: int,
) -> pd.DataFrame:
    month_ts = pd.to_datetime(ds_temp["valid_time"].values[time_index]).to_period("M").to_timestamp()
    month_key = str(month_ts.date())

    month_variables = {
        "temperature_mean_c": ds_temp["t2m"].isel(valid_time=time_index).where(land_mask) - 273.15,
        "precipitation_mean_mm": ds_prec["tp"].isel(valid_time=time_index).where(land_mask) * 1000.0,
    }

    if ds_edaphic is not None:
        if "swvl1" in ds_edaphic.data_vars:
            month_variables["swvl1"] = ds_edaphic["swvl1"].isel(valid_time=time_index).where(land_mask)
        if "swvl2" in ds_edaphic.data_vars:
            month_variables["swvl2"] = ds_edaphic["swvl2"].isel(valid_time=time_index).where(land_mask)

    month_ds = xr.Dataset(month_variables)
    frame = month_ds.to_dataframe().reset_index()
    frame = frame.dropna(subset=["temperature_mean_c", "precipitation_mean_mm"], how="all")
    for optional_column in ("swvl1", "swvl2"):
        if optional_column not in frame.columns:
            frame[optional_column] = pd.NA

    frame = frame[
        ["latitude", "longitude", "temperature_mean_c", "precipitation_mean_mm", "swvl1", "swvl2"]
    ].copy()
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

    ndvi_month = ndvi_lookup.get(month_key)
    if ndvi_month is None:
        frame["ndvi"] = pd.NA
    else:
        frame = frame.merge(ndvi_month, on=["latitude", "longitude"], how="left")

    cropland_month = cropland_lookup.get(month_key)
    if cropland_month is None:
        frame["cropland"] = pd.NA
    else:
        frame = frame.merge(cropland_month, on=["latitude", "longitude"], how="left")

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
            "ndvi",
            "swvl1",
            "swvl2",
            "cropland",
        ]
    ]


# Aggreghiamo il dataset `cella + mese` in una tabella mensile dell'area selezionata.
def weighted_area_mean(frame: pd.DataFrame, value_column: str) -> float | None:
    values = pd.to_numeric(frame[value_column], errors="coerce")
    weights = pd.to_numeric(frame["latitude_weight"], errors="coerce")
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return None
    return float((values[valid] * weights[valid]).sum() / weights[valid].sum())


def compute_area_monthly(cell_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, float | int | str]] = []

    for month, frame in cell_df.groupby("month", sort=True):
        records.append(
            {
                "month": str(pd.Timestamp(month).date()),
                "temperature_mean_area_c": weighted_area_mean(frame, "temperature_mean_c"),
                "precipitation_mean_area_mm": weighted_area_mean(frame, "precipitation_mean_mm"),
                "ndvi_mean_area": weighted_area_mean(frame, "ndvi"),
                "soil_water_surface_mean_area": weighted_area_mean(frame, "swvl1"),
                "soil_water_deep_mean_area": weighted_area_mean(frame, "swvl2"),
                "cropland_mean_area": weighted_area_mean(frame, "cropland"),
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
) -> tuple[xr.Dataset, xr.Dataset, xr.Dataset | None, xr.DataArray, str]:
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
    edaphic_note = "swvl1/swvl2 non disponibili: dataset edaphic non trovato."
    ds_edaphic = None
    if source_paths["edaphic"].exists():
        ds_edaphic = subset_bbox(
            filter_dataset_month_range(
                subset_europe(xr.open_dataset(source_paths["edaphic"])),
                start=start,
                end=end,
                max_steps=max_steps,
            ),
            bounds=bounds,
        )
        missing_edaphic = [name for name in ("swvl1", "swvl2") if name not in ds_edaphic.data_vars]
        if missing_edaphic:
            edaphic_note = f"Dataset edaphic presente, ma mancano: {', '.join(missing_edaphic)}."
        else:
            edaphic_note = "Umidita del suolo da ERA5 edaphic (`swvl1`, `swvl2`)."

    return ds_temp, ds_prec, ds_edaphic, land_mask, edaphic_note


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

    ds_temp, ds_prec, ds_edaphic, land_mask, edaphic_note = load_climate_datasets(
        source_paths=source_paths,
        bounds=bounds,
        start=args.start,
        end=args.end,
        max_steps=args.max_steps,
    )
    months = [
        pd.to_datetime(value).to_period("M").to_timestamp()
        for value in ds_temp["valid_time"].values
    ]
    ndvi_lookup, ndvi_note = load_ndvi_lookup(
        source_paths=source_paths,
        bounds=bounds,
        start=args.start,
        end=args.end,
        max_steps=args.max_steps,
        months=months,
    )
    cropland_lookup, cropland_note = load_cropland_lookup(
        agriculture_path=source_paths["agriculture"],
        bounds=bounds,
        months=months,
    )

    try:
        cell_frames = []
        for idx in range(ds_temp.sizes["valid_time"]):
            cell_frames.append(
                build_selected_cell_month_frame(
                    ds_temp=ds_temp,
                    ds_prec=ds_prec,
                    ds_edaphic=ds_edaphic,
                    land_mask=land_mask,
                    species_lookup=species_lookup,
                    ndvi_lookup=ndvi_lookup,
                    cropland_lookup=cropland_lookup,
                    time_index=idx,
                )
            )
    finally:
        ds_temp.close()
        ds_prec.close()
        if ds_edaphic is not None:
            ds_edaphic.close()

    if not cell_frames:
        raise SystemExit("Nessun timestep disponibile nel periodo selezionato.")

    cell_df = pd.concat(cell_frames, ignore_index=True)
    area_climate_monthly = compute_area_monthly(cell_df)
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
        "indicator_notes": [
            "Temperatura da ERA5 `t2m`, convertita da Kelvin a Celsius.",
            "Precipitazione da ERA5 `tp`, convertita in millimetri.",
            edaphic_note,
            ndvi_note,
            cropland_note,
            "NaN sulle variabili fisiche significa sorgente assente o nessuna cella valida per area/mese.",
        ],
        "temperature_source": str(source_paths["temperature"]),
        "precipitation_source": str(source_paths["precipitation"]),
        "edaphic_source": str(source_paths["edaphic"]),
        "ndvi_csv_source": str(source_paths["ndvi_csv"]),
        "vegetation_dynamic_source": str(source_paths["vegetation_dynamic"]),
        "agriculture_source": str(source_paths["agriculture"]),
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
