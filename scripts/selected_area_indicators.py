#!/usr/bin/env python3
"""Calcola gli indicatori osservativi per un'area selezionata e un periodo.

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
import calendar
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


def resolve_output_dir(env_name: str) -> Path:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {env_name}")
    path = Path(value).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


# Convertiamo una label arbitraria in uno slug adatto ai nomi file.
def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return normalized.strip("_") or "selected_area"


def days_in_month(month_ts: pd.Timestamp) -> int:
    return calendar.monthrange(month_ts.year, month_ts.month)[1]


def weighted_mean(frame: pd.DataFrame, value_column: str, weight_column: str = "latitude_weight") -> float:
    values = pd.to_numeric(frame[value_column], errors="coerce")
    weights = pd.to_numeric(frame[weight_column], errors="coerce")
    valid = values.notna() & weights.notna()
    if not valid.any():
        return float("nan")
    return float((values[valid] * weights[valid]).sum() / weights[valid].sum())


def optional_path(path: Path) -> Path | None:
    return path if path.exists() else None


def read_spatial_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return pd.read_csv(path, low_memory=False)
    if suffix in {".xlsx", ".xls"}:
        workbook = pd.ExcelFile(path)
        for sheet_name in workbook.sheet_names:
            preview = pd.read_excel(workbook, sheet_name=sheet_name, nrows=0)
            columns = {str(column).strip().casefold() for column in preview.columns}
            if columns & {"latitude", "lat"} and columns & {"longitude", "lon", "long"}:
                return pd.read_excel(workbook, sheet_name=sheet_name)
        raise ValueError(f"Nessun foglio con coordinate trovato in {path}")
    raise ValueError(f"Formato tabellare non supportato: {path.suffix}")


def coordinate_columns(df: pd.DataFrame) -> tuple[str, str]:
    columns = {str(column).strip().casefold(): column for column in df.columns}
    lat_column = next((columns[name] for name in ("latitude", "lat") if name in columns), None)
    lon_column = next((columns[name] for name in ("longitude", "lon", "long") if name in columns), None)
    if lat_column is None or lon_column is None:
        raise KeyError("La tabella non contiene colonne latitude/longitude.")
    return str(lat_column), str(lon_column)


def prepare_spatial_frame(df: pd.DataFrame) -> pd.DataFrame:
    lat_column, lon_column = coordinate_columns(df)
    frame = df.rename(columns={lat_column: "latitude", lon_column: "longitude"}).copy()
    frame["latitude"] = snap_coordinates_to_grid(pd.to_numeric(frame["latitude"], errors="coerce"))
    frame["longitude"] = snap_coordinates_to_grid(pd.to_numeric(frame["longitude"], errors="coerce"))
    return frame.dropna(subset=["latitude", "longitude"])


def month_number_from_value(value: object) -> int | None:
    if pd.isna(value):
        return None
    if isinstance(value, (int, float, np.integer, np.floating)):
        month = int(value)
        return month if 1 <= month <= 12 else None
    text = str(value).strip()
    if text.isdigit():
        month = int(text)
        return month if 1 <= month <= 12 else None
    lookup = {
        "jan": 1,
        "january": 1,
        "gen": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "mag": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }
    lowered = text.casefold()
    return lookup.get(lowered) or lookup.get(lowered[:3])


def value_column(df: pd.DataFrame, variable_name: str) -> str:
    lower_to_column = {str(column).strip().casefold(): str(column) for column in df.columns}
    for candidate in (variable_name, variable_name.lower(), "value", "Value"):
        if candidate.casefold() in lower_to_column:
            return lower_to_column[candidate.casefold()]
    for column in df.columns:
        if variable_name.casefold() in str(column).casefold():
            return str(column)
    raise KeyError(f"Colonna valore non trovata per {variable_name}.")


def parse_month_from_column_name(column: str, variable_name: str) -> pd.Timestamp | None:
    if variable_name.casefold() not in str(column).casefold():
        return None
    for pattern in (
        r"(?P<month>\d{1,2})[\/_-](?P<year>\d{4})",
        r"(?P<year>\d{4})[\/_-](?P<month>\d{1,2})",
        r"(?P<year>\d{4})(?P<month>\d{2})",
    ):
        match = re.search(pattern, str(column))
        if not match:
            continue
        month = int(match.group("month"))
        year = int(match.group("year"))
        if 1 <= month <= 12:
            return pd.Timestamp(year=year, month=month, day=1)
    return None


def find_monthly_column(columns: list[str], variable_name: str, month: pd.Timestamp) -> str:
    month = month.to_period("M").to_timestamp()
    direct_candidates = [
        f"{variable_name}_{month:%m/%Y}",
        f"{variable_name}_{month.month}/{month.year}",
        f"{variable_name}_{month:%Y_%m}",
        f"{variable_name}_{month:%Y-%m}",
        f"{variable_name}_{month:%Y%m}",
    ]
    columns_by_name = {str(column): str(column) for column in columns}
    for candidate in direct_candidates:
        if candidate in columns_by_name:
            return columns_by_name[candidate]
    for column in columns:
        parsed = parse_month_from_column_name(str(column), variable_name)
        if parsed is not None and parsed == month:
            return str(column)
    raise KeyError(f"Colonna mensile {variable_name} non trovata per {month:%Y-%m}.")


def build_monthly_table_layer(
    table: pd.DataFrame | None,
    month: pd.Timestamp,
    variable_name: str,
    output_column: str,
) -> pd.DataFrame:
    if table is None:
        return pd.DataFrame(columns=["latitude", "longitude", output_column])

    frame = prepare_spatial_frame(table)
    year_column = next((name for name in ("Year", "year", "YEAR", "Anno", "anno") if name in frame.columns), None)
    month_column = next((name for name in ("Month", "month", "MONTH", "Mese", "mese") if name in frame.columns), None)
    date_column = next(
        (name for name in ("Timestamp", "timestamp", "Date", "date", "valid_time") if name in frame.columns),
        None,
    )

    if year_column and month_column:
        local = frame.copy()
        local["_year"] = pd.to_numeric(local[year_column], errors="coerce")
        local["_month"] = local[month_column].map(month_number_from_value)
        local = local[(local["_year"] == month.year) & (local["_month"] == month.month)]
        selected_value_column = value_column(local, variable_name)
    elif date_column:
        local = frame.copy()
        local["_month_start"] = pd.to_datetime(local[date_column], errors="coerce").dt.to_period("M").dt.to_timestamp()
        local = local[local["_month_start"] == month.to_period("M").to_timestamp()]
        selected_value_column = value_column(local, variable_name)
    else:
        try:
            selected_value_column = find_monthly_column([str(column) for column in frame.columns], variable_name, month)
        except KeyError:
            return pd.DataFrame(columns=["latitude", "longitude", output_column])
        local = frame

    if local.empty:
        return pd.DataFrame(columns=["latitude", "longitude", output_column])

    return (
        local[["latitude", "longitude", selected_value_column]]
        .rename(columns={selected_value_column: output_column})
        .assign(**{output_column: lambda df: pd.to_numeric(df[output_column], errors="coerce")})
        .dropna(subset=[output_column])
        .groupby(["latitude", "longitude"], as_index=False)[output_column]
        .mean()
    )


def find_yearly_column(columns: list[str], prefix: str, year: int) -> str:
    candidates = [f"{prefix}_{year}", f"{prefix}{year}", str(year)]
    for candidate in candidates:
        if candidate in columns:
            return candidate
    year_columns = []
    for column in columns:
        match = re.search(r"(?P<year>\d{4})", str(column))
        if match:
            year_columns.append((int(match.group("year")), str(column)))
    past_or_current = [(column_year, column) for column_year, column in year_columns if column_year <= year]
    if past_or_current:
        return max(past_or_current, key=lambda item: item[0])[1]
    raise KeyError(f"Colonna annuale {prefix}_{year} non trovata.")


def build_annual_table_layer(
    table: pd.DataFrame | None,
    month: pd.Timestamp,
    variable_name: str,
    output_column: str,
) -> pd.DataFrame:
    if table is None:
        return pd.DataFrame(columns=["latitude", "longitude", output_column])

    frame = prepare_spatial_frame(table)
    if "Variable" in frame.columns:
        frame = frame[frame["Variable"].astype(str).str.casefold() == variable_name.casefold()]
    if frame.empty:
        return pd.DataFrame(columns=["latitude", "longitude", output_column])

    selected_value_column = find_yearly_column([str(column) for column in frame.columns], "Agri", month.year)
    return (
        frame[["latitude", "longitude", selected_value_column]]
        .rename(columns={selected_value_column: output_column})
        .assign(**{output_column: lambda df: pd.to_numeric(df[output_column], errors="coerce")})
        .dropna(subset=[output_column])
        .groupby(["latitude", "longitude"], as_index=False)[output_column]
        .mean()
    )


def merge_layer(frame: pd.DataFrame, layer: pd.DataFrame, value_column_name: str) -> pd.DataFrame:
    if layer.empty:
        frame[value_column_name] = np.nan
        return frame
    return frame.merge(layer, on=["latitude", "longitude"], how="left")


def empty_land_layer(land_mask: xr.DataArray) -> xr.DataArray:
    return xr.full_like(land_mask, np.nan, dtype=float)


def select_month_dataarray(
    ds: xr.Dataset,
    variable_name: str,
    month_ts: pd.Timestamp,
    land_mask: xr.DataArray,
) -> xr.DataArray:
    if variable_name not in ds.data_vars:
        return empty_land_layer(land_mask)

    data = ds[variable_name]
    if "valid_time" not in data.dims:
        return data.where(land_mask)

    months = pd.to_datetime(ds["valid_time"].values).to_period("M").to_timestamp()
    target_month = month_ts.to_period("M").to_timestamp()
    matching_indexes = np.where(months == target_month)[0]
    if len(matching_indexes) == 0:
        return empty_land_layer(land_mask)

    return data.isel(valid_time=int(matching_indexes[0])).where(land_mask)


def precipitation_layers(
    ds_prec: xr.Dataset,
    land_mask: xr.DataArray,
    month_ts: pd.Timestamp,
) -> tuple[xr.DataArray, xr.DataArray, str]:
    month_days = days_in_month(month_ts)
    if "avg_tprate" in ds_prec.data_vars:
        daily_mm = select_month_dataarray(ds_prec, "avg_tprate", month_ts, land_mask) * 86400.0
        return daily_mm, daily_mm * month_days, "avg_tprate kg m^-2 s^-1 -> mm/mese"

    if "tp" not in ds_prec.data_vars:
        empty = empty_land_layer(land_mask)
        return empty, empty, "precipitazione non disponibile"

    monthly_mm = select_month_dataarray(ds_prec, "tp", month_ts, land_mask) * 1000.0
    return monthly_mm / month_days, monthly_mm, "tp raw_m * 1000 -> mm/mese"


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


# Risolviamo i file sorgente osservativi direttamente da BioCube.
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
        "ndvi": biocube_dir / "Land" / "Europe_ndvi_monthly_un_025.csv",
        "agriculture": biocube_dir / "Agriculture" / "Europe_combined_agriculture_data.csv",
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
    ds_edaphic: xr.Dataset,
    land_mask: xr.DataArray,
    ndvi_table: pd.DataFrame | None,
    agriculture_table: pd.DataFrame | None,
    species_lookup: dict[str, pd.DataFrame],
    time_index: int,
) -> pd.DataFrame:
    month_ts = pd.to_datetime(ds_temp["valid_time"].values[time_index]).to_period("M").to_timestamp()
    month_key = str(month_ts.date())
    precipitation_daily_mm, precipitation_monthly_mm, _ = precipitation_layers(
        ds_prec=ds_prec,
        land_mask=land_mask,
        month_ts=month_ts,
    )

    month_ds = xr.Dataset(
        {
            "temperature_mean_c": ds_temp["t2m"].isel(valid_time=time_index).where(land_mask) - 273.15,
            "precipitation_mean_daily_mm": precipitation_daily_mm,
            "precipitation_mean_mm": precipitation_monthly_mm,
            "swvl1_mean": select_month_dataarray(ds_edaphic, "swvl1", month_ts, land_mask),
            "swvl2_mean": select_month_dataarray(ds_edaphic, "swvl2", month_ts, land_mask),
        }
    )
    frame = month_ds.to_dataframe().reset_index()
    frame = frame.dropna(
        subset=["temperature_mean_c", "precipitation_mean_mm", "swvl1_mean", "swvl2_mean"],
        how="all",
    )
    frame = frame[
        [
            "latitude",
            "longitude",
            "temperature_mean_c",
            "precipitation_mean_daily_mm",
            "precipitation_mean_mm",
            "swvl1_mean",
            "swvl2_mean",
        ]
    ].copy()
    frame["latitude"] = frame["latitude"].round(2)
    frame["longitude"] = frame["longitude"].round(2)
    frame = merge_layer(
        frame,
        build_monthly_table_layer(ndvi_table, month_ts, "NDVI", "ndvi_mean"),
        "ndvi_mean",
    )
    frame = merge_layer(
        frame,
        build_annual_table_layer(agriculture_table, month_ts, "Cropland", "cropland_mean"),
        "cropland_mean",
    )
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
            "precipitation_mean_daily_mm",
            "precipitation_mean_mm",
            "ndvi_mean",
            "swvl1_mean",
            "swvl2_mean",
            "cropland_mean",
        ]
    ]


# Aggreghiamo il dataset `cella + mese` in una tabella mensile dell'area selezionata.
def compute_area_climate_monthly(cell_df: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, float | int | str]] = []

    for month, frame in cell_df.groupby("month", sort=True):
        records.append(
            {
                "month": str(pd.Timestamp(month).date()),
                "temperature_mean_area_c": weighted_mean(frame, "temperature_mean_c"),
                "precipitation_mean_area_mm": weighted_mean(frame, "precipitation_mean_mm"),
                "precipitation_mean_daily_area_mm": weighted_mean(frame, "precipitation_mean_daily_mm"),
                "precipitation_unit": "mm/mese",
                "ndvi_mean_area": weighted_mean(frame, "ndvi_mean"),
                "swvl1_mean_area": weighted_mean(frame, "swvl1_mean"),
                "swvl2_mean_area": weighted_mean(frame, "swvl2_mean"),
                "cropland_mean_area": weighted_mean(frame, "cropland_mean"),
                "valid_cell_count": int(
                    frame[
                        [
                            "temperature_mean_c",
                            "precipitation_mean_mm",
                            "ndvi_mean",
                            "swvl1_mean",
                            "swvl2_mean",
                            "cropland_mean",
                        ]
                    ].notna().any(axis=1).sum()
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
) -> tuple[xr.Dataset, xr.Dataset, xr.Dataset, xr.DataArray]:
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

    ds_edaphic = subset_bbox(
        filter_dataset_month_range(
            subset_europe(xr.open_dataset(source_paths["edaphic"])),
            start=start,
            end=end,
            max_steps=max_steps,
        ),
        bounds=bounds,
    )

    if ds_temp.sizes.get("latitude", 0) == 0 or ds_temp.sizes.get("longitude", 0) == 0:
        raise SystemExit(
            "Il bounding box selezionato non interseca celle climatiche valide in Europa. "
            "Controlla che le coordinate siano nel dominio lat 30..75 e lon -25..45. "
            f"Bounds ricevuti: lat {bounds['min_lat']}..{bounds['max_lat']}, "
            f"lon {bounds['min_lon']}..{bounds['max_lon']}."
        )

    land_mask = build_land_mask(ds_temp)
    return ds_temp, ds_prec, ds_edaphic, land_mask


# Eseguiamo l'intera pipeline: selezione area, costruzione celle, aggregazione e salvataggio output.
def main() -> None:
    args = build_parser().parse_args()
    if args.list_cities:
        print_available_cities()
        return

    load_dotenv(PROJECT_ROOT / ".env")
    load_dotenv(PROJECT_ROOT / ".env.local", override=True)

    biocube_dir = require_path("BIOCUBE_DIR")
    output_dir = resolve_output_dir("PROJECT_OUTPUT_DIR")
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

    ndvi_table = (
        read_spatial_table(source_paths["ndvi"])
        if optional_path(source_paths["ndvi"]) is not None
        else None
    )
    agriculture_table = (
        read_spatial_table(source_paths["agriculture"])
        if optional_path(source_paths["agriculture"]) is not None
        else None
    )

    ds_temp, ds_prec, ds_edaphic, land_mask = load_climate_datasets(
        source_paths=source_paths,
        bounds=bounds,
        start=args.start,
        end=args.end,
        max_steps=args.max_steps,
    )
    precipitation_conversion = (
        "avg_tprate kg m^-2 s^-1 -> mm/mese"
        if "avg_tprate" in ds_prec.data_vars
        else "tp raw_m * 1000 -> mm/mese"
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
                    ndvi_table=ndvi_table,
                    agriculture_table=agriculture_table,
                    species_lookup=species_lookup,
                    time_index=idx,
                )
            )
    finally:
        ds_temp.close()
        ds_prec.close()
        ds_edaphic.close()

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
        "precipitation_conversion": precipitation_conversion,
        "observational_schema": (
            "monthly contiene solo valori osservativi reali: temperatura, precipitazione, NDVI, SWVL1, SWVL2, Cropland e celle valide"
        ),
        "temperature_source": str(source_paths["temperature"]),
        "precipitation_source": str(source_paths["precipitation"]),
        "edaphic_source": str(source_paths["edaphic"]),
        "ndvi_source": str(source_paths["ndvi"]) if optional_path(source_paths["ndvi"]) else None,
        "agriculture_source": str(source_paths["agriculture"]) if optional_path(source_paths["agriculture"]) else None,
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
