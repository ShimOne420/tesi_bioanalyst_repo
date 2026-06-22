"""Backend FastAPI locale per interrogare gli indicatori minimi.

Questa API e pensata per lo sviluppo locale:

- riceve una selezione città o bounding box
- richiama lo script Python del progetto
- restituisce JSON pronto per la UI Next.js
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import numpy as np
import pandas as pd
import xarray as xr
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "local_preview"
CITY_CATALOG_PATH = PROJECT_ROOT / "data" / "european_cities.json"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from selected_area_indicators import (
    infer_spatial_table_month_range,
    resolve_ndvi_source_path,
    resolve_vegetation_dynamic_source_path,
    vegetation_dynamic_source_score,
)

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)

DEFAULT_FORECAST_TARGET_MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
FORECAST_VARIABLE_SPECS = {
    "temperature": {"workbook_prefix": "t2m", "output_column": "temperature_mean_c"},
    "ndvi": {"workbook_prefix": "NDVI", "output_column": "ndvi_mean"},
    "swvl1": {"workbook_prefix": "swvl1", "output_column": "swvl1_mean"},
    "swvl2": {"workbook_prefix": "swvl2", "output_column": "swvl2_mean"},
    "stl1": {"workbook_prefix": "stl1", "output_column": "stl1_mean"},
    "stl2": {"workbook_prefix": "stl2", "output_column": "stl2_mean"},
    "cropland": {"workbook_prefix": "Cropland", "output_column": "cropland_mean"},
    "arable": {"workbook_prefix": "Arable", "output_column": "arable_mean"},
    "forest": {"workbook_prefix": "Forest", "output_column": "forest_mean"},
}


# Configuriamo l'app FastAPI con CORS locale per la UI Next.js su localhost.
app = FastAPI(title="BioMap Local API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Normalizziamo una label in modo che possa essere usata anche come stem dei file di output.
def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return normalized.strip("_") or "selected_area"


# Convertiamo una stringa numerica in float o `None` per costruire il JSON di risposta.
def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


# Convertiamo una stringa numerica in intero o `None`.
def parse_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    return int(float(value))


def nullable_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def nullable_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(float(value))


# Carichiamo una sola volta il catalogo locale completo delle citta europee usato da backend e UI.
@lru_cache(maxsize=1)
def load_city_catalog() -> list[dict[str, Any]]:
    if not CITY_CATALOG_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "Catalogo citta non trovato. Esegui `python scripts/generate_european_cities_catalog.py` "
                "per rigenerarlo."
            ),
        )

    return json.loads(CITY_CATALOG_PATH.read_text(encoding="utf-8"))


# Costruiamo anche un lookup per recuperare rapidamente coordinate e metadati di una citta selezionata.
@lru_cache(maxsize=1)
def load_city_lookup() -> dict[str, dict[str, Any]]:
    return {city["value"]: city for city in load_city_catalog()}


# Leggiamo il path del dataset dai file `.env` / `.env.local` per usare i file reali di BioCube.
def get_biocube_dir() -> Path:
    raw_value = os.getenv("BIOCUBE_DIR")
    if not raw_value:
        raise HTTPException(status_code=500, detail="BIOCUBE_DIR non configurata in .env o .env.local.")

    path = Path(raw_value).expanduser()
    if not path.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"BIOCUBE_DIR non trovata: {path}. Se hai spostato i dati su SSD F:, aggiorna "
                "BIOCUBE_DIR nel file .env.local della root del repo."
            ),
        )

    return path


# Restituiamo i path delle sorgenti BioCube usate dagli indicatori osservativi.
def get_source_paths() -> dict[str, Path]:
    biocube_dir = get_biocube_dir()
    default_ndvi_path = biocube_dir / "Land" / "Europe_ndvi_monthly_un_025.csv"
    source_paths = {
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
        "ndvi": resolve_ndvi_source_path(biocube_dir, default_ndvi_path) or default_ndvi_path,
        "agriculture": biocube_dir / "Agriculture" / "Europe_combined_agriculture_data.csv",
        "forest": biocube_dir / "Forest" / "Europe_forest_data.csv",
    }
    vegetation_path = resolve_vegetation_dynamic_source_path(biocube_dir)
    if vegetation_path is not None:
        source_paths["vegetation"] = vegetation_path
    return source_paths


def validate_source_paths(source_paths: dict[str, Path]) -> None:
    missing = [f"{name}: {path}" for name, path in source_paths.items() if not path.exists()]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=(
                "BIOCUBE_DIR e raggiungibile, ma mancano alcuni file richiesti dalla pipeline "
                "osservativa. Controlla che BIOCUBE_DIR punti alla cartella biocube sul disco SSD F:. "
                f"File mancanti: {'; '.join(missing)}"
            ),
        )


def get_forecast_cache_dir(*, strict: bool = True) -> Path | None:
    raw_value = os.getenv("FORECAST_CACHE_DIR")
    if not raw_value:
        if strict:
            raise HTTPException(
                status_code=500,
                detail=(
                    "FORECAST_CACHE_DIR non configurata in .env o .env.local. "
                    "Imposta la cartella `previsioni` con i run gia calcolati."
                ),
            )
        return None

    path = Path(raw_value).expanduser()
    if not path.exists():
        if strict:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"FORECAST_CACHE_DIR non trovata: {path}. Controlla il path della cartella "
                    "`previsioni` sul computer universitario."
                ),
            )
        return None

    return path


def normalize_month_label(value: str) -> str:
    return pd.Timestamp(value).to_period("M").strftime("%Y-%m")


def get_forecast_target_months() -> list[str]:
    raw_value = os.getenv("FORECAST_TARGET_MONTHS", "").strip()
    if not raw_value:
        return DEFAULT_FORECAST_TARGET_MONTHS

    tokens = [token.strip() for token in raw_value.replace(";", ",").split(",") if token.strip()]
    if not tokens:
        return DEFAULT_FORECAST_TARGET_MONTHS

    months = sorted({normalize_month_label(token) for token in tokens})
    if not months:
        return DEFAULT_FORECAST_TARGET_MONTHS

    return months


def build_forecast_metadata() -> dict[str, Any]:
    cache_dir = get_forecast_cache_dir(strict=False)
    target_months = get_forecast_target_months()
    available_months: list[str] = []
    if cache_dir is not None:
        available_months = [
            month
            for month in target_months
            if (cache_dir / month / "cell_matrix").exists()
        ]

    return {
        "targetMonths": target_months,
        "availableMonths": available_months,
        "cacheConfigured": cache_dir is not None,
    }


# Calcoliamo una sola volta il periodo realmente disponibile leggendo i file locali del dataset.
@lru_cache(maxsize=1)
def get_dataset_metadata() -> dict[str, Any]:
    source_paths = get_source_paths()
    validate_source_paths(source_paths)

    species_df = pd.read_parquet(source_paths["species"], columns=["Timestamp"])
    species_min = pd.to_datetime(species_df["Timestamp"]).min().to_period("M").to_timestamp()
    species_max = pd.to_datetime(species_df["Timestamp"]).max().to_period("M").to_timestamp()

    ds_temp = xr.open_dataset(source_paths["temperature"])
    try:
        temperature_times = pd.to_datetime(ds_temp["valid_time"].values)
        temp_min = temperature_times.min().to_period("M").to_timestamp()
        temp_max = temperature_times.max().to_period("M").to_timestamp()
    finally:
        ds_temp.close()

    ds_prec = xr.open_dataset(source_paths["precipitation"])
    try:
        precipitation_times = pd.to_datetime(ds_prec["valid_time"].values)
        prec_min = precipitation_times.min().to_period("M").to_timestamp()
        prec_max = precipitation_times.max().to_period("M").to_timestamp()
    finally:
        ds_prec.close()

    ds_edaphic = xr.open_dataset(source_paths["edaphic"])
    try:
        edaphic_times = pd.to_datetime(ds_edaphic["valid_time"].values)
        edaphic_min = edaphic_times.min().to_period("M").to_timestamp()
        edaphic_max = edaphic_times.max().to_period("M").to_timestamp()
    finally:
        ds_edaphic.close()

    try:
        ndvi_range = infer_spatial_table_month_range(source_paths["ndvi"], "NDVI")
    except (OSError, ValueError, KeyError, pd.errors.EmptyDataError, pd.errors.ParserError):
        ndvi_range = None

    vegetation_score = None
    vegetation_path = source_paths.get("vegetation")
    if vegetation_path is not None:
        vegetation_score = vegetation_dynamic_source_score(vegetation_path)

    # Le specie e le tabelle opzionali non devono bloccare il selettore periodo:
    # se non hanno osservazioni in un mese, la UI mostra `n.d.` invece di chiudere il range.
    common_start = max(temp_min, prec_min, edaphic_min)
    common_end = min(temp_max, prec_max, edaphic_max)

    return {
        "period": {
            "minMonth": common_start.strftime("%Y-%m"),
            "maxMonth": common_end.strftime("%Y-%m"),
        },
        "sources": {
            "species": {
                "minMonth": species_min.strftime("%Y-%m"),
                "maxMonth": species_max.strftime("%Y-%m"),
            },
            "temperature": {
                "minMonth": temp_min.strftime("%Y-%m"),
                "maxMonth": temp_max.strftime("%Y-%m"),
            },
            "precipitation": {
                "minMonth": prec_min.strftime("%Y-%m"),
                "maxMonth": prec_max.strftime("%Y-%m"),
            },
            "edaphic": {
                "minMonth": edaphic_min.strftime("%Y-%m"),
                "maxMonth": edaphic_max.strftime("%Y-%m"),
            },
            "ndvi": {
                "path": str(source_paths["ndvi"]),
                "minMonth": ndvi_range[0].strftime("%Y-%m") if ndvi_range else None,
                "maxMonth": ndvi_range[1].strftime("%Y-%m") if ndvi_range else None,
            },
            "vegetation": {
                "path": str(vegetation_path) if vegetation_path else None,
                "maxMonth": vegetation_score[1].strftime("%Y-%m") if vegetation_score else None,
                "sourceKind": "ndvi" if vegetation_score and vegetation_score[0] == 2 else "lai_proxy" if vegetation_score else None,
            },
        },
        "forecast": build_forecast_metadata(),
        "cities": load_city_catalog(),
    }


# Leggiamo il CSV prodotto dallo script Python e lo trasformiamo in lista di record JSON.
def read_monthly_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            rows.append(
                {
                    "month": row["month"],
                    "temperature_mean_area_c": parse_float(row["temperature_mean_area_c"]),
                    "ndvi_mean_area": parse_float(row.get("ndvi_mean_area")),
                    "swvl1_mean_area": parse_float(row.get("swvl1_mean_area")),
                    "swvl2_mean_area": parse_float(row.get("swvl2_mean_area")),
                    "stl1_mean_area": parse_float(row.get("stl1_mean_area")),
                    "stl2_mean_area": parse_float(row.get("stl2_mean_area")),
                    "cropland_mean_area": parse_float(row.get("cropland_mean_area")),
                    "arable_mean_area": parse_float(row.get("arable_mean_area")),
                    "forest_mean_area": parse_float(row.get("forest_mean_area")),
                    "cell_count_land": parse_int(row["cell_count_land"]),
                    "cells_with_species_records": parse_int(row["cells_with_species_records"]),
                    "species_count_observed_area": parse_int(row["species_count_observed_area"]),
                }
            )
        return rows


def read_cells_parquet(path: Path, month: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise HTTPException(status_code=404, detail="Parquet celle non trovato per questo calcolo.")

    target_month = pd.Timestamp(month).to_period("M").to_timestamp()
    df = pd.read_parquet(path)
    df["month"] = pd.to_datetime(df["month"]).dt.to_period("M").dt.to_timestamp()
    df = df[df["month"] == target_month].copy()

    if df.empty:
        raise HTTPException(status_code=404, detail=f"Nessuna cella trovata per il mese {target_month:%Y-%m}.")

    records = []
    for row in df.itertuples(index=False):
        record = row._asdict()
        records.append(
            {
                "month": pd.Timestamp(record["month"]).strftime("%Y-%m-%d"),
                "latitude": nullable_float(record.get("latitude")),
                "longitude": nullable_float(record.get("longitude")),
                "temperature_mean_c": nullable_float(record.get("temperature_mean_c")),
                "ndvi_mean": nullable_float(record.get("ndvi_mean")),
                "swvl1_mean": nullable_float(record.get("swvl1_mean")),
                "swvl2_mean": nullable_float(record.get("swvl2_mean")),
                "stl1_mean": nullable_float(record.get("stl1_mean")),
                "stl2_mean": nullable_float(record.get("stl2_mean")),
                "cropland_mean": nullable_float(record.get("cropland_mean")),
                "arable_mean": nullable_float(record.get("arable_mean")),
                "forest_mean": nullable_float(record.get("forest_mean")),
                "species_count_observed_cell": nullable_int(record.get("species_count_observed_cell")),
            }
        )

    return records


def parse_month_start(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).to_period("M").to_timestamp()


def resolve_selection_bounds(body: dict[str, Any]) -> tuple[dict[str, float], str, str]:
    selection_mode = str(body.get("selectionMode") or "").strip()
    label_value = str(body.get("label") or body.get("city") or "selected_area")
    label_slug = slugify(label_value)

    if selection_mode == "city":
        city = body.get("city")
        if not city:
            raise HTTPException(status_code=400, detail="Campo `city` mancante.")

        city_config = load_city_lookup().get(str(city))
        if city_config is None:
            raise HTTPException(status_code=400, detail="Città non trovata nel catalogo europeo.")

        half_window_deg = float(body.get("halfWindowDeg", 0.5))
        lat = float(city_config["lat"])
        lon = float(city_config["lon"])
        bounds = {
            "min_lat": lat - half_window_deg,
            "max_lat": lat + half_window_deg,
            "min_lon": lon - half_window_deg,
            "max_lon": lon + half_window_deg,
        }
        return bounds, label_slug, selection_mode

    if selection_mode == "bbox":
        bounds = body.get("bounds") or {}
        required = ["minLat", "maxLat", "minLon", "maxLon"]
        missing = [key for key in required if key not in bounds]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Bounding box incompleto, mancano: {', '.join(missing)}",
            )
        normalized = {
            "min_lat": float(bounds["minLat"]),
            "max_lat": float(bounds["maxLat"]),
            "min_lon": float(bounds["minLon"]),
            "max_lon": float(bounds["maxLon"]),
        }
        return normalized, label_slug, selection_mode

    raise HTTPException(status_code=400, detail="selectionMode deve essere `city` o `bbox`.")


def get_forecast_output_paths(label_slug: str) -> dict[str, Path]:
    return {
        "cells_parquet": LOCAL_OUTPUT_DIR / f"forecast_{label_slug}_cells.parquet",
    }


def list_forecast_months_until_target(target_month: str) -> list[pd.Timestamp]:
    target_months = get_forecast_target_months()
    month_ts = parse_month_start(target_month)
    month_label = month_ts.strftime("%Y-%m")
    if month_label not in target_months:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Il forecast supporta solo i mesi configurati: {', '.join(target_months)}. "
                f"Hai richiesto {month_label}."
            ),
        )

    first_month = pd.Timestamp(f"{target_months[0]}-01")
    return list(pd.period_range(start=first_month, end=month_ts, freq="M").to_timestamp())


def forecast_cell_matrix_path(month_ts: pd.Timestamp, workbook_prefix: str) -> Path:
    cache_dir = get_forecast_cache_dir(strict=True)
    assert cache_dir is not None
    return cache_dir / month_ts.strftime("%Y-%m") / "cell_matrix" / f"{workbook_prefix}_cell_matrix.xlsx"


@lru_cache(maxsize=256)
def read_forecast_full_grid(path_str: str) -> pd.DataFrame:
    return pd.read_excel(Path(path_str), sheet_name="full_grid")


def find_required_column(frame: pd.DataFrame, candidates: list[str], *, context: str) -> str:
    normalized = {str(column).strip().casefold(): str(column) for column in frame.columns}
    for candidate in candidates:
        column = normalized.get(candidate.casefold())
        if column:
            return column
    raise HTTPException(
        status_code=500,
        detail=f"Colonna richiesta non trovata in {context}. Attese: {', '.join(candidates)}",
    )


def locate_predicted_column(frame: pd.DataFrame, workbook_path: Path) -> str:
    predicted_columns = [str(column) for column in frame.columns if str(column).startswith("predicted_")]
    if not predicted_columns:
        raise HTTPException(
            status_code=500,
            detail=f"Colonna `predicted_*` non trovata nel workbook forecast {workbook_path.name}.",
        )
    return predicted_columns[0]


def normalize_forecast_temperature_like(values: pd.Series, predicted_column: str) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    sample = numeric.dropna()
    should_convert = predicted_column.endswith("_native")
    if not should_convert and not sample.empty:
        should_convert = float(sample.abs().median()) > 150.0
    return numeric - 273.15 if should_convert else numeric


def load_forecast_variable_layer(month_ts: pd.Timestamp, variable_key: str) -> pd.DataFrame:
    spec = FORECAST_VARIABLE_SPECS[variable_key]
    workbook_path = forecast_cell_matrix_path(month_ts, str(spec["workbook_prefix"]))
    if not workbook_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Workbook forecast non trovato per {month_ts:%Y-%m}: {workbook_path}. "
                "Genera o copia il run precomputato nella cartella `previsioni`."
            ),
        )

    try:
        frame = read_forecast_full_grid(str(workbook_path)).copy()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Non sono riuscito a leggere il workbook forecast {workbook_path.name}: {exc}",
        ) from exc

    latitude_column = find_required_column(frame, ["lat", "latitude"], context=workbook_path.name)
    longitude_column = find_required_column(frame, ["lon", "longitude"], context=workbook_path.name)
    predicted_column = locate_predicted_column(frame, workbook_path)

    layer = frame[[latitude_column, longitude_column, predicted_column]].copy()
    layer.columns = ["latitude", "longitude", str(spec["output_column"])]
    layer["latitude"] = pd.to_numeric(layer["latitude"], errors="coerce")
    layer["longitude"] = pd.to_numeric(layer["longitude"], errors="coerce")

    if variable_key in {"temperature", "stl1", "stl2"}:
        layer[str(spec["output_column"])] = normalize_forecast_temperature_like(
            layer[str(spec["output_column"])],
            predicted_column,
        )
    else:
        layer[str(spec["output_column"])] = pd.to_numeric(
            layer[str(spec["output_column"])],
            errors="coerce",
        )

    return layer[["latitude", "longitude", str(spec["output_column"])]]


def select_bounds(frame: pd.DataFrame, bounds: dict[str, float]) -> pd.DataFrame:
    return frame[
        (frame["latitude"] >= bounds["min_lat"])
        & (frame["latitude"] <= bounds["max_lat"])
        & (frame["longitude"] >= bounds["min_lon"])
        & (frame["longitude"] <= bounds["max_lon"])
    ].copy()


def build_forecast_month_cell_frame(month_ts: pd.Timestamp, bounds: dict[str, float]) -> pd.DataFrame:
    merged: pd.DataFrame | None = None
    for variable_key in FORECAST_VARIABLE_SPECS:
        layer = load_forecast_variable_layer(month_ts, variable_key)
        merged = layer if merged is None else merged.merge(layer, on=["latitude", "longitude"], how="outer")

    assert merged is not None
    merged["latitude"] = merged["latitude"].round(2)
    merged["longitude"] = merged["longitude"].round(2)
    merged = select_bounds(merged, bounds)
    if merged.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                "Il bounding box selezionato non interseca celle forecast valide nel cache "
                f"per il mese {month_ts:%Y-%m}."
            ),
        )

    merged["month"] = month_ts
    merged["cell_id"] = merged["latitude"].map(lambda value: f"{value:.2f}") + "_" + merged["longitude"].map(
        lambda value: f"{value:.2f}"
    )
    merged["latitude_weight"] = merged["latitude"].map(lambda value: float(np.cos(np.radians(value))))
    merged["species_count_observed_cell"] = pd.Series([pd.NA] * len(merged), dtype="Int64")
    return merged[
        [
            "month",
            "latitude",
            "longitude",
            "cell_id",
            "latitude_weight",
            "species_count_observed_cell",
            "temperature_mean_c",
            "ndvi_mean",
            "swvl1_mean",
            "swvl2_mean",
            "stl1_mean",
            "stl2_mean",
            "cropland_mean",
            "arable_mean",
            "forest_mean",
        ]
    ]


def weighted_mean(frame: pd.DataFrame, column: str) -> float | None:
    values = pd.to_numeric(frame[column], errors="coerce")
    weights = pd.to_numeric(frame["latitude_weight"], errors="coerce")
    valid_mask = values.notna() & weights.notna()
    if not valid_mask.any():
        return None

    valid_values = values[valid_mask].to_numpy(dtype=np.float64)
    valid_weights = weights[valid_mask].to_numpy(dtype=np.float64)
    weight_sum = float(valid_weights.sum())
    if weight_sum == 0.0:
        return None

    return float(np.average(valid_values, weights=valid_weights))


def compute_forecast_monthly(cell_df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for month, frame in cell_df.groupby("month", sort=True):
        records.append(
            {
                "month": str(pd.Timestamp(month).date()),
                "temperature_mean_area_c": weighted_mean(frame, "temperature_mean_c"),
                "ndvi_mean_area": weighted_mean(frame, "ndvi_mean"),
                "swvl1_mean_area": weighted_mean(frame, "swvl1_mean"),
                "swvl2_mean_area": weighted_mean(frame, "swvl2_mean"),
                "stl1_mean_area": weighted_mean(frame, "stl1_mean"),
                "stl2_mean_area": weighted_mean(frame, "stl2_mean"),
                "cropland_mean_area": weighted_mean(frame, "cropland_mean"),
                "arable_mean_area": weighted_mean(frame, "arable_mean"),
                "forest_mean_area": weighted_mean(frame, "forest_mean"),
                "cell_count_land": int(len(frame)),
                "cells_with_species_records": 0,
                "species_count_observed_area": None,
            }
        )
    return records


def resolve_python_executable() -> str:
    candidates = [
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv-bioanalyst" / "Scripts" / "python.exe",
        PROJECT_ROOT / ".venv" / "bin" / "python",
        PROJECT_ROOT / ".venv-bioanalyst" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return sys.executable


# Deriviamo i file di output generati per una certa label in modo coerente tra API e UI.
def get_output_paths(label_slug: str) -> dict[str, Path]:
    stem = f"selected_{label_slug}_area_monthly"
    return {
        "summary": LOCAL_OUTPUT_DIR / f"{stem}_summary.json",
        "csv": LOCAL_OUTPUT_DIR / f"{stem}.csv",
        "excel_csv": LOCAL_OUTPUT_DIR / f"{stem}_excel.csv",
        "xlsx": LOCAL_OUTPUT_DIR / f"{stem}.xlsx",
        "cells_parquet": LOCAL_OUTPUT_DIR / f"selected_{label_slug}_cells.parquet",
    }


# Costruiamo il comando CLI del motore indicatori a partire dal payload ricevuto dall'API.
def build_indicator_command(body: dict[str, Any]) -> tuple[list[str], str]:
    selection_mode = body.get("selectionMode")
    label_value = body.get("label") or body.get("city") or "selected_area"
    label_slug = slugify(label_value)

    cmd = [
        resolve_python_executable(),
        str(PROJECT_ROOT / "scripts" / "selected_area_indicators.py"),
        "--start",
        str(body.get("start")),
        "--end",
        str(body.get("end")),
        "--label",
        label_slug,
        "--output-mode",
        str(body.get("outputMode", "both")),
    ]

    max_steps = body.get("maxSteps")
    if max_steps is not None:
        cmd.extend(["--max-steps", str(max_steps)])

    if selection_mode == "city":
        city = body.get("city")
        if not city:
            raise HTTPException(status_code=400, detail="Campo `city` mancante.")

        city_config = load_city_lookup().get(str(city))
        if city_config is None:
            raise HTTPException(status_code=400, detail="Città non trovata nel catalogo europeo.")

        cmd.extend(["--lat", str(city_config["lat"])])
        cmd.extend(["--lon", str(city_config["lon"])])
        cmd.extend(["--half-window-deg", str(body.get("halfWindowDeg", 0.5))])
    elif selection_mode == "bbox":
        bounds = body.get("bounds") or {}
        required = ["minLat", "maxLat", "minLon", "maxLon"]
        missing = [key for key in required if key not in bounds]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Bounding box incompleto, mancano: {', '.join(missing)}",
            )
        cmd.extend(["--min-lat", str(bounds["minLat"])])
        cmd.extend(["--max-lat", str(bounds["maxLat"])])
        cmd.extend(["--min-lon", str(bounds["minLon"])])
        cmd.extend(["--max-lon", str(bounds["maxLon"])])
    else:
        raise HTTPException(status_code=400, detail="selectionMode deve essere `city` o `bbox`.")

    return cmd, label_slug


# Eseguiamo lo script Python locale e leggiamo gli output prodotti nella cartella `local_preview`.
def run_indicator_job(body: dict[str, Any]) -> dict[str, Any]:
    validate_source_paths(get_source_paths())
    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd, label_slug = build_indicator_command(body)

    completed = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env={
            **os.environ,
            "PROJECT_OUTPUT_DIR": str(LOCAL_OUTPUT_DIR),
        },
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=completed.stderr.strip() or completed.stdout.strip() or "Errore nello script Python.",
        )

    output_paths = get_output_paths(label_slug)
    summary_path = output_paths["summary"]
    csv_path = output_paths["csv"]

    if not summary_path.exists() or not csv_path.exists():
        raise HTTPException(status_code=500, detail="Output non trovati dopo l'esecuzione dello script.")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    monthly = read_monthly_csv(csv_path)
    notes = [
        note
        for note in [
            summary.get("species_note"),
            summary.get("observational_schema"),
        ]
        if note
    ]

    return {
        "status": "ok",
        "dashboardMode": "observed",
        "sourceMode": "local",
        "label": summary["label"],
        "selectionMode": body.get("selectionMode", summary["selection_mode"]),
        "bounds": {
            "minLat": summary["bounds"]["min_lat"],
            "maxLat": summary["bounds"]["max_lat"],
            "minLon": summary["bounds"]["min_lon"],
            "maxLon": summary["bounds"]["max_lon"],
        },
        "start": summary["start"],
        "end": summary["end"],
        "monthly": monthly,
        "cellsUrl": f"/api/cells/{label_slug}",
        "notes": notes,
        "downloads": {
            "csvUrl": f"/api/download/{label_slug}/csv",
            "excelCsvUrl": f"/api/download/{label_slug}/excel_csv",
            "xlsxUrl": f"/api/download/{label_slug}/xlsx",
        },
    }


def run_forecast_cache_job(body: dict[str, Any]) -> dict[str, Any]:
    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bounds, label_slug, selection_mode = resolve_selection_bounds(body)
    target_month = str(body.get("targetMonth") or "").strip()
    if not target_month:
        raise HTTPException(status_code=400, detail="Il campo `targetMonth` e obbligatorio per il forecast.")

    months = list_forecast_months_until_target(target_month)
    month_frames = [build_forecast_month_cell_frame(month_ts, bounds) for month_ts in months]
    cell_df = pd.concat(month_frames, ignore_index=True)
    output_paths = get_forecast_output_paths(label_slug)
    cell_df.to_parquet(output_paths["cells_parquet"], index=False)

    notes = [
        "Forecast caricato da cache precomputata: il frontend non esegue run live del modello.",
    ]
    if len(months) == 1:
        notes.append(f"Modalita one-step: mese previsto {months[0]:%Y-%m}.")
    else:
        notes.append(f"Rollout multi-step caricato da {months[0]:%Y-%m} a {months[-1]:%Y-%m}.")

    return {
        "status": "ok",
        "dashboardMode": "forecast",
        "sourceMode": "forecast_cache",
        "label": label_slug,
        "selectionMode": selection_mode,
        "bounds": {
            "minLat": bounds["min_lat"],
            "maxLat": bounds["max_lat"],
            "minLon": bounds["min_lon"],
            "maxLon": bounds["max_lon"],
        },
        "start": str(months[0].date()),
        "end": str(months[-1].date()),
        "targetMonth": str(months[-1].date()),
        "forecastMonths": [str(month.date()) for month in months],
        "monthly": compute_forecast_monthly(cell_df),
        "cellsUrl": f"/api/forecast/cells/{label_slug}",
        "notes": notes,
    }


# Esporiamo un controllo base per sapere se il backend locale è attivo.
@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "biomap-local-api"}


# Esporiamo l'elenco città per una futura UI completamente data-driven.
@app.get("/api/cities")
def list_cities() -> dict[str, list[dict[str, Any]]]:
    return {"cities": load_city_catalog()}


# Esporiamo il periodo realmente disponibile del dataset per popolare i selettori della UI.
@app.get("/api/metadata")
def metadata() -> dict[str, Any]:
    return get_dataset_metadata()


# Riceviamo una selezione città o area e restituiamo gli indicatori minimi in JSON.
@app.post("/api/indicators")
def indicators(body: dict[str, Any]) -> dict[str, Any]:
    if not body.get("start") or not body.get("end"):
        raise HTTPException(status_code=400, detail="I campi `start` e `end` sono obbligatori.")

    return run_indicator_job(body)


@app.post("/api/forecast")
def forecast(body: dict[str, Any]) -> dict[str, Any]:
    return run_forecast_cache_job(body)


@app.get("/api/cells/{label}")
def cells(label: str, month: str) -> dict[str, Any]:
    label_slug = slugify(label)
    output_paths = get_output_paths(label_slug)
    return {
        "label": label_slug,
        "month": pd.Timestamp(month).to_period("M").to_timestamp().strftime("%Y-%m-%d"),
        "cells": read_cells_parquet(output_paths["cells_parquet"], month),
    }


@app.get("/api/forecast/cells/{label}")
def forecast_cells(label: str, month: str) -> dict[str, Any]:
    label_slug = slugify(label)
    output_paths = get_forecast_output_paths(label_slug)
    return {
        "label": label_slug,
        "month": pd.Timestamp(month).to_period("M").to_timestamp().strftime("%Y-%m-%d"),
        "cells": read_cells_parquet(output_paths["cells_parquet"], month),
    }


# Permettiamo alla UI di scaricare i file prodotti dall'ultimo calcolo per una label specifica.
@app.get("/api/download/{label}/{file_format}")
def download_result(label: str, file_format: str) -> FileResponse:
    label_slug = slugify(label)
    output_paths = get_output_paths(label_slug)

    if file_format not in {"csv", "excel_csv", "xlsx"}:
        raise HTTPException(status_code=400, detail="Formato non supportato.")

    target = output_paths[file_format]
    if not target.exists():
        raise HTTPException(status_code=404, detail="File di output non trovato.")

    media_type = "text/csv" if file_format in {"csv", "excel_csv"} else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return FileResponse(target, media_type=media_type, filename=target.name)
