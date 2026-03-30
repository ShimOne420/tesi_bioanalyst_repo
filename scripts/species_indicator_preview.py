#!/usr/bin/env python3
"""Preview del primo indicatore minimo: species richness."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require_path(env_name: str) -> Path:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {env_name}")
    path = Path(value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Percorso non trovato per {env_name}: {path}")
    return path


def main() -> None:
    load_dotenv()

    biocube_dir = require_path("BIOCUBE_DIR")
    output_dir = require_path("PROJECT_OUTPUT_DIR")
    species_path = biocube_dir / "Species" / "europe_species.parquet"

    if not species_path.exists():
        raise FileNotFoundError(f"File specie non trovato: {species_path}")

    df = pd.read_parquet(
        species_path,
        columns=["Species", "Latitude", "Longitude", "Timestamp"],
    )

    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    richness = (
        df.groupby(["Latitude", "Longitude", "Timestamp"])["Species"]
        .nunique()
        .reset_index(name="species_richness")
        .sort_values(["Timestamp", "Latitude", "Longitude"])
    )

    summary = {
        "source_file": str(species_path),
        "rows_raw": int(len(df)),
        "unique_species_total": int(df["Species"].nunique()),
        "unique_cells": int(df[["Latitude", "Longitude"]].drop_duplicates().shape[0]),
        "time_start": str(df["Timestamp"].min().date()),
        "time_end": str(df["Timestamp"].max().date()),
        "rows_species_richness": int(len(richness)),
        "species_richness_min": int(richness["species_richness"].min()),
        "species_richness_max": int(richness["species_richness"].max()),
        "species_richness_mean": float(richness["species_richness"].mean()),
    }

    preferred_output_dir = output_dir
    fallback_output_dir = PROJECT_ROOT / "outputs" / "local_preview"
    summary_path = preferred_output_dir / "species_richness_summary.json"
    preview_path = preferred_output_dir / "species_richness_preview.csv"

    try:
        preferred_output_dir.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        richness.head(500).to_csv(preview_path, index=False)
        effective_output_dir = preferred_output_dir
    except PermissionError:
        fallback_output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = fallback_output_dir / "species_richness_summary.json"
        preview_path = fallback_output_dir / "species_richness_preview.csv"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        richness.head(500).to_csv(preview_path, index=False)
        effective_output_dir = fallback_output_dir

    print("Species richness preview creato con successo.")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nSummary: {summary_path}")
    print(f"Preview CSV (prime 500 righe): {preview_path}")
    if effective_output_dir == fallback_output_dir:
        print(
            "\nNota: ho usato la cartella locale del repo perché il path esterno non era "
            "scrivibile in questo ambiente."
        )


if __name__ == "__main__":
    main()
