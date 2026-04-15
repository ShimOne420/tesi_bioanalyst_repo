#!/usr/bin/env python3
"""Scarica da Hugging Face il subset BioCube necessario al ramo native."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import snapshot_download


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ID = "BioDT/BioCube"


MINIMAL_NATIVE_PATTERNS = [
    "Copernicus/ERA5-monthly/era5-single/era5_single.nc",
    "Copernicus/ERA5-monthly/era5-edaphic/era5-edaphic-0.nc",
    "Copernicus/ERA5-monthly/era5-pressure/era5_pressure.nc",
    "Copernicus/ERA5-monthly/era5-climate-energy-moisture/era5-climate-energy-moisture-0.nc",
    "Copernicus/ERA5-monthly/era5-climate-energy-moisture/era5-climate-energy-moisture-1.nc",
    "Copernicus/ERA5-monthly/era5-land-vegetation/*",
    "Species/europe_species.parquet",
]


EXTRA_MODALITY_PATTERNS = [
    "Agriculture/*",
    "Forest/*",
    "Land/*",
    "RedList/*",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scarica BioCube nella cartella BIOCUBE_DIR configurata nel file .env.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Scarica tutto BioCube. Richiede molto spazio disco.",
    )
    parser.add_argument(
        "--with-extra-modalities",
        action="store_true",
        help="Aggiunge Agriculture, Forest, Land e RedList al subset minimo.",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=None,
        help="Cartella di destinazione. Se omessa usa BIOCUBE_DIR da .env.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra cosa verrebbe scaricato senza avviare il download.",
    )
    return parser


def resolve_target_dir(cli_target: Path | None) -> Path:
    if cli_target is not None:
        return cli_target.expanduser().resolve()

    load_dotenv(PROJECT_ROOT / ".env")
    value = os.getenv("BIOCUBE_DIR")
    if not value:
        raise SystemExit("BIOCUBE_DIR non impostata in .env e nessun --target-dir fornito.")
    return Path(value).expanduser().resolve()


def build_allow_patterns(*, full: bool, with_extra_modalities: bool) -> list[str] | None:
    if full:
        return None
    patterns = list(MINIMAL_NATIVE_PATTERNS)
    if with_extra_modalities:
        patterns.extend(EXTRA_MODALITY_PATTERNS)
    return patterns


def main() -> None:
    args = build_parser().parse_args()
    target_dir = resolve_target_dir(args.target_dir)
    allow_patterns = build_allow_patterns(
        full=args.full,
        with_extra_modalities=args.with_extra_modalities,
    )

    print(f"Repository Hugging Face: {REPO_ID}")
    print(f"Destinazione: {target_dir}")
    if allow_patterns is None:
        print("Modalita: download completo")
    else:
        print("Modalita: subset")
        for pattern in allow_patterns:
            print(f"  - {pattern}")

    if args.dry_run:
        print("\nDry-run completato. Nessun file scaricato.")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        local_dir=target_dir,
        allow_patterns=allow_patterns,
        resume_download=True,
    )
    print("\nDownload completato.")
    print(f"BioCube disponibile in: {target_dir}")


if __name__ == "__main__":
    main()
