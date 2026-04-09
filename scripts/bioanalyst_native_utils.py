#!/usr/bin/env python3
"""Utility del ramo `forecast-bioanalyst-native`.

Questo modulo implementa solo il livello `native-first`:

- preparazione dei batch nel formato atteso da BioAnalyst;
- bootstrap del runner ufficiale `bfm-model`;
- esecuzione one-step e rollout;
- salvataggio degli output nativi del modello.

L'aggregazione BIOMAP viene tenuta fuori da qui e vive in uno strato separato.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import torch

from bioanalyst_model_utils import (
    BFM_REPO_ROOT,
    PROJECT_ROOT,
    build_local_config,
    ensure_bfm_repo_on_path,
    load_project_env,
    raw_dict_to_batch,
    require_path,
    resolve_checkpoint_path,
    resolve_forecast_months,
    resolve_forecast_output_dir,
    resolve_selection,
    resolve_source_paths,
    resolve_torch_device,
    rescale_batch_correct,
    save_window_batches,
    slugify,
    write_json,
)


@dataclass(slots=True)
class NativeRunContext:
    selection_mode: str
    bounds: dict[str, float]
    label: str
    months_info: dict[str, pd.Timestamp | bool]
    run_dir: Path
    batch_dir: Path
    checkpoint_path: Path
    checkpoint_kind: str
    device: torch.device
    project_output_dir: Path


@dataclass(slots=True)
class NativeRuntime:
    cfg: Any
    model: Any
    dataset_class: Any
    batch_to_device: Any
    build_new_batch_with_prediction: Any
    detach_batch: Any
    checkpoint_diagnostics: dict[str, Any]


@dataclass(slots=True)
class NativeOneStepResult:
    predicted_batch_original: Any
    observed_batch_original: Any | None
    checkpoint_diagnostics: dict[str, Any]
    saved_windows: dict[str, Path]
    forecast_month: pd.Timestamp


@dataclass(slots=True)
class NativeRolloutResult:
    rollout_batches_original: list[Any]
    checkpoint_diagnostics: dict[str, Any]
    saved_windows: dict[str, Path]
    forecast_months: list[pd.Timestamp]


def ensure_batched_batch(batch):
    """Uniforma metadata e gruppi tensori al formato batched atteso da `bfm-model`."""
    metadata = batch.batch_metadata
    latitudes = metadata.latitudes
    longitudes = metadata.longitudes
    timestamps = metadata.timestamp

    if hasattr(latitudes, "dim") and latitudes.dim() == 1:
        latitudes = latitudes.unsqueeze(0)
    if hasattr(longitudes, "dim") and longitudes.dim() == 1:
        longitudes = longitudes.unsqueeze(0)
    if isinstance(timestamps, list) and timestamps and isinstance(timestamps[0], str):
        timestamps = [timestamps]

    def add_batch_dim_to_group(group):
        updated = {}
        for name, tensor in group.items():
            if hasattr(tensor, "dim") and tensor.dim() in (3, 4):
                updated[name] = tensor.unsqueeze(0)
            else:
                updated[name] = tensor
        return updated

    return batch._replace(
        batch_metadata=metadata._replace(
            latitudes=latitudes,
            longitudes=longitudes,
            timestamp=timestamps,
        ),
        surface_variables=add_batch_dim_to_group(batch.surface_variables),
        edaphic_variables=add_batch_dim_to_group(batch.edaphic_variables),
        atmospheric_variables=add_batch_dim_to_group(batch.atmospheric_variables),
        climate_variables=add_batch_dim_to_group(batch.climate_variables),
        species_variables=add_batch_dim_to_group(batch.species_variables),
        vegetation_variables=add_batch_dim_to_group(batch.vegetation_variables),
        land_variables=add_batch_dim_to_group(batch.land_variables),
        agriculture_variables=add_batch_dim_to_group(batch.agriculture_variables),
        forest_variables=add_batch_dim_to_group(batch.forest_variables),
        redlist_variables=add_batch_dim_to_group(batch.redlist_variables),
        misc_variables=add_batch_dim_to_group(batch.misc_variables),
    )


def classify_incompatible_keys(incompatible, state_dict: dict[str, torch.Tensor]) -> dict[str, Any]:
    """Riassume missing/unexpected keys per rendere leggibile il checkpoint loading."""
    missing = list(incompatible.missing_keys)
    latent_alias_prefix = "encoder._latent_parameter_list."
    only_latent_aliases = bool(missing) and all(key.startswith(latent_alias_prefix) for key in missing)
    checkpoint_has_latent_named_params = any(key.startswith("encoder.") and key.endswith("_latents") for key in state_dict)
    return {
        "missing_keys_count": len(missing),
        "unexpected_keys_count": len(incompatible.unexpected_keys),
        "missing_keys_sample": missing[:10],
        "unexpected_keys_sample": list(incompatible.unexpected_keys[:10]),
        "only_latent_alias_missing_keys": only_latent_aliases,
        "checkpoint_has_named_latent_parameters": checkpoint_has_latent_named_params,
    }


def build_native_run_context(
    *,
    args,
    project_output_dir: Path,
    model_dir: Path,
    run_suffix: str,
) -> NativeRunContext:
    """Risolviamo area, periodo, checkpoint e cartelle di output del runner nativo."""
    selection_mode, bounds, label = resolve_selection(args)
    months_info = resolve_forecast_months(args.start, args.end)
    device = resolve_torch_device(args.device)
    checkpoint_path = resolve_checkpoint_path(model_dir, args.checkpoint)
    run_label = f"{slugify(label)}_{months_info['end_month'].strftime('%Y_%m')}_{run_suffix}"
    run_dir = resolve_forecast_output_dir(project_output_dir, run_label)
    batch_dir = run_dir / "batches"
    return NativeRunContext(
        selection_mode=selection_mode,
        bounds=bounds,
        label=label,
        months_info=months_info,
        run_dir=run_dir,
        batch_dir=batch_dir,
        checkpoint_path=checkpoint_path,
        checkpoint_kind=args.checkpoint,
        device=device,
        project_output_dir=project_output_dir,
    )


def prepare_native_saved_windows(
    *,
    context: NativeRunContext,
    source_paths: dict[str, Path],
    compare_month: pd.Timestamp | None,
    use_atmospheric_data: bool,
) -> dict[str, Path]:
    """Costruisce i batch `.pt` raw nel formato ufficiale del modello."""
    input_months = [
        context.months_info["input_prev"],
        context.months_info["input_last"],
    ]
    return save_window_batches(
        output_dir=context.batch_dir,
        input_months=input_months,
        compare_month=compare_month,
        source_paths=source_paths,
        use_atmospheric_data=use_atmospheric_data,
    )


def build_native_runtime(*, batch_dir: Path, checkpoint_path: Path, device: torch.device) -> NativeRuntime:
    """Carica config, dataloader e modello ufficiale per il runner native-first."""
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.batch_utils import build_new_batch_with_prediction
    from bfm_model.bfm.dataloader_monthly import LargeClimateDataset, batch_to_device, detach_batch
    from bfm_model.bfm.model_helpers import setup_bfm_model
    from safetensors.torch import load_file

    cfg = build_local_config(batch_dir=batch_dir, checkpoint_path=checkpoint_path, device_name=str(device))
    model = setup_bfm_model(cfg, mode="test")
    state_dict = load_file(str(checkpoint_path))
    incompatible = model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    torch.set_float32_matmul_precision(cfg.training.precision_in)

    return NativeRuntime(
        cfg=cfg,
        model=model,
        dataset_class=LargeClimateDataset,
        batch_to_device=batch_to_device,
        build_new_batch_with_prediction=build_new_batch_with_prediction,
        detach_batch=detach_batch,
        checkpoint_diagnostics=classify_incompatible_keys(incompatible, state_dict),
    )


def load_native_scaled_input(saved_windows: dict[str, Path], runtime: NativeRuntime):
    """Carica il batch input tramite il dataloader ufficiale di BioAnalyst."""
    dataset = runtime.dataset_class(
        data_dir=str(saved_windows["input_window"].parent),
        scaling_settings=runtime.cfg.data.scaling,
        num_species=runtime.cfg.data.species_number,
        atmos_levels=runtime.cfg.data.atmos_levels,
        model_patch_size=runtime.cfg.model.patch_size,
    )
    x_batch_scaled = ensure_batched_batch(dataset.load_and_process_files(str(saved_windows["input_window"])))
    return dataset, x_batch_scaled


def load_raw_observed_target(target_window: Path):
    """Legge il target osservato raw e lo converte nel Batch usato dal modello."""
    raw_target = torch.load(target_window, map_location="cpu", weights_only=False)
    return ensure_batched_batch(raw_dict_to_batch(raw_target))


def extract_forecast_month(batch) -> pd.Timestamp:
    """Estrae il timestamp finale di un batch predetto."""
    timestamp_value = batch.batch_metadata.timestamp
    while isinstance(timestamp_value, (list, tuple)):
        timestamp_value = timestamp_value[-1]
    return pd.Timestamp(str(timestamp_value))


def run_native_one_step(
    *,
    context: NativeRunContext,
    runtime: NativeRuntime,
    saved_windows: dict[str, Path],
) -> NativeOneStepResult:
    """Esegue un forecast one-step e restituisce solo output nativi del modello."""
    dataset, x_batch_scaled = load_native_scaled_input(saved_windows, runtime)

    with torch.inference_mode():
        x_batch_device = runtime.batch_to_device(x_batch_scaled, context.device)
        predicted_dict_scaled = runtime.model(x_batch_device, runtime.model.lead_time, batch_size=1)
        predicted_batch_scaled = runtime.build_new_batch_with_prediction(x_batch_device, predicted_dict_scaled, months=1)

    predicted_batch_original = rescale_batch_correct(
        runtime.detach_batch(predicted_batch_scaled),
        scaling_statistics=dataset.scaling_statistics,
        mode=runtime.cfg.data.scaling.mode,
        direction="original",
    )

    observed_batch_original = None
    if "target_window" in saved_windows:
        observed_batch_original = load_raw_observed_target(saved_windows["target_window"])

    return NativeOneStepResult(
        predicted_batch_original=predicted_batch_original,
        observed_batch_original=observed_batch_original,
        checkpoint_diagnostics=runtime.checkpoint_diagnostics,
        saved_windows=saved_windows,
        forecast_month=extract_forecast_month(predicted_batch_original),
    )


def run_native_rollout(
    *,
    context: NativeRunContext,
    runtime: NativeRuntime,
    saved_windows: dict[str, Path],
    steps: int,
) -> NativeRolloutResult:
    """Esegue un rollout multi-step del runner nativo e restituisce solo batch nativi."""
    dataset, initial_batch_scaled = load_native_scaled_input(saved_windows, runtime)

    with torch.inference_mode():
        curr = runtime.batch_to_device(initial_batch_scaled, context.device)
        rollout_batches_scaled = []
        for rollout_step in range(steps):
            preds = runtime.model(curr, runtime.model.lead_time, batch_size=1, rollout_step=rollout_step)
            next_batch = runtime.build_new_batch_with_prediction(curr, preds)
            rollout_batches_scaled.append(next_batch)
            curr = next_batch

    rollout_batches_original = [
        rescale_batch_correct(
            runtime.detach_batch(batch),
            scaling_statistics=dataset.scaling_statistics,
            mode=runtime.cfg.data.scaling.mode,
            direction="original",
        )
        for batch in rollout_batches_scaled
    ]
    forecast_months = [extract_forecast_month(batch) for batch in rollout_batches_original]

    return NativeRolloutResult(
        rollout_batches_original=rollout_batches_original,
        checkpoint_diagnostics=runtime.checkpoint_diagnostics,
        saved_windows=saved_windows,
        forecast_months=forecast_months,
    )


def save_native_one_step_artifacts(
    *,
    context: NativeRunContext,
    runtime: NativeRuntime,
    result: NativeOneStepResult,
) -> dict[str, Path]:
    """Salva i batch nativi one-step e il manifest del run."""
    predicted_path = context.run_dir / "native_prediction_original.pt"
    torch.save(result.predicted_batch_original, predicted_path)

    observed_path = None
    if result.observed_batch_original is not None:
        observed_path = context.run_dir / "native_target_original.pt"
        torch.save(result.observed_batch_original, observed_path)

    manifest = {
        "mode": "bioanalyst_native_one_step",
        "label": context.label,
        "selection_mode": context.selection_mode,
        "bounds": context.bounds,
        "checkpoint": str(context.checkpoint_path),
        "checkpoint_kind": context.checkpoint_kind,
        "device": str(context.device),
        "input_months": [
            str(context.months_info["input_prev"].date()),
            str(context.months_info["input_last"].date()),
        ],
        "forecast_month": str(result.forecast_month.date()),
        "raw_batch_input": str(result.saved_windows["input_window"]),
        "raw_batch_target": str(result.saved_windows["target_window"]) if "target_window" in result.saved_windows else None,
        "native_prediction_original": str(predicted_path),
        "native_target_original": str(observed_path) if observed_path else None,
        "checkpoint_diagnostics": runtime.checkpoint_diagnostics,
    }
    write_json(context.run_dir / "forecast_native_manifest.json", manifest)
    return {
        "manifest": context.run_dir / "forecast_native_manifest.json",
        "prediction": predicted_path,
        "observed": observed_path,
    }


def save_native_rollout_artifacts(
    *,
    context: NativeRunContext,
    runtime: NativeRuntime,
    result: NativeRolloutResult,
) -> dict[str, Path]:
    """Salva i batch nativi rollout e il manifest del run."""
    batches_dir = context.run_dir / "native_rollout_batches"
    batches_dir.mkdir(parents=True, exist_ok=True)

    batch_paths = []
    for step_index, batch in enumerate(result.rollout_batches_original, start=1):
        batch_path = batches_dir / f"step_{step_index:02d}.pt"
        torch.save(batch, batch_path)
        batch_paths.append(batch_path)

    manifest = {
        "mode": "bioanalyst_native_rollout",
        "label": context.label,
        "selection_mode": context.selection_mode,
        "bounds": context.bounds,
        "checkpoint": str(context.checkpoint_path),
        "checkpoint_kind": context.checkpoint_kind,
        "device": str(context.device),
        "input_months": [
            str(context.months_info["input_prev"].date()),
            str(context.months_info["input_last"].date()),
        ],
        "forecast_months": [str(month.date()) for month in result.forecast_months],
        "raw_batch_input": str(result.saved_windows["input_window"]),
        "raw_batch_target": str(result.saved_windows["target_window"]) if "target_window" in result.saved_windows else None,
        "native_rollout_batches": [str(path) for path in batch_paths],
        "checkpoint_diagnostics": runtime.checkpoint_diagnostics,
    }
    write_json(context.run_dir / "forecast_native_manifest.json", manifest)
    return {
        "manifest": context.run_dir / "forecast_native_manifest.json",
        "batches_dir": batches_dir,
    }


def prepare_native_forecast_environment():
    """Carica `.env` e restituisce i path base del progetto forecast."""
    load_project_env()
    biocube_dir = require_path("BIOCUBE_DIR")
    model_dir = require_path("BIOANALYST_MODEL_DIR")
    project_output_dir = require_path("PROJECT_OUTPUT_DIR", create=True)
    source_paths = resolve_source_paths(biocube_dir)
    return {
        "biocube_dir": biocube_dir,
        "model_dir": model_dir,
        "project_output_dir": project_output_dir,
        "source_paths": source_paths,
        "project_root": PROJECT_ROOT,
        "bfm_repo_root": BFM_REPO_ROOT,
    }
