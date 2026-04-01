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
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pandas as pd
import xarray as xr
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCAL_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "local_preview"
CITY_CATALOG_PATH = PROJECT_ROOT / "data" / "european_cities.json"
load_dotenv(PROJECT_ROOT / ".env")


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
def parse_float(value: str) -> float | None:
    if value == "":
        return None
    return float(value)


# Convertiamo una stringa numerica in intero o `None`.
def parse_int(value: str) -> int | None:
    if value == "":
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


# Leggiamo il path del dataset dal file `.env` per usare i file reali di BioCube.
def get_biocube_dir() -> Path:
    raw_value = os.getenv("BIOCUBE_DIR")
    if not raw_value:
        raise HTTPException(status_code=500, detail="BIOCUBE_DIR non configurata nel file .env.")

    path = Path(raw_value).expanduser()
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"BIOCUBE_DIR non trovata: {path}")

    return path


# Restituiamo i path delle tre sorgenti minime usate dagli indicatori.
def get_source_paths() -> dict[str, Path]:
    biocube_dir = get_biocube_dir()
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


# Calcoliamo una sola volta il periodo realmente disponibile leggendo i file locali del dataset.
@lru_cache(maxsize=1)
def get_dataset_metadata() -> dict[str, Any]:
    source_paths = get_source_paths()

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

    common_start = max(species_min, temp_min, prec_min)
    common_end = min(species_max, temp_max, prec_max)

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
        },
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
                    "precipitation_mean_area_mm": parse_float(row["precipitation_mean_area_mm"]),
                    "cell_count_land": parse_int(row["cell_count_land"]),
                    "cells_with_species_records": parse_int(row["cells_with_species_records"]),
                    "species_count_observed_area": parse_int(row["species_count_observed_area"]),
                }
            )
        return rows


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
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
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

    return {
        "status": "ok",
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
        "notes": [summary["species_note"]],
        "downloads": {
            "csvUrl": f"/api/download/{label_slug}/csv",
            "excelCsvUrl": f"/api/download/{label_slug}/excel_csv",
            "xlsxUrl": f"/api/download/{label_slug}/xlsx",
        },
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
