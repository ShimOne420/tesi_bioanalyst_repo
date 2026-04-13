#!/usr/bin/env python3
"""Converte un run native di BioAnalyst in indicatori area-level per BIOMAP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from bioanalyst_model_utils import summarize_batch_for_area, write_forecast_tables, write_json
from bioanalyst_native_utils import load_native_batch_artifact, load_native_manifest


def build_parser():
    parser = argparse.ArgumentParser(
        description="Legge un run native e salva un export BIOMAP minimale con temperatura, precipitazione e species proxy.",
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="Cartella del run native.")
    parser.add_argument(
        "--species-threshold",
        type=float,
        default=0.5,
        help="Soglia usata per considerare presente una specie nel proxy area-level.",
    )
    return parser


def build_indicator_record(
    *,
    manifest: dict,
    forecast_month: str,
    summary: dict[str, float | int],
    kind: str,
    step_index: int | None = None,
) -> dict[str, object]:
    return {
        "label": manifest["label"],
        "selection_mode": manifest["selection_mode"],
        "forecast_month": forecast_month,
        "kind": kind,
        "step_index": step_index,
        "temperature_mean_area_c": summary["temperature_mean_area_c"],
        "precipitation_mean_area_mm": summary["precipitation_mean_area_mm"],
        "species_count_area_proxy": summary["species_count_area_proxy"],
        "max_species_signal_area": summary["max_species_signal_area"],
        "cell_count_land_proxy": summary["cell_count_land_proxy"],
        "area_bounds": json.dumps(manifest["bounds"]),
    }


def compute_biomap_deltas(predicted: dict[str, float | int], observed: dict[str, float | int]) -> dict[str, float]:
    return {
        "temperature_abs_error_c": abs(predicted["temperature_mean_area_c"] - observed["temperature_mean_area_c"]),
        "precipitation_abs_error_mm": abs(
            predicted["precipitation_mean_area_mm"] - observed["precipitation_mean_area_mm"]
        ),
        "species_count_abs_error_proxy": abs(
            float(predicted["species_count_area_proxy"]) - float(observed["species_count_area_proxy"])
        ),
    }


def export_one_step(manifest: dict, run_dir: Path, species_threshold: float) -> dict[str, Path]:
    predicted_batch = load_native_batch_artifact(Path(manifest["native_prediction_original"]))
    predicted_summary = summarize_batch_for_area(
        predicted_batch,
        manifest["bounds"],
        species_threshold=species_threshold,
    )

    records = [
        build_indicator_record(
            manifest=manifest,
            forecast_month=manifest["forecast_month"],
            summary=predicted_summary,
            kind="predicted",
        )
    ]

    observed_summary = None
    comparison_metrics = None
    if manifest.get("native_target_original"):
        observed_batch = load_native_batch_artifact(Path(manifest["native_target_original"]))
        observed_summary = summarize_batch_for_area(
            observed_batch,
            manifest["bounds"],
            species_threshold=species_threshold,
        )
        records.append(
            build_indicator_record(
                manifest=manifest,
                forecast_month=manifest["forecast_month"],
                summary=observed_summary,
                kind="observed_next_month",
            )
        )
        comparison_metrics = compute_biomap_deltas(predicted_summary, observed_summary)

    biomap_dir = run_dir / "biomap"
    biomap_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame.from_records(records)
    table_paths = write_forecast_tables(biomap_dir, "biomap_area_summary", frame)

    summary_payload = {
        "mode": manifest["mode"],
        "label": manifest["label"],
        "forecast_month": manifest["forecast_month"],
        "species_threshold": species_threshold,
        "predicted_summary": predicted_summary,
        "observed_summary": observed_summary,
        "comparison_metrics": comparison_metrics,
    }
    summary_json = biomap_dir / "biomap_area_summary.json"
    write_json(summary_json, summary_payload)

    return {
        **table_paths,
        "json": summary_json,
    }


def export_rollout(manifest: dict, run_dir: Path, species_threshold: float) -> dict[str, Path]:
    records = []
    for step_index, (forecast_month, batch_path) in enumerate(
        zip(manifest["forecast_months"], manifest["native_rollout_batches"], strict=True),
        start=1,
    ):
        batch = load_native_batch_artifact(Path(batch_path))
        summary = summarize_batch_for_area(
            batch,
            manifest["bounds"],
            species_threshold=species_threshold,
        )
        records.append(
            build_indicator_record(
                manifest=manifest,
                forecast_month=forecast_month,
                summary=summary,
                kind="predicted_rollout",
                step_index=step_index,
            )
        )

    biomap_dir = run_dir / "biomap"
    biomap_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame.from_records(records)
    table_paths = write_forecast_tables(biomap_dir, "biomap_rollout_summary", frame)

    summary_payload = {
        "mode": manifest["mode"],
        "label": manifest["label"],
        "forecast_months": manifest["forecast_months"],
        "species_threshold": species_threshold,
        "rows": len(records),
    }
    summary_json = biomap_dir / "biomap_rollout_summary.json"
    write_json(summary_json, summary_payload)

    return {
        **table_paths,
        "json": summary_json,
    }


def main() -> None:
    args = build_parser().parse_args()
    run_dir = args.run_dir.resolve()
    manifest = load_native_manifest(run_dir)

    if manifest["mode"] == "bioanalyst_native_one_step":
        output_paths = export_one_step(manifest, run_dir, args.species_threshold)
    elif manifest["mode"] == "bioanalyst_native_rollout":
        output_paths = export_rollout(manifest, run_dir, args.species_threshold)
    else:
        raise SystemExit(f"Modalità run non supportata: {manifest['mode']}")

    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "mode": manifest["mode"],
                "species_threshold": args.species_threshold,
                "outputs": {key: str(value) for key, value in output_paths.items()},
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
