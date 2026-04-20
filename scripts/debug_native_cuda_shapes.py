#!/usr/bin/env python3
"""Diagnostica shape/memoria per il runner BioAnalyst native.

Lo script non sostituisce il forecast: prepara lo stesso batch, stampa le
dimensioni reali dei gruppi e, solo se richiesto, prova il forward CUDA.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch

from bioanalyst_model_utils import build_local_config, build_selection_parser, ensure_bfm_repo_on_path
from bioanalyst_native_utils import (
    NATIVE_GROUP_FIELDS,
    build_native_run_context,
    build_native_runtime,
    ensure_batched_batch,
    prepare_native_forecast_environment,
    prepare_native_saved_windows,
)


RAW_GROUP_FIELDS = {
    "surface": "surface_variables",
    "edaphic": "edaphic_variables",
    "atmospheric": "atmospheric_variables",
    "climate": "climate_variables",
    "species": "species_variables",
    "vegetation": "vegetation_variables",
    "land": "land_variables",
    "agriculture": "agriculture_variables",
    "forest": "forest_variables",
    "redlist": "redlist_variables",
    "misc": "misc_variables",
}


def build_parser():
    parser = build_selection_parser("Debug shape e memoria CUDA per BioAnalyst native.")
    parser.add_argument("--checkpoint", choices=["small", "large"], default="small")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cuda")
    parser.add_argument(
        "--fast-smoke-test",
        action="store_true",
        help="Usa placeholder a zero per il blocco atmosferico, come nel runner one-step.",
    )
    parser.add_argument(
        "--move-to-device",
        action="store_true",
        help="Sposta il batch scalato sul device scelto, senza eseguire il forward.",
    )
    parser.add_argument(
        "--run-forward",
        action="store_true",
        help="Esegue anche model(...). Puo andare in OOM: usare solo dopo aver letto le shape.",
    )
    parser.add_argument(
        "--amp-bf16",
        action="store_true",
        help="Durante il forward CUDA usa autocast bf16 per ridurre memoria.",
    )
    parser.add_argument(
        "--limit-vars",
        type=int,
        default=8,
        help="Numero massimo di variabili mostrate per gruppo.",
    )
    return parser


def tensor_info(value: Any) -> dict[str, Any]:
    if not isinstance(value, torch.Tensor):
        return {"type": type(value).__name__}
    return {
        "shape": list(value.shape),
        "dtype": str(value.dtype),
        "device": str(value.device),
        "numel": int(value.numel()),
        "size_mb": round(value.numel() * value.element_size() / 1024 / 1024, 3),
    }


def summarize_group(group: dict[str, Any], limit: int) -> dict[str, Any]:
    names = sorted(group)
    shown = names[:limit]
    return {
        "variable_count": len(names),
        "shown_variables": shown,
        "variables": {name: tensor_info(group[name]) for name in shown},
    }


def summarize_raw_batch(raw_batch: dict[str, Any], limit: int) -> dict[str, Any]:
    summary = {
        "metadata": {
            "timestamps": raw_batch.get("batch_metadata", {}).get("timestamp"),
            "lat_count": len(raw_batch.get("batch_metadata", {}).get("latitudes", [])),
            "lon_count": len(raw_batch.get("batch_metadata", {}).get("longitudes", [])),
        },
        "groups": {},
    }
    for group_name, field_name in RAW_GROUP_FIELDS.items():
        summary["groups"][group_name] = summarize_group(raw_batch.get(field_name, {}), limit)
    return summary


def summarize_batch(batch: Any, limit: int) -> dict[str, Any]:
    metadata = batch.batch_metadata
    summary = {
        "metadata": {
            "timestamps": metadata.timestamp,
            "latitudes": tensor_info(metadata.latitudes),
            "longitudes": tensor_info(metadata.longitudes),
        },
        "groups": {},
    }
    for group_name, field_name in NATIVE_GROUP_FIELDS.items():
        summary["groups"][group_name] = summarize_group(getattr(batch, field_name), limit)
    return summary


def print_group_summary(title: str, summary: dict[str, Any]) -> None:
    print(f"\n=== {title} ===", flush=True)
    print(json.dumps(summary["metadata"], indent=2, ensure_ascii=False), flush=True)
    for group_name, group_summary in summary["groups"].items():
        print(f"\n[{group_name}] variabili: {group_summary['variable_count']}", flush=True)
        for variable_name, info in group_summary["variables"].items():
            print(f"  - {variable_name}: {info}", flush=True)


def print_cuda_memory(label: str) -> None:
    if not torch.cuda.is_available():
        return
    torch.cuda.synchronize()
    allocated = torch.cuda.memory_allocated() / 1024 / 1024
    reserved = torch.cuda.memory_reserved() / 1024 / 1024
    max_allocated = torch.cuda.max_memory_allocated() / 1024 / 1024
    print(
        f"[cuda-memory] {label}: allocated={allocated:.1f} MB, "
        f"reserved={reserved:.1f} MB, peak={max_allocated:.1f} MB",
        flush=True,
    )


def load_scaled_input_without_model(saved_windows: dict[str, Path], cfg: Any):
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.dataloader_monthly import LargeClimateDataset, batch_to_device

    dataset = LargeClimateDataset(
        data_dir=str(saved_windows["input_window"].parent),
        scaling_settings=cfg.data.scaling,
        num_species=cfg.data.species_number,
        atmos_levels=cfg.data.atmos_levels,
        model_patch_size=cfg.model.patch_size,
    )
    scaled_batch = ensure_batched_batch(dataset.load_and_process_files(str(saved_windows["input_window"])))
    return dataset, scaled_batch, batch_to_device


def main() -> None:
    args = build_parser().parse_args()
    env = prepare_native_forecast_environment()
    context = build_native_run_context(
        args=args,
        project_output_dir=env["project_output_dir"],
        model_dir=env["model_dir"],
        run_suffix="native_shape_debug",
    )

    print(f"[1/5] Debug run: {context.label} -> {context.run_dir}", flush=True)
    saved_windows = prepare_native_saved_windows(
        context=context,
        source_paths=env["source_paths"],
        compare_month=None,
        use_atmospheric_data=not args.fast_smoke_test,
    )

    raw_batch = torch.load(saved_windows["input_window"], map_location="cpu", weights_only=False)
    raw_summary = summarize_raw_batch(raw_batch, args.limit_vars)
    print_group_summary("RAW BATCH SALVATO", raw_summary)

    cfg = build_local_config(
        batch_dir=context.batch_dir,
        checkpoint_path=context.checkpoint_path,
        device_name=str(context.device),
    )
    _dataset, scaled_batch, batch_to_device = load_scaled_input_without_model(saved_windows, cfg)
    scaled_batch = ensure_batched_batch(scaled_batch)
    scaled_summary = summarize_batch(scaled_batch, args.limit_vars)
    print_group_summary("SCALED BATCH DOPO DATALOADER", scaled_summary)

    moved_summary = None
    if args.move_to_device or args.run_forward:
        print_cuda_memory("prima batch_to_device")
        scaled_batch = batch_to_device(scaled_batch, context.device)
        print_cuda_memory("dopo batch_to_device")
        moved_summary = summarize_batch(scaled_batch, args.limit_vars)
        print_group_summary(f"BATCH SU {context.device}", moved_summary)

    forward_summary = None
    if args.run_forward:
        print("\n[forward] carico modello e provo model(...)", flush=True)
        runtime = build_native_runtime(
            batch_dir=context.batch_dir,
            checkpoint_path=context.checkpoint_path,
            device=context.device,
        )
        print_cuda_memory("dopo caricamento modello")
        try:
            with torch.inference_mode():
                autocast_enabled = bool(args.amp_bf16 and context.device.type == "cuda")
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=autocast_enabled):
                    predictions = runtime.model(scaled_batch, runtime.model.lead_time, batch_size=1)
            print_cuda_memory("dopo forward")
            forward_summary = {
                name: tensor_info(value)
                for name, value in sorted(predictions.items())
                if isinstance(value, torch.Tensor)
            }
            print("\n=== PREDICTION DICT ===", flush=True)
            print(json.dumps(forward_summary, indent=2, ensure_ascii=False), flush=True)
        except RuntimeError as exc:
            print_cuda_memory("dopo errore forward")
            print("\n[forward-error]", flush=True)
            print(str(exc), flush=True)
            raise

    output = {
        "label": context.label,
        "device": str(context.device),
        "checkpoint": str(context.checkpoint_path),
        "fast_smoke_test": bool(args.fast_smoke_test),
        "raw_batch": raw_summary,
        "scaled_batch": scaled_summary,
        "moved_batch": moved_summary,
        "forward_prediction": forward_summary,
    }
    output_path = context.run_dir / "native_shape_debug_summary.json"
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[done] Summary salvato in: {output_path}", flush=True)


if __name__ == "__main__":
    main()
