from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


# Definiamo gli argomenti CLI per dry-run, download reale e filtri sui moduli da scaricare.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Wrapper locale per pianificare o scaricare BioCube usando BIOCUBE_DIR da .env."
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Esegue il download reale. Senza questo flag esegue solo dry-run.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Numero di download paralleli.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Abilita la modalita veloce del downloader originale.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help='Pattern da includere, ripetibile. Esempio: --include "Species/*"',
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help='Pattern da escludere, ripetibile. Esempio: --exclude "*.csv"',
    )
    return parser


# Carichiamo il path di destinazione da `.env` e richiamiamo il downloader originale del repo.
def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    repo_root = project_root.parents[1]
    env_path = project_root / ".env"
    load_dotenv(env_path)

    target_dir = os.getenv("BIOCUBE_DIR")
    if not target_dir:
        raise SystemExit("BIOCUBE_DIR non impostata in .env")

    downloader = repo_root / "Dataset" / "scripts" / "download_biocube.py"
    if not downloader.exists():
        raise SystemExit(f"Downloader non trovato: {downloader}")

    args = build_parser().parse_args()

    cmd = [
        sys.executable,
        str(downloader),
        "--target-dir",
        target_dir,
        "--workers",
        str(args.workers),
    ]

    if args.download:
        cmd.append("--download")
    if args.fast:
        cmd.append("--fast")
    for pattern in args.include:
        cmd.extend(["--include", pattern])
    for pattern in args.exclude:
        cmd.extend(["--exclude", pattern])

    print("Eseguo comando:")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd, check=False)
    return result.returncode


# Rendiamo lo script eseguibile da terminale.
if __name__ == "__main__":
    raise SystemExit(main())
