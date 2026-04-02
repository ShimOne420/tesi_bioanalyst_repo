#!/usr/bin/env python3
"""Scarica i pesi ufficiali di BioAnalyst nella cartella esterna configurata.

Questo script tiene i checkpoint fuori da GitHub e usa il path definito in `.env`
tramite `BIOANALYST_MODEL_DIR`.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi, hf_hub_download


# Definiamo il repository ufficiale dei pesi e i checkpoint noti.
REPO_ID = "BioDT/bfm-pretrained"
CHECKPOINTS = {
    "small": "bfm-pretrained-small.safetensors",
    "large": "bfm-pretrain-large.safetensors",
}


# Risolviamo la root del progetto per trovare `.env`.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


# Recuperiamo una directory da ambiente e la creiamo se manca.
def require_directory(env_name: str) -> Path:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {env_name}")
    path = Path(value).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


# Costruiamo la CLI con opzioni semplici per listare o scaricare i checkpoint.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scarica i pesi ufficiali di BioAnalyst.")
    parser.add_argument(
        "--checkpoint",
        choices=sorted(CHECKPOINTS),
        default="small",
        help="Checkpoint da scaricare: small o large.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Mostra i file disponibili nel repository Hugging Face e termina.",
    )
    return parser


# Stampiamo un riepilogo leggibile dei file presenti nel repository remoto.
def print_available_files() -> None:
    api = HfApi()
    for item in api.list_repo_files(repo_id=REPO_ID, repo_type="model"):
        print(item)


# Eseguiamo il download con resume verso la cartella esterna del progetto.
def main() -> None:
    args = build_parser().parse_args()
    load_dotenv(PROJECT_ROOT / ".env")

    if args.list:
        print_available_files()
        return

    model_dir = require_directory("BIOANALYST_MODEL_DIR")
    filename = CHECKPOINTS[args.checkpoint]

    downloaded_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=filename,
        local_dir=model_dir,
        local_dir_use_symlinks=False,
        resume_download=True,
    )

    checkpoint_path = Path(downloaded_path)
    size_gb = checkpoint_path.stat().st_size / (1024**3)

    print(f"Checkpoint scaricato: {checkpoint_path}")
    print(f"Dimensione: {size_gb:.2f} GB")


# Rendiamo lo script eseguibile da terminale.
if __name__ == "__main__":
    main()
