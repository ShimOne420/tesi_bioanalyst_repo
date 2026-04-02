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
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import xarray as xr
from dotenv import load_dotenv
from hydra import compose, initialize_config_dir
from hydra.core.global_hydra import GlobalHydra
from omegaconf import OmegaConf

from minimum_indicator_utils import build_bbox_from_point, normalize_longitude, resolve_output_base_dir


# Risolviamo una volta sola la root del progetto e il repo ufficiale clonato localmente.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BFM_REPO_ROOT = PROJECT_ROOT / "external" / "bfm-model"
MODEL_CONFIG_DIR = BFM_REPO_ROOT / "bfm_model" / "bfm" / "configs"
MODEL_BATCH_STATS_PATH = BFM_REPO_ROOT / "batch_statistics" / "monthly_batches_stats_splitted_channels.json"
MODEL_LAND_MASK_PATH = BFM_REPO_ROOT / "batch_statistics" / "europe_Land_2020_grid.pkl"
CITY_CATALOG_PATH = PROJECT_ROOT / "data" / "european_cities.json"


# Definiamo il dominio usato per i batch del modello, allineato alla mask ufficiale 160x280.
MODEL_BOUNDS = {
    "min_lat": 30.0,
    "max_lat": 70.0,
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
}


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
    climate_last_available = pd.Timestamp("2020-12-01")

    if input_last > climate_last_available:
        raise SystemExit("Il forecast locale usa ancora il blocco climatico BioCube 2000-2020. Scegli un `end` entro 2020-12.")

    compare_available = forecast_month <= climate_last_available
    return {
        "start_month": start_month,
        "end_month": end_month,
        "input_prev": input_prev,
        "input_last": input_last,
        "forecast_month": forecast_month,
        "compare_available": compare_available,
    }


# Risolviamo i path dei file sorgente raw realmente usati nella costruzione dei batch.
def resolve_source_paths(biocube_dir: Path) -> dict[str, Path]:
    resolved = {}
    for key, (relative_path, _) in MODEL_SOURCE_FILES.items():
        path = biocube_dir / relative_path
        if not path.exists():
            raise FileNotFoundError(f"Sorgente mancante per {key}: {path}")
        resolved[key] = path
    return resolved


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
    species_df["Latitude"] = species_df["Latitude"].round(2)
    species_df["Longitude"] = species_df["Longitude"].round(2)

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
) -> dict:
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
        "vegetation_variables": build_zero_group(MODEL_VEGETATION_VARS, months),
        "land_variables": build_zero_group(MODEL_LAND_VARS, months),
        "agriculture_variables": build_zero_group(MODEL_AGRICULTURE_VARS, months),
        "forest_variables": build_zero_group(MODEL_FOREST_VARS, months),
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
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / "window_00000.pt"
    torch.save(build_raw_batch_for_months(source_paths, input_months, use_atmospheric_data=use_atmospheric_data), input_path)

    results = {"input_window": input_path}
    if compare_month is not None:
        target_path = output_dir / "window_00001.pt"
        torch.save(
            build_raw_batch_for_months(
                source_paths,
                [input_months[-1], compare_month],
                use_atmospheric_data=use_atmospheric_data,
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


# Costruiamo una config Hydra locale usando il repo ufficiale ma con path e device del progetto.
def build_local_config(batch_dir: Path, checkpoint_path: Path, device_name: str):
    overrides = [
        "model.embed_dim=256",
        "model.depth=3",
        "model.swin_backbone_size=medium",
        "model.num_heads=16",
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
        "training.precision=32-true",
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


# Scegliamo il device locale più robusto: CPU di default, MPS opzionale, mai CUDA su Mac.
def resolve_torch_device(device_request: str) -> torch.device:
    if device_request == "cpu":
        return torch.device("cpu")
    if device_request == "mps":
        if torch.backends.mps.is_available():
            return torch.device("mps")
        raise SystemExit("MPS non disponibile su questa macchina.")
    if device_request == "auto" and torch.backends.mps.is_available():
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
        if array.ndim == 4:
            return array[0, -1]
        if array.ndim == 3:
            return array[-1]
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

    return {
        "temperature_mean_area_c": float(np.nansum(temperature * weights) / np.nansum(weights)),
        "precipitation_mean_area_mm": float(np.nansum(precipitation * weights) / np.nansum(weights)),
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
    load_dotenv(PROJECT_ROOT / ".env")
