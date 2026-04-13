#!/usr/bin/env python3
"""Legge un run native e stampa un riepilogo leggibile del forecast."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bioanalyst_model_utils import write_json
from bioanalyst_native_utils import (
    NATIVE_GROUP_FIELDS,
    compute_native_climate_comparison,
    compute_native_group_comparison,
    evaluate_native_run_sanity,
    load_native_batch_artifact,
    load_native_manifest,
    resolve_native_batch_path,
    summarize_native_batch,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Legge un run native di BioAnalyst e stampa summary, variabili e confronto con observed.",
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="Cartella del run che contiene `forecast_native_manifest.json`.")
    parser.add_argument(
        "--batch-kind",
        choices=["prediction", "observed", "rollout"],
        default="prediction",
        help="Quale batch leggere in dettaglio.",
    )
    parser.add_argument(
        "--rollout-step",
        type=int,
        default=None,
        help="Step del rollout da leggere se `--batch-kind rollout`.",
    )
    parser.add_argument(
        "--group",
        choices=sorted(NATIVE_GROUP_FIELDS),
        default="climate",
        help="Gruppo da ispezionare in dettaglio.",
    )
    parser.add_argument(
        "--variable",
        default="t2m",
        help="Variabile del gruppo da ispezionare in dettaglio.",
    )
    parser.add_argument(
        "--no-save-json",
        action="store_true",
        help="Non salva `native_inspection_summary.json` nella cartella del run.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run_dir = args.run_dir.resolve()
    manifest = load_native_manifest(run_dir)

    batch_path = resolve_native_batch_path(
        manifest,
        batch_kind=args.batch_kind,
        rollout_step=args.rollout_step,
    )
    batch = load_native_batch_artifact(batch_path)

    summary = {
        "run_dir": str(run_dir),
        "mode": manifest.get("mode"),
        "label": manifest.get("label"),
        "selection_mode": manifest.get("selection_mode"),
        "bounds": manifest.get("bounds"),
        "checkpoint_kind": manifest.get("checkpoint_kind"),
        "device": manifest.get("device"),
        "checkpoint_diagnostics": manifest.get("checkpoint_diagnostics"),
        "group_source_status": manifest.get("group_source_status"),
        "inspected_batch": str(batch_path),
        "batch_summary": summarize_native_batch(
            batch,
            group_name=args.group,
            variable_name=args.variable,
        ),
    }

    if manifest.get("native_prediction_original") and manifest.get("native_target_original"):
        predicted_batch = load_native_batch_artifact(Path(manifest["native_prediction_original"]))
        observed_batch = load_native_batch_artifact(Path(manifest["native_target_original"]))
        summary["native_sanity_checks"] = evaluate_native_run_sanity(
            manifest,
            predicted_batch,
            observed_batch,
        )
        summary["native_climate_comparison"] = compute_native_climate_comparison(
            predicted_batch,
            observed_batch,
            bounds=manifest.get("bounds"),
        )
        summary["native_group_comparison"] = compute_native_group_comparison(
            predicted_batch,
            observed_batch,
            group_name=args.group,
            bounds=manifest.get("bounds"),
        )

    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if not args.no_save_json:
        output_path = run_dir / "native_inspection_summary.json"
        write_json(output_path, summary)
        print(f"\nSummary salvato in: {output_path}")


if __name__ == "__main__":
    main()
