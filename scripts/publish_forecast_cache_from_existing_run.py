#!/usr/bin/env python3
"""Pubblica un run forecast già esistente nel formato cache `previsioni/YYYY-MM/cell_matrix`."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd

from bioanalyst_native_utils import (
    load_native_batch_artifact,
    load_native_manifest,
    resolve_native_batch_path,
)
from run import export_reliable_feature_workbooks


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Copia un run native gia esistente nella struttura forecast cache usata dal frontend, "
            "senza rieseguire il modello."
        )
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="Cartella del run con forecast_native_manifest.json.")
    parser.add_argument("--month", required=True, help="Mese da pubblicare nel cache, formato YYYY-MM.")
    parser.add_argument(
        "--batch-kind",
        choices=["prediction", "rollout"],
        default="prediction",
        help="Usa la prediction one-step oppure uno step del rollout.",
    )
    parser.add_argument(
        "--rollout-step",
        type=int,
        default=None,
        help="Step rollout da usare quando --batch-kind rollout.",
    )
    parser.add_argument(
        "--forecast-cache-dir",
        type=Path,
        default=None,
        help="Override manuale della cartella previsioni. Se omesso usa FORECAST_CACHE_DIR.",
    )
    parser.add_argument(
        "--matrix-export-format",
        choices=["excel", "csv", "both"],
        default="excel",
        help="Formato dei workbook cell_matrix pubblicati nel cache.",
    )
    return parser


def normalize_month_label(value: str) -> str:
    return pd.Timestamp(value).to_period("M").strftime("%Y-%m")


def resolve_forecast_cache_dir(args) -> Path:
    raw_value = args.forecast_cache_dir or os.getenv("FORECAST_CACHE_DIR")
    if not raw_value:
        raise SystemExit("Imposta FORECAST_CACHE_DIR oppure passa --forecast-cache-dir.")
    cache_dir = Path(raw_value).expanduser()
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def build_area_specs(manifest: dict[str, object]) -> list[dict[str, object]]:
    bounds = manifest.get("bounds")
    if not isinstance(bounds, dict):
        raise SystemExit("Nel manifest manca `bounds`.")
    return [
        {
            "area_label": str(manifest.get("label", "selected_area")),
            "area_kind": str(manifest.get("selection_mode", "selected_area")),
            "bounds": bounds,
            "is_primary_area": True,
        }
    ]


def main() -> None:
    args = build_parser().parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    manifest = load_native_manifest(run_dir)
    batch_path = resolve_native_batch_path(
        manifest,
        batch_kind=args.batch_kind,
        rollout_step=args.rollout_step,
    )
    batch = load_native_batch_artifact(batch_path)

    month_label = normalize_month_label(args.month)
    month_dir = resolve_forecast_cache_dir(args) / month_label
    cell_matrix_dir = month_dir / "cell_matrix"
    month_dir.mkdir(parents=True, exist_ok=True)

    publish_manifest = {
        **manifest,
        "forecast_month": f"{month_label}-01",
        "source_run_dir": str(run_dir),
        "source_batch_kind": args.batch_kind,
        "source_rollout_step": args.rollout_step,
    }
    export_outputs = export_reliable_feature_workbooks(
        run_dir=run_dir,
        manifest=publish_manifest,
        predicted_batch=batch,
        observed_batch=None,
        area_specs=build_area_specs(manifest),
        export_root=cell_matrix_dir,
        flat_output=True,
        matrix_export_format=args.matrix_export_format,
    )

    cache_manifest = {
        "mode": "forecast_cache_publish_from_existing_run",
        "forecast_month": f"{month_label}-01",
        "source_run_dir": str(run_dir),
        "source_batch_kind": args.batch_kind,
        "source_rollout_step": args.rollout_step,
        "cell_matrix_dir": str(cell_matrix_dir),
        "features": export_outputs.get("features", {}),
        "missing_features": export_outputs.get("missing_features", []),
    }
    (month_dir / "_forecast_cache_manifest.json").write_text(
        json.dumps(cache_manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "month": month_label,
                "cache_dir": str(month_dir),
                "cell_matrix_dir": str(cell_matrix_dir),
                "manifest": str(month_dir / "_forecast_cache_manifest.json"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
