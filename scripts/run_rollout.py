#!/usr/bin/env python3
"""Esegue un rollout native e pubblica i mesi previsti nel cache `previsioni/YYYY-MM`."""

from __future__ import annotations

import json
import os
from pathlib import Path

from omegaconf import OmegaConf

from bioanalyst_model_utils import build_selection_parser
from bioanalyst_native_utils import (
    build_native_run_context,
    build_native_runtime,
    prepare_native_forecast_environment,
    prepare_native_saved_windows,
    run_native_rollout,
    save_native_rollout_artifacts,
)
from run import export_reliable_feature_workbooks


def build_parser():
    parser = build_selection_parser(
        "Runner rollout BioAnalyst native con pubblicazione diretta del cache `previsioni/YYYY-MM`."
    )
    parser.add_argument("--checkpoint", choices=["small", "large"], default="small")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="cuda")
    parser.add_argument(
        "--input-mode",
        choices=["clean", "all"],
        default="all",
        help="clean usa solo input core; all aggiunge vegetation/agriculture/forest quando disponibili.",
    )
    parser.add_argument("--steps", type=int, default=6, help="Numero di mesi forecast da pubblicare.")
    parser.add_argument(
        "--fast-smoke-test",
        action="store_true",
        help="Usa placeholder atmosferici a zero per verificare velocemente la pipeline.",
    )
    parser.add_argument("--amp-bf16", action="store_true", help="Usa autocast bfloat16 su CUDA.")
    parser.add_argument(
        "--matrix-export-format",
        choices=["excel", "csv", "both"],
        default="excel",
        help="Formato dei workbook `cell_matrix` pubblicati nel cache forecast.",
    )
    parser.add_argument(
        "--forecast-cache-dir",
        type=Path,
        default=None,
        help="Override manuale della cartella `previsioni`. Se omesso usa FORECAST_CACHE_DIR o PROJECT_OUTPUT_DIR/previsioni.",
    )
    return parser


def resolve_forecast_cache_dir(env: dict[str, Path], args) -> Path:
    raw_value = args.forecast_cache_dir or os.getenv("FORECAST_CACHE_DIR")
    cache_dir = Path(raw_value).expanduser() if raw_value else (env["project_output_dir"] / "previsioni")
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def build_primary_area_specs(context) -> list[dict[str, object]]:
    return [
        {
            "area_label": context.label,
            "area_kind": context.selection_mode,
            "bounds": context.bounds,
            "is_primary_area": True,
        }
    ]


def main() -> None:
    args = build_parser().parse_args()
    if args.steps < 1:
        raise SystemExit("`--steps` deve essere almeno 1.")

    env = prepare_native_forecast_environment()
    context = build_native_run_context(
        args=args,
        project_output_dir=env["project_output_dir"],
        model_dir=env["model_dir"],
        source_paths=env["source_paths"],
        run_suffix=f"native_rollout_{args.steps}m",
    )
    compare_month = context.months_info["forecast_month"] if context.months_info["compare_available"] else None
    print(f"[1/5] Setup rollout pronto per `{context.label}` in `{context.run_dir}`", flush=True)

    saved_windows = prepare_native_saved_windows(
        context=context,
        source_paths=env["source_paths"],
        compare_month=compare_month,
        use_atmospheric_data=not args.fast_smoke_test,
    )
    print(f"[2/5] Batch iniziale preparato in `{context.batch_dir}`", flush=True)

    runtime = build_native_runtime(
        batch_dir=context.batch_dir,
        checkpoint_path=context.checkpoint_path,
        device=context.device,
    )
    print(f"[3/5] Modello caricato con checkpoint `{context.checkpoint_path.name}`", flush=True)

    result = run_native_rollout(
        context=context,
        runtime=runtime,
        saved_windows=saved_windows,
        steps=args.steps,
        use_amp_bf16=args.amp_bf16,
    )
    artifact_paths = save_native_rollout_artifacts(
        context=context,
        runtime=runtime,
        result=result,
    )
    (context.run_dir / "forecast_native_rollout_config.yaml").write_text(
        OmegaConf.to_yaml(runtime.cfg),
        encoding="utf-8",
    )

    manifest = json.loads(artifact_paths["manifest"].read_text(encoding="utf-8"))
    cache_dir = resolve_forecast_cache_dir(env, args)
    area_specs = build_primary_area_specs(context)
    published_months: list[dict[str, object]] = []

    print(f"[4/5] Pubblico il cache forecast in `{cache_dir}`", flush=True)
    for step_index, (forecast_month, batch) in enumerate(
        zip(result.forecast_months, result.rollout_batches_original, strict=True),
        start=1,
    ):
        month_label = forecast_month.strftime("%Y-%m")
        month_dir = cache_dir / month_label
        cell_matrix_dir = month_dir / "cell_matrix"
        month_dir.mkdir(parents=True, exist_ok=True)

        month_manifest = {
            **manifest,
            "forecast_month": str(forecast_month.date()),
            "rollout_step_index": step_index,
            "rollout_steps_total": args.steps,
            "source_run_dir": str(context.run_dir),
        }
        export_outputs = export_reliable_feature_workbooks(
            run_dir=context.run_dir,
            manifest=month_manifest,
            predicted_batch=batch,
            observed_batch=None,
            area_specs=area_specs,
            export_root=cell_matrix_dir,
            flat_output=True,
            matrix_export_format=args.matrix_export_format,
        )
        cache_manifest = {
            "mode": "bioanalyst_native_rollout_cache",
            "forecast_month": str(forecast_month.date()),
            "rollout_step_index": step_index,
            "rollout_steps_total": args.steps,
            "input_months": manifest["input_months"],
            "source_run_dir": str(context.run_dir),
            "cell_matrix_dir": str(cell_matrix_dir),
            "features": export_outputs.get("features", {}),
            "missing_features": export_outputs.get("missing_features", []),
        }
        (month_dir / "_forecast_cache_manifest.json").write_text(
            json.dumps(cache_manifest, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        published_months.append(
            {
                "month": month_label,
                "cell_matrix_dir": str(cell_matrix_dir),
                "manifest": str(month_dir / "_forecast_cache_manifest.json"),
            }
        )

    summary = {
        "mode": "bioanalyst_native_rollout_cache_publish",
        "label": context.label,
        "selection_mode": context.selection_mode,
        "bounds": context.bounds,
        "checkpoint": str(context.checkpoint_path),
        "checkpoint_kind": context.checkpoint_kind,
        "device": str(context.device),
        "steps": args.steps,
        "input_months": manifest["input_months"],
        "forecast_months": [str(month.date()) for month in result.forecast_months],
        "run_dir": str(context.run_dir),
        "forecast_cache_dir": str(cache_dir),
        "published_months": published_months,
    }
    print("[5/5] Cache forecast pronto", flush=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
