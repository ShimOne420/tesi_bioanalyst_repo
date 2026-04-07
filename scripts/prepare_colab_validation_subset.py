#!/usr/bin/env python3
"""Prepara un subset minimo del progetto per validare il forecast su Colab GPU.

Questo script serve a copiare solo i file davvero necessari per la validazione clima:

- subset BioCube minimo richiesto dal modello;
- checkpoint `small` di BioAnalyst;
- cartella output pulita;
- manifest finale con i path copiati.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from bioanalyst_model_utils import MODEL_SOURCE_FILES, load_project_env, require_path


# Copiamo un file singolo mantenendo metadata e creando le cartelle intermedie.
def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


# Costruiamo una CLI piccola e orientata all'export verso Google Drive o una cartella di staging.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepara il subset minimo per validazione GPU gratuita su Colab.")
    parser.add_argument(
        "--target-dir",
        required=True,
        help="Cartella target dove copiare subset dati, pesi e output.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Se presente, elimina la target dir prima di ricrearla.",
    )
    return parser


# Coordiniamo la copia dei file minimi davvero utili per la validazione clima.
def main() -> None:
    args = build_parser().parse_args()

    # Carichiamo i path del progetto locale.
    load_project_env()
    biocube_dir = require_path("BIOCUBE_DIR")
    model_dir = require_path("BIOANALYST_MODEL_DIR")

    # Prepariamo la cartella target, opzionalmente pulendola.
    target_dir = Path(args.target_dir).expanduser().resolve()
    if args.clean and target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    # Copiamo il subset minimo di BioCube necessario alla validazione forecast.
    copied_sources: dict[str, str] = {}
    for key, (relative_path, _) in MODEL_SOURCE_FILES.items():
        src = biocube_dir / relative_path
        if not src.exists():
            raise FileNotFoundError(f"Sorgente mancante per {key}: {src}")
        dst = target_dir / "biocube" / relative_path
        copy_file(src, dst)
        copied_sources[key] = str(dst)

    # Copiamo il checkpoint small, che e il punto di partenza attuale della validazione.
    small_ckpt = model_dir / "bfm-pretrained-small.safetensors"
    if not small_ckpt.exists():
        raise FileNotFoundError(f"Checkpoint small non trovato: {small_ckpt}")
    copied_checkpoint = target_dir / "models" / small_ckpt.name
    copy_file(small_ckpt, copied_checkpoint)

    # Prepariamo una cartella output vuota da usare direttamente anche su Colab.
    output_dir = target_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Scriviamo un manifest finale per documentare esattamente cosa e stato copiato.
    manifest = {
        "mode": "prepare_colab_validation_subset",
        "target_dir": str(target_dir),
        "biocube_subset_root": str(target_dir / "biocube"),
        "model_root": str(target_dir / "models"),
        "output_root": str(output_dir),
        "checkpoint": str(copied_checkpoint),
        "copied_sources": copied_sources,
    }
    (target_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # Stampiamo un riepilogo pratico utile dal terminale.
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


# Rendiamo lo script eseguibile da terminale VS Code.
if __name__ == "__main__":
    main()
