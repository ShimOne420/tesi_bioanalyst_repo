#!/usr/bin/env python3
"""Runner rollout native di BioAnalyst."""

from __future__ import annotations

import json

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


def build_parser():
    parser = build_selection_parser("Runner rollout nativo BioAnalyst per area e periodo selezionati.")
    parser.add_argument("--checkpoint", choices=["small", "large"], default="small")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--steps", type=int, default=6, help="Numero di step mensili del rollout.")
    parser.add_argument(
        "--fast-smoke-test",
        action="store_true",
        help="Salta il blocco atmosferico e usa placeholder a zero per un test tecnico rapido.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.steps < 1:
        raise SystemExit("`--steps` deve essere almeno 1.")

    env = prepare_native_forecast_environment()
    context = build_native_run_context(
        args=args,
        project_output_dir=env["project_output_dir"],
        model_dir=env["model_dir"],
        run_suffix=f"native_rollout_{args.steps}m",
    )
    compare_month = context.months_info["forecast_month"] if context.months_info["compare_available"] else None
    print(f"[1/5] Setup native rollout pronto per `{context.label}` in `{context.run_dir}`", flush=True)

    saved_windows = prepare_native_saved_windows(
        context=context,
        source_paths=env["source_paths"],
        compare_month=compare_month,
        use_atmospheric_data=not args.fast_smoke_test,
    )
    print(f"[2/5] Batch iniziale nativo preparato in `{context.batch_dir}`", flush=True)

    runtime = build_native_runtime(
        batch_dir=context.batch_dir,
        checkpoint_path=context.checkpoint_path,
        device=context.device,
    )
    print(f"[3/5] Runner ufficiale pronto con checkpoint `{context.checkpoint_path.name}`", flush=True)

    result = run_native_rollout(
        context=context,
        runtime=runtime,
        saved_windows=saved_windows,
        steps=args.steps,
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

    summary = {
        "mode": "bioanalyst_native_rollout",
        "label": context.label,
        "selection_mode": context.selection_mode,
        "bounds": context.bounds,
        "project_root": str(env["project_root"]),
        "bfm_repo_root": str(env["bfm_repo_root"]),
        "checkpoint": str(context.checkpoint_path),
        "checkpoint_kind": context.checkpoint_kind,
        "device": str(context.device),
        "steps": args.steps,
        "fast_smoke_test": bool(args.fast_smoke_test),
        "input_months": [
            str(context.months_info["input_prev"].date()),
            str(context.months_info["input_last"].date()),
        ],
        "forecast_months": [str(month.date()) for month in result.forecast_months],
        "checkpoint_diagnostics": result.checkpoint_diagnostics,
        "manifest": str(artifact_paths["manifest"]),
        "native_rollout_batches_dir": str(artifact_paths["batches_dir"]),
    }
    print("[4/5] Output nativi rollout salvati", flush=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
