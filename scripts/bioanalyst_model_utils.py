"""Funzioni di supporto per il forecasting locale con BioAnalyst.

Questo modulo non va eseguito da solo. Serve per:

- risolvere path e checkpoint del modello;
- costruire batch `.pt` compatibili con `bfm-model`;
- riusare la selezione `citta / punto / bounding box`;
- aggregare le predizioni del modello su un'area BIOMAP leggibile.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import xarray as xr
from dotenv import load_dotenv
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from omegaconf import OmegaConf

from minimum_indicator_utils import (
    build_bbox_from_point,
    normalize_longitude,
    resolve_output_base_dir,
    snap_coordinates_to_grid,
)


def first_existing_path(*candidates: Path) -> Path:
    """Restituisce il primo path esistente, altrimenti il primo candidato."""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


# Risolviamo una volta sola la root del progetto e il repo ufficiale clonato localmente.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHARED_MAIN_ROOT = PROJECT_ROOT.parent / "tesi_bioanalyst_repo"
BFM_REPO_ROOT = first_existing_path(
    PROJECT_ROOT / "external" / "bfm-model",
    SHARED_MAIN_ROOT / "external" / "bfm-model",
)
MODEL_CONFIG_DIR = BFM_REPO_ROOT / "bfm_model" / "bfm" / "configs"
MODEL_BATCH_STATS_PATH = BFM_REPO_ROOT / "batch_statistics" / "monthly_batches_stats_splitted_channels.json"
MODEL_LAND_MASK_PATH = BFM_REPO_ROOT / "batch_statistics" / "europe_Land_2020_grid.pkl"
CITY_CATALOG_PATH = PROJECT_ROOT / "data" / "european_cities.json"


# Definiamo il dominio usato per i batch del modello, allineato alla mask ufficiale 160x280.
MODEL_BOUNDS = {
    "min_lat": 32.0,
    "max_lat": 72.0,
    "min_lon": -25.0,
    "max_lon": 45.0,
}
MODEL_HEIGHT = 160
MODEL_WIDTH = 280


# Manteniamo allineati gli elenchi ufficiali delle variabili del modello.
MODEL_ATMOS_LEVELS = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50]
MODEL_SURFACE_VARS = ["t2m", "msl", "slt", "z", "u10", "v10", "lsm"]
MODEL_EDAPHIC_VARS = ["swvl1", "swvl2", "stl1", "stl2"]
MODEL_ATMOS_VARS = ["z", "t", "u", "v", "q"]
MODEL_CLIMATE_VARS = [
    "smlt",
    "tp",
    "csfr",
    "avg_sdswrf",
    "avg_snswrf",
    "avg_snlwrf",
    "avg_tprate",
    "avg_sdswrfcs",
    "sd",
    "t2m",
    "d2m",
]
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
MODEL_VEGETATION_VARS = ["NDVI"]
MODEL_LAND_VARS = ["Land"]
MODEL_AGRICULTURE_VARS = ["Agriculture", "Arable", "Cropland"]
MODEL_FOREST_VARS = ["Forest"]
MODEL_REDLIST_VARS = ["RLI"]
MODEL_MISC_VARS = ["avg_slhtf", "avg_pevr"]


# Definiamo i file sorgente realmente presenti nella release locale di BioCube.
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

# Questi file migliorano la completezza del batch, ma `--input-mode clean`
# deve poter girare anche senza portarli dentro al test.
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


def normalize_input_mode(input_mode: str) -> str:
    value = (input_mode or "all").strip().lower()
    if value not in {"clean", "all"}:
        raise ValueError(f"input_mode non valido: {input_mode}. Usa 'clean' oppure 'all'.")
    return value


def require_source_path(source_paths: dict[str, Path], key: str) -> Path:
    if key in source_paths:
        return source_paths[key]
    relative_path = MODEL_SOURCE_FILES[key][0]
    raise FileNotFoundError(
        f"Sorgente opzionale richiesta da input-mode all ma non trovata: {key} ({relative_path})"
    )


# Verifichiamo un path di ambiente e lo trasformiamo in Path.
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


# Normalizziamo stringhe in slug stabili per cartelle e output.
def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return normalized.strip("_") or "forecast"


# Uniformiamo tutte le date al primo giorno del mese.
def to_month_start(value: str | pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(value).to_period("M").to_timestamp()


# Formattiamo i timestamp nel formato atteso dai batch del modello.
def month_to_timestamp_str(value: pd.Timestamp) -> str:
    month = to_month_start(value)
    return month.strftime("%Y-%m-%d 00:00:00")


# Prepariamo un mese precedente e uno successivo rispetto a un anchor.
def shift_month(value: pd.Timestamp, months: int) -> pd.Timestamp:
    return to_month_start(value) + pd.DateOffset(months=months)


# Rendiamo importabile `bfm_model` anche se il repo è solo clonato localmente.
def ensure_bfm_repo_on_path() -> None:
    repo_path = str(BFM_REPO_ROOT)
    if repo_path not in sys.path:
        sys.path.insert(0, repo_path)


# Convertiamo un raw dict `.pt` nel NamedTuple `Batch` usato dal repo ufficiale.
def raw_dict_to_batch(raw_batch: dict):
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.dataloader_monthly import Batch, Metadata, normalize_keys

    metadata = raw_batch["batch_metadata"]
    batch_metadata = Metadata(
        latitudes=torch.tensor(metadata["latitudes"], dtype=torch.float32),
        longitudes=torch.tensor(metadata["longitudes"], dtype=torch.float32),
        timestamp=metadata["timestamp"],
        lead_time=(pd.Timestamp(metadata["timestamp"][1]).year - pd.Timestamp(metadata["timestamp"][0]).year) * 12
        + (pd.Timestamp(metadata["timestamp"][1]).month - pd.Timestamp(metadata["timestamp"][0]).month)
        + 1,
        pressure_levels=metadata["pressure_levels"],
        species_list=metadata["species_list"],
    )

    return Batch(
        batch_metadata=batch_metadata,
        surface_variables=raw_batch["surface_variables"],
        edaphic_variables=raw_batch["edaphic_variables"],
        atmospheric_variables=raw_batch["atmospheric_variables"],
        climate_variables=raw_batch["climate_variables"],
        species_variables=normalize_keys(raw_batch["species_variables"]),
        vegetation_variables=raw_batch["vegetation_variables"],
        land_variables=raw_batch["land_variables"],
        agriculture_variables=raw_batch["agriculture_variables"],
        forest_variables=raw_batch["forest_variables"],
        redlist_variables=raw_batch["redlist_variables"],
        misc_variables=raw_batch["misc_variables"],
    )


# Leggiamo il catalogo città completo e lo indicizziamo per nome in minuscolo.
def load_city_catalog() -> list[dict]:
    with CITY_CATALOG_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


# Normalizziamo un nome città per confronti robusti tra UI, CLI e catalogo.
def normalize_city_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.strip().lower())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


# Risolviamo una città nel catalogo scegliendo la prima occorrenza ordinata per popolazione.
def resolve_city_bounds(city_name: str, half_window_deg: float) -> tuple[dict[str, float], str]:
    # Supportiamo sia i label del catalogo sia alcune forme CLI comuni in italiano.
    alias_map = {
        "milano": "milan",
        "roma": "rome",
        "napoli": "naples",
        "torino": "turin",
        "firenze": "florence",
        "venezia": "venice",
    }

    city_key = normalize_city_name(city_name)
    city_key = alias_map.get(city_key, city_key)

    # Confrontiamo il valore richiesto con piu campi del catalogo per tollerare UI e CLI.
    matches = []
    for item in load_city_catalog():
        label_key = normalize_city_name(item.get("label", ""))
        value_key = normalize_city_name(item.get("value", "").split("_")[0])
        country_key = normalize_city_name(item.get("country", ""))
        composite_key = normalize_city_name(f"{item.get('label', '')} {item.get('country', '')}")
        if city_key in {label_key, value_key, composite_key, f"{label_key} {country_key}".strip()}:
            matches.append(item)

    if not matches:
        raise SystemExit(f"Città non trovata nel catalogo europeo: {city_name}")

    # Usiamo la prima occorrenza gia ordinata per popolazione nel catalogo.
    city = matches[0]
    bounds = build_bbox_from_point(lat=city["lat"], lon=city["lon"], half_window_deg=half_window_deg)
    return bounds, city["label"]


# Creiamo un parser area/periodo coerente con la logica già usata dal backend indicatori.
def build_selection_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--start", required=True, help="Mese iniziale del periodo osservato, es. 2019-01-01")
    parser.add_argument("--end", required=True, help="Mese finale del periodo osservato, es. 2019-12-01")
    parser.add_argument("--label", default=None, help="Etichetta manuale dell'analisi.")
    parser.add_argument("--city", help="Città europea del catalogo locale.")
    parser.add_argument("--lat", type=float, help="Latitudine del punto di interesse.")
    parser.add_argument("--lon", type=float, help="Longitudine del punto di interesse.")
    parser.add_argument("--half-window-deg", type=float, default=0.5, help="Semiampiezza della finestra per città o punto.")
    parser.add_argument("--min-lat", type=float, help="Limite sud del bounding box.")
    parser.add_argument("--max-lat", type=float, help="Limite nord del bounding box.")
    parser.add_argument("--min-lon", type=float, help="Limite ovest del bounding box.")
    parser.add_argument("--max-lon", type=float, help="Limite est del bounding box.")
    return parser


# Risolviamo la selezione area in un bounding box unico, indipendente dall'interfaccia futura.
def resolve_selection(args: argparse.Namespace) -> tuple[str, dict[str, float], str]:
    has_city = args.city is not None
    has_point = args.lat is not None and args.lon is not None
    has_bbox = None not in (args.min_lat, args.max_lat, args.min_lon, args.max_lon)
    if sum([has_city, has_point, has_bbox]) != 1:
        raise SystemExit("Specifica una sola selezione: città, punto oppure bounding box completo.")

    if has_city:
        bounds, resolved_name = resolve_city_bounds(args.city, args.half_window_deg)
        return "city", bounds, args.label or resolved_name

    if has_point:
        bounds = build_bbox_from_point(args.lat, args.lon, args.half_window_deg)
        return "point", bounds, args.label or f"point_{args.lat}_{args.lon}"

    bounds = {
        "min_lat": args.min_lat,
        "max_lat": args.max_lat,
        "min_lon": args.min_lon,
        "max_lon": args.max_lon,
    }
    return "bbox", bounds, args.label or "selected_bbox"


# Verifichiamo che il periodo scelto abbia almeno due mesi e rientri nella parte climatica disponibile.
def resolve_forecast_months(start: str, end: str) -> dict[str, pd.Timestamp | bool]:
    start_month = to_month_start(start)
    end_month = to_month_start(end)
    if end_month < start_month:
        raise SystemExit("Il mese finale deve essere successivo o uguale al mese iniziale.")

    observed_months = pd.period_range(start=start_month, end=end_month, freq="M").to_timestamp()
    if len(observed_months) < 2:
        raise SystemExit("Per il forecast servono almeno due mesi osservati nel periodo selezionato.")

    input_prev = observed_months[-2]
    input_last = observed_months[-1]
    forecast_month = shift_month(input_last, 1)
    return {
        "start_month": start_month,
        "end_month": end_month,
        "input_prev": input_prev,
        "input_last": input_last,
        "forecast_month": forecast_month,
        "compare_available": True,
    }


# Risolviamo i path dei file sorgente raw realmente usati nella costruzione dei batch.
def resolve_source_paths(biocube_dir: Path) -> dict[str, Path]:
    resolved = {}
    for key, (relative_path, _) in MODEL_SOURCE_FILES.items():
        path = biocube_dir / relative_path
        if not path.exists():
            if key in OPTIONAL_MODEL_SOURCE_KEYS:
                continue
            raise FileNotFoundError(f"Sorgente mancante per {key}: {path}")
        resolved[key] = path
    return resolved


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
        (name for name in ("Timestamp", "timestamp", "Date", "date", "Month", "month", "valid_time") if name in ndvi_frame.columns),
        None,
    )
    year_column = next((name for name in ("Year", "year", "YEAR", "Anno", "anno") if name in ndvi_frame.columns), None)
    month_column = next((name for name in ("Month", "month", "MONTH", "Mese", "mese") if name in ndvi_frame.columns), None)

    month_set: set[pd.Timestamp] = set()
    if year_column and month_column:
        years = pd.to_numeric(ndvi_frame[year_column], errors="coerce")
        month_numbers = ndvi_frame[month_column].map(month_number_from_value)
        for year_value, month_value in zip(years, month_numbers, strict=False):
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


def format_future_availability_error(report: dict[str, Any]) -> str:
    joined = "\n".join(f"- {item}" for item in report["missing_input_sources"])
    return (
        "Il forecast richiesto non puo essere costruito con i dati locali disponibili per i due mesi input.\n"
        f"Mesi input richiesti: {', '.join(report['input_months'])}\n"
        "Sorgenti mancanti o non estese:\n"
        f"{joined}"
    )


# Ritagliamo l'Europa senza `sortby` globale quando la longitudine e in formato 0..360.
def crop_model_domain(ds: xr.Dataset) -> xr.Dataset:
    lon_min = float(ds["longitude"].values[0])
    lon_max = float(ds["longitude"].values[-1])

    # Caso ERA5 classico 0..360: prendiamo due slice e le concateniamo gia in ordine finale.
    if lon_min >= 0.0 and lon_max > 180.0:
        west = ds.sel(
            latitude=slice(MODEL_BOUNDS["max_lat"], MODEL_BOUNDS["min_lat"]),
            longitude=slice(360.0 + MODEL_BOUNDS["min_lon"], 360.0),
        )
        east = ds.sel(
            latitude=slice(MODEL_BOUNDS["max_lat"], MODEL_BOUNDS["min_lat"]),
            longitude=slice(0.0, MODEL_BOUNDS["max_lon"]),
        )
        europe = xr.concat([west, east], dim="longitude")
        europe = europe.assign_coords(longitude=(((europe["longitude"] + 180) % 360) - 180).astype("float32"))
    else:
        europe = normalize_longitude(ds).sel(
            latitude=slice(MODEL_BOUNDS["max_lat"], MODEL_BOUNDS["min_lat"]),
            longitude=slice(MODEL_BOUNDS["min_lon"], MODEL_BOUNDS["max_lon"]),
        )

    return europe.isel(latitude=slice(0, MODEL_HEIGHT), longitude=slice(0, MODEL_WIDTH))


# Apriamo un dataset ERA5, lo ritagliamo sul dominio del modello e carichiamo solo i mesi richiesti.
def open_model_domain_dataset(path: Path, months: list[pd.Timestamp] | None = None) -> xr.Dataset:
    with xr.open_dataset(path, engine="netcdf4") as ds:
        cropped = crop_model_domain(ds)
        if months is not None and "valid_time" in cropped.coords:
            positions = resolve_time_positions(cropped, months)
            cropped = cropped.isel(valid_time=positions)
        cropped = cropped.load()
    return cropped


# Ricaviamo le coordinate finali del dominio 160x280 usato dal modello senza caricare tutte le variabili.
def load_model_grid(source_paths: dict[str, Path]) -> tuple[np.ndarray, np.ndarray]:
    with xr.open_dataset(source_paths["surface"], engine="netcdf4") as ds:
        cropped = crop_model_domain(ds)
        latitudes = cropped["latitude"].values.astype(np.float32)
        longitudes = cropped["longitude"].values.astype(np.float32)
    return latitudes, longitudes


# Convertiamo una lista di mesi in posizioni `valid_time` del dataset.
def resolve_time_positions(ds: xr.Dataset, months: list[pd.Timestamp]) -> list[int]:
    available = pd.to_datetime(ds["valid_time"].values).to_period("M").to_timestamp()
    positions = []
    for month in months:
        matches = np.where(available == month)[0]
        if len(matches) == 0:
            raise KeyError(f"Mese non trovato nel dataset: {month.date()}")
        positions.append(int(matches[0]))
    return positions


# Rimuoviamo eventuali dimensioni ausiliarie e portiamo un campo 2D/3D in tensore float32.
def squeeze_common_dims(data_array: xr.DataArray) -> xr.DataArray:
    dims_to_drop = [dim for dim in ("number", "expver") if dim in data_array.dims]
    for dim in dims_to_drop:
        data_array = data_array.isel({dim: 0}, drop=True)
    return data_array


# Estraiamo una variabile 2D mensile nel formato [T, H, W].
def extract_month_tensor(ds: xr.Dataset, var_name: str, months: list[pd.Timestamp]) -> torch.Tensor:
    positions = resolve_time_positions(ds, months)
    array = squeeze_common_dims(ds[var_name].isel(valid_time=positions))
    array = array.transpose("valid_time", "latitude", "longitude")
    return torch.from_numpy(array.values.astype(np.float32))


# Estraiamo una variabile atmosferica 3D nel formato [T, L, H, W].
def extract_atmospheric_tensor(ds: xr.Dataset, var_name: str, months: list[pd.Timestamp]) -> torch.Tensor:
    positions = resolve_time_positions(ds, months)
    array = squeeze_common_dims(ds[var_name].isel(valid_time=positions))
    array = array.sel(pressure_level=MODEL_ATMOS_LEVELS)
    array = array.transpose("valid_time", "pressure_level", "latitude", "longitude")
    return torch.from_numpy(array.values.astype(np.float32))


# Creiamo un gruppo di placeholder a zero per le variabili mancanti nella release locale.
def build_zero_group(var_names: list[str], months: list[pd.Timestamp]) -> dict[str, torch.Tensor]:
    return {
        name: torch.zeros((len(months), MODEL_HEIGHT, MODEL_WIDTH), dtype=torch.float32)
        for name in var_names
    }


def prepare_yearly_grid_frame(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    """Porta CSV annuali BioCube sulla griglia 0.25 gradi del modello."""
    required_columns = {"Latitude", "Longitude"}
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise KeyError(f"Colonne mancanti in {source_name}: {sorted(missing_columns)}")

    prepared = frame.copy()
    prepared["Latitude"] = snap_coordinates_to_grid(prepared["Latitude"])
    prepared["Longitude"] = snap_coordinates_to_grid(prepared["Longitude"])
    return prepared[
        prepared["Latitude"].between(MODEL_BOUNDS["min_lat"], MODEL_BOUNDS["max_lat"])
        & prepared["Longitude"].between(MODEL_BOUNDS["min_lon"], MODEL_BOUNDS["max_lon"])
    ]


def yearly_column_to_grid(
    frame: pd.DataFrame,
    column_name: str,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> torch.Tensor:
    """Rasterizza una colonna annuale CSV in una mappa [H, W] allineata al batch."""
    if column_name not in frame.columns:
        raise KeyError(f"Colonna annuale non trovata nel dataset: {column_name}")

    lat_index = {round(float(value), 2): idx for idx, value in enumerate(latitudes)}
    lon_index = {round(float(value), 2): idx for idx, value in enumerate(longitudes)}
    tensor = torch.zeros((MODEL_HEIGHT, MODEL_WIDTH), dtype=torch.float32)

    useful = frame[["Latitude", "Longitude", column_name]].dropna(subset=[column_name])
    grouped = useful.groupby(["Latitude", "Longitude"], as_index=False)[column_name].mean()

    for lat_value, lon_value, data_value in grouped[["Latitude", "Longitude", column_name]].itertuples(index=False, name=None):
        lat_key = round(float(lat_value), 2)
        lon_key = round(float(lon_value), 2)
        if lat_key not in lat_index or lon_key not in lon_index:
            continue
        tensor[lat_index[lat_key], lon_index[lon_key]] = float(data_value)

    return tensor


def find_monthly_column(columns: list[str], variable_name: str, month: pd.Timestamp) -> str:
    """Trova una colonna mensile in CSV BioCube accettando i formati piu probabili."""
    month = to_month_start(month)
    month_number = int(month.month)
    month_tokens = {
        f"{month_number}",
        f"{month_number:02d}",
        month.strftime("%b").lower(),
        month.strftime("%B").lower(),
    }
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

    ignored = {"country", "latitude", "longitude", "lat", "lon", "year", "month", "date", "timestamp", "variable"}
    regex_matches = []
    for column in columns:
        column_text = str(column)
        normalized = re.sub(r"[^a-zA-Z0-9]+", " ", column_text).casefold()
        tokens = set(normalized.split())
        if column_text.casefold() in ignored:
            continue
        if str(month.year) not in tokens:
            continue
        if not tokens.intersection(month_tokens):
            continue
        regex_matches.append(column_text)

    if regex_matches:
        with_variable_name = [name for name in regex_matches if variable_name.casefold() in name.casefold()]
        return with_variable_name[0] if with_variable_name else regex_matches[0]

    raise KeyError(
        f"Colonna mensile {variable_name} non trovata per {month:%Y-%m}. "
        f"Esempi attesi: {candidates[:6]}. "
        f"Prime colonne disponibili: {columns[:20]}"
    )


def find_value_column(columns: list[str], variable_name: str) -> str:
    """Trova una colonna valore in un CSV long-form di BioCube."""
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
    raise KeyError(f"Nessuna colonna valore trovata per {variable_name}. Colonne: {columns[:20]}")


def month_number_from_value(value) -> int:
    """Interpreta mese numerico, nome mese o data completa."""
    if pd.isna(value):
        raise ValueError("mese nullo")
    numeric_value = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if not pd.isna(numeric_value):
        return int(numeric_value)

    text = str(value).strip()
    try:
        return int(pd.Timestamp(text).month)
    except Exception:
        month_lookup = {
            "jan": 1,
            "january": 1,
            "feb": 2,
            "february": 2,
            "mar": 3,
            "march": 3,
            "apr": 4,
            "april": 4,
            "may": 5,
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
        key = text.casefold()[:3] if len(text) > 3 else text.casefold()
        if key in month_lookup:
            return month_lookup[key]
        if text.casefold() in month_lookup:
            return month_lookup[text.casefold()]
        raise


def build_vegetation_group_from_ndvi_csv(
    ndvi_path: Path,
    months: list[pd.Timestamp],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> dict[str, torch.Tensor]:
    """Costruisce il canale NDVI dal CSV ufficiale BioCube quando e disponibile."""
    ndvi_frame = prepare_yearly_grid_frame(pd.read_csv(ndvi_path), "ndvi")
    date_column = next(
        (name for name in ("Timestamp", "timestamp", "Date", "date", "Month", "month", "valid_time") if name in ndvi_frame.columns),
        None,
    )
    year_column = next((name for name in ("Year", "year", "YEAR", "Anno", "anno") if name in ndvi_frame.columns), None)
    month_column = next((name for name in ("Month", "month", "MONTH", "Mese", "mese") if name in ndvi_frame.columns), None)
    ndvi_column = next((name for name in ("NDVI", "ndvi") if name in ndvi_frame.columns), None)

    maps = []
    if year_column and month_column:
        value_column = ndvi_column or find_value_column(ndvi_frame.columns.tolist(), "NDVI")
        dated_frame = ndvi_frame.copy()
        dated_frame["_year"] = pd.to_numeric(dated_frame[year_column], errors="coerce").astype("Int64")
        dated_frame["_month_number"] = dated_frame[month_column].map(month_number_from_value)
        for month in months:
            month_frame = dated_frame[
                (dated_frame["_year"] == int(month.year))
                & (dated_frame["_month_number"] == int(month.month))
            ]
            if month_frame.empty:
                raise KeyError(f"Nessuna riga NDVI trovata per {to_month_start(month):%Y-%m}")
            maps.append(yearly_column_to_grid(month_frame, value_column, latitudes, longitudes))
    elif date_column:
        value_column = ndvi_column or find_value_column(ndvi_frame.columns.tolist(), "NDVI")
        dated_frame = ndvi_frame.copy()
        dated_frame["_month"] = pd.to_datetime(dated_frame[date_column]).dt.to_period("M").dt.to_timestamp()
        for month in months:
            month_frame = dated_frame[dated_frame["_month"] == to_month_start(month)]
            if month_frame.empty:
                raise KeyError(f"Nessuna riga NDVI trovata per {to_month_start(month):%Y-%m}")
            maps.append(yearly_column_to_grid(month_frame, value_column, latitudes, longitudes))
    else:
        maps = [
            yearly_column_to_grid(
                ndvi_frame,
                find_monthly_column(ndvi_frame.columns.tolist(), "NDVI", month),
                latitudes,
                longitudes,
            )
            for month in months
        ]
    return {"NDVI": torch.stack(maps)}


def build_forest_group(forest_path: Path, months: list[pd.Timestamp], latitudes: np.ndarray, longitudes: np.ndarray) -> dict[str, torch.Tensor]:
    """Costruisce il gruppo `forest` reale usando Europe_forest_data.csv."""
    forest_frame = prepare_yearly_grid_frame(pd.read_csv(forest_path), "forest")
    forest_maps = [
        yearly_column_to_grid(forest_frame, f"Forest_{pd.Timestamp(month).year}", latitudes, longitudes)
        for month in months
    ]
    return {"Forest": torch.stack(forest_maps)}


def build_agriculture_group(
    agriculture_path: Path,
    months: list[pd.Timestamp],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> dict[str, torch.Tensor]:
    """Costruisce Agriculture, Arable e Cropland dal CSV agricolo europeo."""
    agriculture_frame = prepare_yearly_grid_frame(pd.read_csv(agriculture_path), "agriculture")
    if "Variable" not in agriculture_frame.columns:
        raise KeyError("Colonna `Variable` mancante nel dataset agriculture.")

    agriculture_frame["Variable"] = agriculture_frame["Variable"].astype(str)
    available_variables = sorted(agriculture_frame["Variable"].dropna().unique().tolist())
    group = {}

    for variable_name in MODEL_AGRICULTURE_VARS:
        variable_frame = agriculture_frame[agriculture_frame["Variable"].str.casefold() == variable_name.casefold()]
        if variable_frame.empty:
            raise KeyError(
                f"Variabile agricola mancante: {variable_name}. "
                f"Variabili disponibili: {available_variables}"
            )

        maps = [
            yearly_column_to_grid(variable_frame, f"Agri_{pd.Timestamp(month).year}", latitudes, longitudes)
            for month in months
        ]
        group[variable_name] = torch.stack(maps)

    return group


def select_monthly_grid_array(
    ds: xr.Dataset,
    var_name: str,
    months: list[pd.Timestamp],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> xr.DataArray:
    """Estrae una variabile mensile e la riallinea alla griglia nativa 0.25 gradi."""
    positions = resolve_time_positions(ds, months)
    array = squeeze_common_dims(ds[var_name].isel(valid_time=positions))
    array = array.sel(
        latitude=xr.DataArray(latitudes, dims="latitude"),
        longitude=xr.DataArray(longitudes, dims="longitude"),
        method="nearest",
    )
    return array.transpose("valid_time", "latitude", "longitude")


def build_vegetation_group(
    vegetation_path: Path,
    months: list[pd.Timestamp],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> dict[str, torch.Tensor]:
    """Costruisce il canale `NDVI`; se manca NDVI usa una proxy dichiarata da LAI."""
    with xr.open_dataset(vegetation_path, engine="netcdf4") as ds:
        ds = normalize_longitude(ds)
        ndvi_var = next((name for name in ("NDVI", "ndvi") if name in ds.data_vars), None)

        if ndvi_var is not None:
            ndvi = select_monthly_grid_array(ds, ndvi_var, months, latitudes, longitudes)
        elif {"lai_hv", "lai_lv"}.issubset(ds.data_vars):
            lai_hv = select_monthly_grid_array(ds, "lai_hv", months, latitudes, longitudes).fillna(0.0)
            lai_lv = select_monthly_grid_array(ds, "lai_lv", months, latitudes, longitudes).fillna(0.0)
            total_lai = lai_hv + lai_lv
            # Proxy prudente: LAI e NDVI sono correlati ma non equivalenti.
            ndvi = (1.0 - np.exp(-0.5 * total_lai)).clip(min=0.0, max=0.92)
        else:
            raise KeyError(
                "Dataset vegetation senza NDVI e senza lai_hv/lai_lv. "
                f"Variabili disponibili: {list(ds.data_vars)}"
            )

        ndvi = ndvi.load()

    return {"NDVI": torch.from_numpy(ndvi.values.astype(np.float32))}


def build_vegetation_group_from_sources(
    source_paths: dict[str, Path],
    months: list[pd.Timestamp],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> dict[str, torch.Tensor]:
    """Preferisce il CSV NDVI ufficiale BioCube; altrimenti usa la sorgente LAI locale."""
    if "land_ndvi_csv" in source_paths:
        return build_vegetation_group_from_ndvi_csv(source_paths["land_ndvi_csv"], months, latitudes, longitudes)
    return build_vegetation_group(
        require_source_path(source_paths, "land_vegetation_dynamic"),
        months,
        latitudes,
        longitudes,
    )


def build_land_group_from_surface(surface_group: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
    """Costruisce il gruppo `Land` nel modo piu fedele possibile usando `lsm` reale di ERA5."""
    land_tensor = surface_group["lsm"].clone().to(torch.float32)
    return {"Land": land_tensor}


def build_native_group_source_status(*, use_atmospheric_data: bool, input_mode: str = "all") -> dict[str, str]:
    """Dichiara in modo esplicito quali gruppi sono reali e quali sono ancora placeholder."""
    input_mode = normalize_input_mode(input_mode)
    if input_mode == "clean":
        vegetation_status = "placeholder_zero_clean_input_mode"
        agriculture_status = "placeholder_zero_clean_input_mode"
        forest_status = "placeholder_zero_clean_input_mode"
        land_vegetation_status = "skipped_clean_input_mode"
    else:
        vegetation_status = "real_ndvi_csv_if_available_else_lai_proxy"
        agriculture_status = "real_from_europe_agriculture_csv"
        forest_status = "real_from_europe_forest_csv"
        land_vegetation_status = "prefer_land_ndvi_csv_else_lai_proxy"

    return {
        "surface": "real",
        "edaphic": "real",
        "atmospheric": "real" if use_atmospheric_data else "placeholder_zero_fast_smoke_test",
        "climate": "real",
        "species": "real",
        "vegetation": vegetation_status,
        "land": "real_from_surface_lsm",
        "agriculture": agriculture_status,
        "forest": forest_status,
        "redlist": "placeholder_zero",
        "misc": "placeholder_zero",
        "land_vegetation_dataset_available": land_vegetation_status,
    }


# Rasterizziamo le osservazioni specie in mappe mensili binarie [T, H, W] per ogni species ID ufficiale.
def build_species_group(species_path: Path, months: list[pd.Timestamp], latitudes: np.ndarray, longitudes: np.ndarray) -> dict[str, torch.Tensor]:
    month_lookup = {to_month_start(month): index for index, month in enumerate(months)}
    lat_index = {round(float(value), 2): idx for idx, value in enumerate(latitudes)}
    lon_index = {round(float(value), 2): idx for idx, value in enumerate(longitudes)}
    min_month = min(months)
    max_month = max(months)
    max_month_exclusive = shift_month(max_month, 1)

    tensors = {
        species_id: torch.zeros((len(months), MODEL_HEIGHT, MODEL_WIDTH), dtype=torch.float32)
        for species_id in MODEL_SPECIES_VARS
    }

    # Riduciamo la lettura del parquet alle sole righe che possono servire davvero a questo batch.
    species_df = pd.read_parquet(
        species_path,
        columns=["Species", "Latitude", "Longitude", "Timestamp"],
        filters=[
            ("Timestamp", ">=", min_month.to_pydatetime()),
            ("Timestamp", "<", max_month_exclusive.to_pydatetime()),
            ("Latitude", ">=", MODEL_BOUNDS["min_lat"]),
            ("Latitude", "<=", MODEL_BOUNDS["max_lat"]),
            ("Longitude", ">=", MODEL_BOUNDS["min_lon"]),
            ("Longitude", "<=", MODEL_BOUNDS["max_lon"]),
        ],
    )
    species_df["month"] = pd.to_datetime(species_df["Timestamp"]).dt.to_period("M").dt.to_timestamp()
    species_df = species_df[species_df["month"].isin(months)].copy()
    species_df["Species"] = species_df["Species"].astype(str)

    # Allineiamo le osservazioni specie alla stessa griglia ERA5 0.25° usata dal modello.
    species_df["Latitude"] = snap_coordinates_to_grid(species_df["Latitude"])
    species_df["Longitude"] = snap_coordinates_to_grid(species_df["Longitude"])

    grouped = (
        species_df.groupby(["month", "Species", "Latitude", "Longitude"])
        .size()
        .reset_index(name="count")
    )

    for row in grouped.itertuples(index=False):
        if row.Species not in tensors:
            continue
        if row.month not in month_lookup:
            continue
        if row.Latitude not in lat_index or row.Longitude not in lon_index:
            continue
        tensors[row.Species][month_lookup[row.month], lat_index[row.Latitude], lon_index[row.Longitude]] = 1.0

    return tensors


# Costruiamo il raw batch `.pt` per due mesi consecutivi partendo da BioCube locale.
def build_raw_batch_for_months(
    source_paths: dict[str, Path],
    months: list[pd.Timestamp],
    use_atmospheric_data: bool = True,
    input_mode: str = "all",
) -> dict:
    input_mode = normalize_input_mode(input_mode)
    print("  - preparo griglia modello", flush=True)
    latitudes, longitudes = load_model_grid(source_paths)

    print("  - carico surface", flush=True)
    surface_ds = open_model_domain_dataset(source_paths["surface"], months)
    print("  - carico edaphic", flush=True)
    edaphic_ds = open_model_domain_dataset(source_paths["edaphic"], months)
    pressure_ds = None
    if use_atmospheric_data:
        print("  - carico atmosphere", flush=True)
        pressure_ds = open_model_domain_dataset(source_paths["atmos"], months)
    else:
        print("  - atmosphere saltata, uso placeholder a zero", flush=True)
    print("  - carico climate_a", flush=True)
    climate_ds_a = open_model_domain_dataset(source_paths["climate_a"], months)
    print("  - carico climate_b", flush=True)
    climate_ds_b = open_model_domain_dataset(source_paths["climate_b"], months)
    if input_mode == "all":
        print("  - carico agriculture CSV", flush=True)
        agriculture_group = build_agriculture_group(
            require_source_path(source_paths, "agriculture_csv"),
            months,
            latitudes,
            longitudes,
        )
        print("  - carico forest CSV", flush=True)
        forest_group = build_forest_group(
            require_source_path(source_paths, "forest_csv"),
            months,
            latitudes,
            longitudes,
        )
        print("  - carico vegetation / NDVI", flush=True)
        vegetation_group = build_vegetation_group_from_sources(
            source_paths,
            months,
            latitudes,
            longitudes,
        )
    else:
        print("  - input-mode clean: vegetation/agriculture/forest a zero", flush=True)
        agriculture_group = build_zero_group(MODEL_AGRICULTURE_VARS, months)
        forest_group = build_zero_group(MODEL_FOREST_VARS, months)
        vegetation_group = build_zero_group(MODEL_VEGETATION_VARS, months)

    print("  - estraggo surface group", flush=True)
    surface_group = {name: extract_month_tensor(surface_ds, name, months) for name in MODEL_SURFACE_VARS}
    print("  - estraggo edaphic group", flush=True)
    edaphic_group = {name: extract_month_tensor(edaphic_ds, name, months) for name in MODEL_EDAPHIC_VARS}
    print("  - estraggo atmospheric group", flush=True)
    if use_atmospheric_data and pressure_ds is not None:
        atmospheric_group = {name: extract_atmospheric_tensor(pressure_ds, name, months) for name in MODEL_ATMOS_VARS}
    else:
        atmospheric_group = {
            name: torch.zeros((len(months), len(MODEL_ATMOS_LEVELS), MODEL_HEIGHT, MODEL_WIDTH), dtype=torch.float32)
            for name in MODEL_ATMOS_VARS
        }
    print("  - estraggo climate group", flush=True)
    climate_group = {
        name: extract_month_tensor(climate_ds_a, name, months)
        for name in MODEL_SOURCE_FILES["climate_a"][1]
    }
    climate_group.update(
        {
            name: extract_month_tensor(climate_ds_b, name, months)
            for name in MODEL_SOURCE_FILES["climate_b"][1]
        }
    )

    surface_ds.close()
    edaphic_ds.close()
    if pressure_ds is not None:
        pressure_ds.close()
    climate_ds_a.close()
    climate_ds_b.close()

    print("  - rasterizzo species group", flush=True)
    raw_batch = {
        "batch_metadata": {
            "latitudes": latitudes.tolist(),
            "longitudes": longitudes.tolist(),
            "timestamp": [month_to_timestamp_str(month) for month in months],
            "pressure_levels": MODEL_ATMOS_LEVELS,
            "species_list": MODEL_SPECIES_VARS,
        },
        "surface_variables": surface_group,
        "edaphic_variables": edaphic_group,
        "atmospheric_variables": atmospheric_group,
        "climate_variables": climate_group,
        "species_variables": build_species_group(source_paths["species"], months, latitudes, longitudes),
        "vegetation_variables": vegetation_group,
        "land_variables": build_land_group_from_surface(surface_group),
        "agriculture_variables": agriculture_group,
        "forest_variables": forest_group,
        "redlist_variables": build_zero_group(MODEL_REDLIST_VARS, months),
        "misc_variables": build_zero_group(MODEL_MISC_VARS, months),
    }
    print("  - raw batch completo", flush=True)
    return raw_batch


# Salviamo finestre `.pt` sovrapposte per test one-step e confronto storico.
def save_window_batches(
    output_dir: Path,
    input_months: list[pd.Timestamp],
    compare_month: pd.Timestamp | None,
    source_paths: dict[str, Path],
    use_atmospheric_data: bool = True,
    input_mode: str = "all",
) -> dict[str, Path | bool]:
    input_mode = normalize_input_mode(input_mode)
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / "window_00000.pt"
    torch.save(
        build_raw_batch_for_months(
            source_paths,
            input_months,
            use_atmospheric_data=use_atmospheric_data,
            input_mode=input_mode,
        ),
        input_path,
    )

    results: dict[str, Path | bool] = {
        "input_window": input_path,
        "atmospheric_data_real": bool(use_atmospheric_data),
        "input_mode": input_mode,
    }
    if compare_month is not None:
        target_path = output_dir / "window_00001.pt"
        torch.save(
            build_raw_batch_for_months(
                source_paths,
                [input_months[-1], compare_month],
                use_atmospheric_data=use_atmospheric_data,
                input_mode=input_mode,
            ),
            target_path,
        )
        results["target_window"] = target_path
    return results


# Selezioniamo il checkpoint locale richiesto e falliamo in modo esplicito se manca.
def resolve_checkpoint_path(model_dir: Path, checkpoint_name: str = "small") -> Path:
    filename = {
        "small": "bfm-pretrained-small.safetensors",
        "large": "bfm-pretrain-large.safetensors",
    }[checkpoint_name]
    checkpoint_path = model_dir / filename
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint non trovato: {checkpoint_path}")
    return checkpoint_path


def infer_checkpoint_kind(checkpoint_path: Path) -> str:
    """Deduce il tipo di checkpoint dal nome file per scegliere la config corretta."""
    name = checkpoint_path.name.lower()
    if "large" in name:
        return "large"
    return "small"


def checkpoint_model_overrides(checkpoint_kind: str) -> list[str]:
    """Override minimi per costruire l'architettura coerente con il checkpoint."""
    if checkpoint_kind == "large":
        return [
            "model.embed_dim=512",
            "model.depth=10",
            "model.patch_size=8",
            "model.swin_backbone_size=large",
            "model.num_heads=16",
            "training.precision=bf16-mixed",
        ]
    return [
        "model.embed_dim=256",
        "model.depth=3",
        "model.patch_size=4",
        "model.swin_backbone_size=medium",
        "model.num_heads=16",
        "training.precision=32-true",
    ]


# Costruiamo una config Hydra locale usando il repo ufficiale ma con path e device del progetto.
def build_local_config(batch_dir: Path, checkpoint_path: Path, device_name: str):
    checkpoint_kind = infer_checkpoint_kind(checkpoint_path)
    overrides = [
        *checkpoint_model_overrides(checkpoint_kind),
        f"model.H={MODEL_HEIGHT}",
        f"model.W={MODEL_WIDTH}",
        f"data.test_data_path='{batch_dir}'",
        f"data.scaling.stats_path='{MODEL_BATCH_STATS_PATH}'",
        f"data.land_mask_path='{MODEL_LAND_MASK_PATH}'",
        f"training.workers=0",
        f"evaluation.batch_size=1",
        f"evaluation.checkpoint_path='{checkpoint_path}'",
        "training.devices=[1]",
        "training.accelerator=cpu",
        "training.precision_in=high",
        f"evaluation.test_device={device_name}",
    ]

    GlobalHydra.instance().clear()
    with initialize_config_dir(config_dir=str(MODEL_CONFIG_DIR), version_base=None):
        cfg = compose(config_name="train_config", overrides=overrides)
    return cfg


# Istanziare direttamente BFM evita di trascinarsi dietro dipendenze di logging inutili per lo smoke test.
def build_bfm_model_from_cfg(cfg):
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.model import BFM

    selected_swin_config = cfg.model_swin_backbone[cfg.model.swin_backbone_size]
    swin_params = {
        "swin_encoder_depths": tuple(selected_swin_config.encoder_depths),
        "swin_encoder_num_heads": tuple(selected_swin_config.encoder_num_heads),
        "swin_decoder_depths": tuple(selected_swin_config.decoder_depths),
        "swin_decoder_num_heads": tuple(selected_swin_config.decoder_num_heads),
        "swin_window_size": tuple(selected_swin_config.window_size),
        "swin_mlp_ratio": selected_swin_config.mlp_ratio,
        "swin_qkv_bias": selected_swin_config.qkv_bias,
        "swin_drop_rate": selected_swin_config.drop_rate,
        "swin_attn_drop_rate": selected_swin_config.attn_drop_rate,
        "swin_drop_path_rate": selected_swin_config.drop_path_rate,
        "use_lora": selected_swin_config.use_lora,
    }

    return BFM(
        surface_vars=tuple(cfg.model.surface_vars),
        edaphic_vars=tuple(cfg.model.edaphic_vars),
        atmos_vars=tuple(cfg.model.atmos_vars),
        climate_vars=tuple(cfg.model.climate_vars),
        species_vars=tuple(cfg.model.species_vars),
        vegetation_vars=tuple(cfg.model.vegetation_vars),
        land_vars=tuple(cfg.model.land_vars),
        agriculture_vars=tuple(cfg.model.agriculture_vars),
        forest_vars=tuple(cfg.model.forest_vars),
        redlist_vars=tuple(cfg.model.redlist_vars),
        misc_vars=tuple(cfg.model.misc_vars),
        atmos_levels=cfg.data.atmos_levels,
        species_num=cfg.data.species_number,
        H=cfg.model.H,
        W=cfg.model.W,
        num_latent_tokens=cfg.model.num_latent_tokens,
        backbone_type=cfg.model.backbone,
        patch_size=cfg.model.patch_size,
        embed_dim=cfg.model.embed_dim,
        num_heads=cfg.model.num_heads,
        head_dim=cfg.model.head_dim,
        depth=cfg.model.depth,
        batch_size=cfg.evaluation.batch_size,
        land_mask_path=str(MODEL_LAND_MASK_PATH),
        lead_time=2,
        **swin_params,
    )


# Applichiamo lo stesso schema di scaling del repo ufficiale, ma con l'inversione corretta.
def _rescale_recursive_correct(
    obj,
    stats: dict,
    dimensions_to_keep_by_key: dict | list | None = None,
    mode: str = "normalize",
    direction: str = "scaled",
):
    dimensions_to_keep_by_key = dimensions_to_keep_by_key or {}

    if isinstance(obj, torch.Tensor):
        if not stats:
            return obj

        mean_val = stats["mean"]
        std_val = stats["std"]
        min_val = stats["min"]
        max_val = stats["max"]

        if dimensions_to_keep_by_key:
            if not isinstance(dimensions_to_keep_by_key, list) or len(dimensions_to_keep_by_key) != 1:
                raise ValueError(f"dimensions_to_keep_by_key non valido: {dimensions_to_keep_by_key}")
            dim_to_keep = dimensions_to_keep_by_key[0]
            split_count = obj.shape[dim_to_keep]
            chunks = torch.chunk(obj, chunks=split_count, dim=dim_to_keep)

            if not isinstance(mean_val, (list, tuple)):
                mean_val = [mean_val] * split_count
                std_val = [std_val] * split_count
                min_val = [min_val] * split_count
                max_val = [max_val] * split_count

            if mode == "standardize":
                if direction == "scaled":
                    changed = [(chunks[i] - mean_val[i]) / std_val[i] for i in range(split_count)]
                else:
                    changed = [chunks[i] * std_val[i] + mean_val[i] for i in range(split_count)]
            elif mode == "normalize":
                if direction == "scaled":
                    changed = [(chunks[i] - min_val[i]) / (max_val[i] - min_val[i]) for i in range(split_count)]
                else:
                    changed = [chunks[i] * (max_val[i] - min_val[i]) + min_val[i] for i in range(split_count)]
            else:
                raise ValueError(f"Modalità scaling non supportata: {mode}")

            return torch.cat(changed, dim=dim_to_keep)

        if mode == "standardize":
            if direction == "scaled":
                return (obj - mean_val) / std_val
            return obj * std_val + mean_val

        if mode == "normalize":
            if direction == "scaled":
                return (obj - min_val) / (max_val - min_val)
            return obj * (max_val - min_val) + min_val

        raise ValueError(f"Modalità scaling non supportata: {mode}")

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key not in {"batch_metadata", "metadata"}:
                obj[key] = _rescale_recursive_correct(
                    value,
                    stats.get(str(key), {}),
                    dimensions_to_keep_by_key.get(str(key), {}),
                    mode=mode,
                    direction=direction,
                )
        return obj

    return obj


# Convertiamo un Batch o dict tra spazio scalato e spazio originale senza usare l'inversione buggata del repo esterno.
def rescale_batch_correct(batch, scaling_statistics: dict, mode: str = "normalize", direction: str = "original"):
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.dataloader_monthly import Batch
    from bfm_model.bfm.scaler import dimensions_to_keep_monthly

    convert_to_batch = False
    if isinstance(batch, Batch):
        payload = deepcopy(batch._asdict())
        convert_to_batch = True
    else:
        payload = deepcopy(batch)

    _rescale_recursive_correct(
        payload,
        scaling_statistics,
        dimensions_to_keep_by_key=dimensions_to_keep_monthly,
        mode=mode,
        direction=direction,
    )

    if convert_to_batch:
        return Batch(**payload)
    return payload


# Scegliamo il device locale più robusto: CPU di default, MPS opzionale, mai CUDA su Mac.
def resolve_torch_device(device_request: str) -> torch.device:
    # Onoriamo esplicitamente la richiesta CPU.
    if device_request == "cpu":
        return torch.device("cpu")
    # Supportiamo CUDA quando il runtime ha una GPU NVIDIA disponibile.
    if device_request == "cuda":
        if torch.cuda.is_available():
            return torch.device("cuda")
        raise SystemExit("CUDA non disponibile su questa macchina.")
    # Manteniamo il supporto MPS per il Mac locale.
    if device_request == "mps":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        raise SystemExit("MPS non disponibile su questa macchina.")
    # In modalita auto preferiamo prima CUDA, poi MPS, e solo dopo CPU.
    if device_request == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
    return torch.device("cpu")


# Creiamo un riepilogo area-level dal batch unscaled usando le stesse coordinate del modello.
def summarize_batch_for_area(batch, bounds: dict[str, float], species_threshold: float = 0.5) -> dict[str, float | int]:
    latitudes = np.asarray(batch.batch_metadata.latitudes, dtype=np.float32)
    longitudes = np.asarray(batch.batch_metadata.longitudes, dtype=np.float32)
    if latitudes.ndim > 1:
        latitudes = latitudes[0]
    if longitudes.ndim > 1:
        longitudes = longitudes[0]

    lat_mask = (latitudes >= bounds["min_lat"]) & (latitudes <= bounds["max_lat"])
    lon_mask = (longitudes >= bounds["min_lon"]) & (longitudes <= bounds["max_lon"])
    if not lat_mask.any() or not lon_mask.any():
        raise SystemExit("L'area selezionata non interseca il dominio del modello.")

    lat_subset = latitudes[lat_mask]
    weights = np.cos(np.deg2rad(lat_subset)).reshape(-1, 1)

    def select_last_map(tensor):
        array = tensor.detach().cpu().numpy()
        if array.ndim == 5:
            return array[0, -1, 0]
        if array.ndim == 4:
            return array[0, -1]
        if array.ndim == 3:
            return array[-1]
        if array.ndim == 2:
            return array
        raise ValueError(f"Shape non supportata per mappa area-level: {array.shape}")

    temperature = select_last_map(batch.climate_variables["t2m"])[lat_mask][:, lon_mask] - 273.15
    precipitation = select_last_map(batch.climate_variables["tp"])[lat_mask][:, lon_mask] * 1000.0

    species_present = 0
    max_species_signal = []
    for species_name, tensor in batch.species_variables.items():
        area_values = select_last_map(tensor)[lat_mask][:, lon_mask]
        species_signal = float(np.nanmax(area_values)) if area_values.size else 0.0
        max_species_signal.append(species_signal)
        if species_signal >= species_threshold:
            species_present += 1

    weights_2d = np.broadcast_to(weights, temperature.shape)

    return {
        "temperature_mean_area_c": float(np.nansum(temperature * weights_2d) / np.nansum(weights_2d)),
        "precipitation_mean_area_mm": float(np.nansum(precipitation * weights_2d) / np.nansum(weights_2d)),
        "species_count_area_proxy": int(species_present),
        "max_species_signal_area": float(max(max_species_signal) if max_species_signal else 0.0),
        "cell_count_land_proxy": int(lat_mask.sum() * lon_mask.sum()),
    }


# Salviamo JSON piccoli in modo consistente per log e summary.
def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))


# Prepariamo una cartella scrivibile per i run forecast usando l'output esterno quando disponibile.
def resolve_forecast_output_dir(project_output_dir: Path, label: str) -> Path:
    base_dir, _ = resolve_output_base_dir(project_output_dir, PROJECT_ROOT)
    run_dir = base_dir / "model_forecast" / slugify(label)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


# Esportiamo una tabella forecast compatibile sia con CSV normale sia con Excel.
def write_forecast_tables(output_dir: Path, stem: str, frame: pd.DataFrame) -> dict[str, Path]:
    csv_path = output_dir / f"{stem}.csv"
    excel_csv_path = output_dir / f"{stem}_excel.csv"
    xlsx_path = output_dir / f"{stem}.xlsx"
    frame.to_csv(csv_path, index=False)
    frame.to_csv(excel_csv_path, index=False, sep=";", encoding="utf-8-sig")
    frame.to_excel(xlsx_path, index=False)
    return {
        "csv": csv_path,
        "excel_csv": excel_csv_path,
        "xlsx": xlsx_path,
    }


# Creiamo una tabella leggibile forecast vs observed per il report finale.
def build_comparison_frame(
    label: str,
    forecast_month: pd.Timestamp,
    selection_mode: str,
    bounds: dict[str, float],
    predicted_summary: dict[str, float | int],
    observed_summary: dict[str, float | int] | None,
) -> pd.DataFrame:
    records = [
        {
            "label": label,
            "selection_mode": selection_mode,
            "forecast_month": str(forecast_month.date()),
            "kind": "predicted",
            "temperature_mean_area_c": predicted_summary["temperature_mean_area_c"],
            "precipitation_mean_area_mm": predicted_summary["precipitation_mean_area_mm"],
            "species_count_area_proxy": predicted_summary["species_count_area_proxy"],
            "max_species_signal_area": predicted_summary["max_species_signal_area"],
            "area_bounds": json.dumps(bounds),
        }
    ]
    if observed_summary is not None:
        records.append(
            {
                "label": label,
                "selection_mode": selection_mode,
                "forecast_month": str(forecast_month.date()),
                "kind": "observed_next_month",
                "temperature_mean_area_c": observed_summary["temperature_mean_area_c"],
                "precipitation_mean_area_mm": observed_summary["precipitation_mean_area_mm"],
                "species_count_area_proxy": observed_summary["species_count_area_proxy"],
                "max_species_signal_area": observed_summary["max_species_signal_area"],
                "area_bounds": json.dumps(bounds),
            }
        )
    return pd.DataFrame.from_records(records)


# Carichiamo `.env` una volta sola prima di usare i path del progetto.
def load_project_env() -> None:
    env_path = first_existing_path(
        PROJECT_ROOT / ".env",
        SHARED_MAIN_ROOT / ".env",
    )
    load_dotenv(env_path)
