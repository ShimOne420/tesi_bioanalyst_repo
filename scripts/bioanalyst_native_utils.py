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
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from bioanalyst_model_utils import (
    BFM_REPO_ROOT,
    PROJECT_ROOT,
    build_native_group_source_status,
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
    input_mode: str
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


NATIVE_GROUP_FIELDS = {
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


DISPLAY_UNIT_RULES = {
    "t2m": ("°C", lambda values: values - 273.15),
    "tp": ("mm", lambda values: values * 1000.0),
}


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
    input_mode = getattr(args, "input_mode", "all")
    run_label = f"{slugify(label)}_{args.checkpoint}_{input_mode}_{months_info['end_month'].strftime('%Y_%m')}_{run_suffix}"
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
        input_mode=input_mode,
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
        input_mode=context.input_mode,
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
    use_amp_bf16: bool = False,
) -> NativeOneStepResult:
    """Esegue un forecast one-step e restituisce solo output nativi del modello."""
    dataset, x_batch_scaled = load_native_scaled_input(saved_windows, runtime)

    with torch.inference_mode():
        x_batch_device = runtime.batch_to_device(x_batch_scaled, context.device)
        autocast_enabled = bool(use_amp_bf16 and context.device.type == "cuda")
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=autocast_enabled):
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
    use_amp_bf16: bool = False,
) -> NativeRolloutResult:
    """Esegue un rollout multi-step del runner nativo e restituisce solo batch nativi."""
    dataset, initial_batch_scaled = load_native_scaled_input(saved_windows, runtime)

    with torch.inference_mode():
        curr = runtime.batch_to_device(initial_batch_scaled, context.device)
        rollout_batches_scaled = []
        for rollout_step in range(steps):
            autocast_enabled = bool(use_amp_bf16 and context.device.type == "cuda")
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=autocast_enabled):
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
        "input_mode": context.input_mode,
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
        "group_source_status": build_native_group_source_status(
            use_atmospheric_data=bool(result.saved_windows.get("atmospheric_data_real", True)),
            input_mode=context.input_mode,
        ),
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
        "input_mode": context.input_mode,
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
        "group_source_status": build_native_group_source_status(
            use_atmospheric_data=bool(result.saved_windows.get("atmospheric_data_real", True)),
            input_mode=context.input_mode,
        ),
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


def load_native_manifest(run_dir: Path) -> dict[str, Any]:
    """Legge il manifest JSON di un run native."""
    manifest_path = run_dir / "forecast_native_manifest.json"
    if not manifest_path.exists():
        raise SystemExit(f"Manifest non trovato: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def load_native_batch_artifact(path: Path):
    """Carica un batch salvato, supportando sia raw dict sia Batch già convertiti."""
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(payload, dict):
        payload = raw_dict_to_batch(payload)
    return ensure_batched_batch(payload)


def flatten_batch_timestamps(batch) -> list[str]:
    """Rende leggibili i timestamp del batch anche quando sono nested list."""
    def flatten(value) -> list[str]:
        if isinstance(value, (list, tuple)):
            flattened = []
            for item in value:
                flattened.extend(flatten(item))
            return flattened
        return [str(value)]

    return flatten(batch.batch_metadata.timestamp)


def batch_lead_time_value(batch) -> float:
    """Converte `lead_time` in float semplice per log e report."""
    lead_time = batch.batch_metadata.lead_time
    if hasattr(lead_time, "item"):
        return float(lead_time.item())
    return float(lead_time)


def get_native_group(batch, group_name: str) -> dict[str, torch.Tensor]:
    """Restituisce il gruppo richiesto dal batch con un nome semplice."""
    field_name = NATIVE_GROUP_FIELDS[group_name]
    return getattr(batch, field_name)


def list_native_group_variables(batch) -> dict[str, list[str]]:
    """Elenca i nomi delle variabili presenti in ciascun gruppo nativo."""
    return {
        group_name: sorted(get_native_group(batch, group_name).keys())
        for group_name in NATIVE_GROUP_FIELDS
        if len(get_native_group(batch, group_name)) > 0
    }


def list_native_group_counts(batch) -> dict[str, int]:
    """Conta quante variabili sono presenti in ciascun gruppo nativo."""
    return {
        group_name: len(get_native_group(batch, group_name))
        for group_name in NATIVE_GROUP_FIELDS
        if len(get_native_group(batch, group_name)) > 0
    }


def extract_native_map(tensor: torch.Tensor, *, level_index: int = 0) -> np.ndarray:
    """Estrae una mappa 2D leggibile dall'ultimo timestep disponibile."""
    values = tensor.detach().cpu().numpy()
    if values.ndim == 2:
        return values.astype(np.float32)
    if values.ndim == 3:
        return values[-1].astype(np.float32)
    if values.ndim == 4:
        reduced = values[0] if values.shape[0] == 1 else values[-1]
        if reduced.ndim == 3:
            return reduced[-1].astype(np.float32)
        return reduced.astype(np.float32)
    if values.ndim == 5:
        return values[0, -1, level_index].astype(np.float32)
    raise SystemExit(f"Shape non supportata per una mappa 2D: {values.shape}")


def convert_display_values(variable_name: str, values: np.ndarray) -> tuple[np.ndarray, str]:
    """Converte alcune variabili note in unita più leggibili per grafici e report."""
    if variable_name in DISPLAY_UNIT_RULES:
        unit, rule = DISPLAY_UNIT_RULES[variable_name]
        return rule(values.astype(np.float32)), unit
    return values.astype(np.float32), "native"


def native_pct_error(predicted: float, observed: float) -> float:
    """Calcola una percentuale robusta per riepiloghi predicted vs observed."""
    if abs(observed) < 1e-12:
        return 0.0 if abs(predicted) < 1e-12 else 100.0
    return abs(predicted - observed) / abs(observed) * 100.0


def native_temperature_pct_error_kelvin(predicted_c: float, observed_c: float) -> float:
    """Percentuale di errore della temperatura in Kelvin per evitare instabilita vicino a 0°C."""
    return native_pct_error(predicted_c + 273.15, observed_c + 273.15)


def resolve_native_area_masks(batch, *, bounds: dict[str, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Costruisce le maschere lat/lon della zona di interesse nella griglia nativa."""
    latitudes = np.asarray(batch.batch_metadata.latitudes, dtype=np.float32)
    longitudes = np.asarray(batch.batch_metadata.longitudes, dtype=np.float32)
    if latitudes.ndim > 1:
        latitudes = latitudes[0]
    if longitudes.ndim > 1:
        longitudes = longitudes[0]

    if bounds:
        lat_mask = (latitudes >= bounds["min_lat"]) & (latitudes <= bounds["max_lat"])
        lon_mask = (longitudes >= bounds["min_lon"]) & (longitudes <= bounds["max_lon"])
    else:
        lat_mask = np.ones_like(latitudes, dtype=bool)
        lon_mask = np.ones_like(longitudes, dtype=bool)

    if not lat_mask.any() or not lon_mask.any():
        raise SystemExit("L'area selezionata non interseca la griglia del modello.")

    return lat_mask, lon_mask


def subset_native_variable_map(
    batch,
    *,
    group_name: str,
    variable_name: str,
    bounds: dict[str, float] | None = None,
) -> tuple[np.ndarray, str]:
    """Estrae la mappa di una variabile nativa e la ritaglia sulla zona di interesse."""
    group = get_native_group(batch, group_name)
    if variable_name not in group:
        available = ", ".join(sorted(group.keys())[:12])
        raise SystemExit(
            f"Variabile `{variable_name}` non trovata nel gruppo `{group_name}`. "
            f"Prime variabili disponibili: {available}"
        )

    raw_map = extract_native_map(group[variable_name])
    display_map, unit = convert_display_values(variable_name, raw_map)
    lat_mask, lon_mask = resolve_native_area_masks(batch, bounds=bounds)
    return display_map[lat_mask][:, lon_mask], unit


def compute_native_variable_comparison(
    predicted_batch,
    observed_batch,
    *,
    group_name: str,
    variable_name: str,
    bounds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Confronta una singola variabile nativa tra prediction e observed."""
    predicted_values, unit = subset_native_variable_map(
        predicted_batch,
        group_name=group_name,
        variable_name=variable_name,
        bounds=bounds,
    )
    observed_values, _ = subset_native_variable_map(
        observed_batch,
        group_name=group_name,
        variable_name=variable_name,
        bounds=bounds,
    )
    delta = predicted_values - observed_values

    predicted_mean = float(np.nanmean(predicted_values))
    observed_mean = float(np.nanmean(observed_values))
    if variable_name == "t2m":
        error_pct = native_temperature_pct_error_kelvin(predicted_mean, observed_mean)
    else:
        error_pct = native_pct_error(predicted_mean, observed_mean)

    return {
        "group": group_name,
        "variable": variable_name,
        "unit": unit,
        "predicted_mean": predicted_mean,
        "observed_mean": observed_mean,
        "bias": float(predicted_mean - observed_mean),
        "mae": float(np.nanmean(np.abs(delta))),
        "rmse": float(np.sqrt(np.nanmean(np.square(delta)))),
        "error_pct": float(error_pct),
    }


def compute_native_group_comparison(
    predicted_batch,
    observed_batch,
    *,
    group_name: str,
    bounds: dict[str, float] | None = None,
    top_n: int = 5,
) -> dict[str, Any]:
    """Confronta tutte le variabili di un gruppo nativo e ne produce un riepilogo."""
    predicted_group = get_native_group(predicted_batch, group_name)
    observed_group = get_native_group(observed_batch, group_name)
    shared_variables = sorted(set(predicted_group).intersection(observed_group))
    if not shared_variables:
        raise SystemExit(f"Nessuna variabile condivisa trovata nel gruppo `{group_name}`.")

    rows = [
        compute_native_variable_comparison(
            predicted_batch,
            observed_batch,
            group_name=group_name,
            variable_name=variable_name,
            bounds=bounds,
        )
        for variable_name in shared_variables
    ]
    ordered_by_mae = sorted(rows, key=lambda row: row["mae"], reverse=True)
    return {
        "group": group_name,
        "variable_count": len(rows),
        "mean_predicted": float(np.mean([row["predicted_mean"] for row in rows])),
        "mean_observed": float(np.mean([row["observed_mean"] for row in rows])),
        "mean_bias": float(np.mean([row["bias"] for row in rows])),
        "mean_mae": float(np.mean([row["mae"] for row in rows])),
        "mean_rmse": float(np.mean([row["rmse"] for row in rows])),
        "mean_error_pct": float(np.mean([row["error_pct"] for row in rows])),
        "top_variables_by_mae": ordered_by_mae[:top_n],
    }


def resolve_native_batch_path(manifest: dict[str, Any], *, batch_kind: str, rollout_step: int | None = None) -> Path:
    """Risolviamo il file `.pt` corretto partendo dal manifest del run."""
    if batch_kind == "prediction":
        path = manifest.get("native_prediction_original")
    elif batch_kind == "observed":
        path = manifest.get("native_target_original")
    elif batch_kind == "rollout":
        rollout_paths = manifest.get("native_rollout_batches", [])
        if not rollout_paths:
            raise SystemExit("Nel manifest non ci sono rollout batch.")
        if rollout_step is None:
            rollout_step = len(rollout_paths)
        if rollout_step < 1 or rollout_step > len(rollout_paths):
            raise SystemExit(f"`--rollout-step` fuori range: {rollout_step}")
        path = rollout_paths[rollout_step - 1]
    else:
        raise SystemExit(f"Tipo batch non supportato: {batch_kind}")

    if not path:
        raise SystemExit(f"Batch `{batch_kind}` non disponibile in questo run.")
    return Path(path)


def summarize_native_batch(batch, *, group_name: str | None = None, variable_name: str | None = None) -> dict[str, Any]:
    """Produce un riepilogo leggero del batch nativo e, se richiesto, di una variabile specifica."""
    latitudes = np.asarray(batch.batch_metadata.latitudes, dtype=np.float32)
    longitudes = np.asarray(batch.batch_metadata.longitudes, dtype=np.float32)
    if latitudes.ndim > 1:
        latitudes = latitudes[0]
    if longitudes.ndim > 1:
        longitudes = longitudes[0]

    summary: dict[str, Any] = {
        "timestamps": flatten_batch_timestamps(batch),
        "lead_time": batch_lead_time_value(batch),
        "grid_shape": [int(latitudes.size), int(longitudes.size)],
        "latitude_range": [float(latitudes.min()), float(latitudes.max())],
        "longitude_range": [float(longitudes.min()), float(longitudes.max())],
        "group_counts": list_native_group_counts(batch),
        "group_variables": list_native_group_variables(batch),
    }

    if group_name and variable_name:
        group = get_native_group(batch, group_name)
        if variable_name not in group:
            raise SystemExit(f"Variabile `{variable_name}` non trovata nel gruppo `{group_name}`.")
        raw_map = extract_native_map(group[variable_name])
        display_map, unit = convert_display_values(variable_name, raw_map)
        summary["variable_summary"] = {
            "group": group_name,
            "variable": variable_name,
            "unit": unit,
            "min": float(np.nanmin(display_map)),
            "max": float(np.nanmax(display_map)),
            "mean": float(np.nanmean(display_map)),
            "std": float(np.nanstd(display_map)),
        }

    return summary


def compute_native_climate_comparison(
    predicted_batch,
    observed_batch,
    *,
    bounds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Confronta prediction e observed su `t2m` e `tp` nello spazio nativo del modello."""
    lat_mask, lon_mask = resolve_native_area_masks(predicted_batch, bounds=bounds)

    return {
        "cell_count": int(lat_mask.sum() * lon_mask.sum()),
        "temperature_c": compute_native_variable_comparison(
            predicted_batch,
            observed_batch,
            group_name="climate",
            variable_name="t2m",
            bounds=bounds,
        ),
        "precipitation_mm": compute_native_variable_comparison(
            predicted_batch,
            observed_batch,
            group_name="climate",
            variable_name="tp",
            bounds=bounds,
        ),
    }


def normalize_native_timestamp_to_month(value: str | None) -> str | None:
    """Normalizza un timestamp qualsiasi al formato `YYYY-MM-DD` del primo giorno del mese."""
    if value is None:
        return None
    return str(pd.Timestamp(value).to_period("M").to_timestamp().date())


def evaluate_native_run_sanity(
    manifest: dict[str, Any],
    predicted_batch,
    observed_batch,
) -> dict[str, Any]:
    """Controlla che prediction e observed siano coerenti con il contratto del run native."""
    prediction_path = manifest.get("native_prediction_original")
    observed_path = manifest.get("native_target_original")
    predicted_timestamps = flatten_batch_timestamps(predicted_batch)
    observed_timestamps = flatten_batch_timestamps(observed_batch) if observed_batch is not None else []
    expected_forecast_month = normalize_native_timestamp_to_month(manifest.get("forecast_month"))
    expected_input_last_month = normalize_native_timestamp_to_month(
        manifest.get("input_months", [None, None])[-1] if manifest.get("input_months") else None
    )

    predicted_last_month = normalize_native_timestamp_to_month(predicted_timestamps[-1]) if predicted_timestamps else None
    observed_last_month = normalize_native_timestamp_to_month(observed_timestamps[-1]) if observed_timestamps else None
    observed_previous_month = normalize_native_timestamp_to_month(observed_timestamps[-2]) if len(observed_timestamps) >= 2 else None

    temperature_comparison = compute_native_variable_comparison(
        predicted_batch,
        observed_batch,
        group_name="climate",
        variable_name="t2m",
        bounds=manifest.get("bounds"),
    )
    precipitation_comparison = compute_native_variable_comparison(
        predicted_batch,
        observed_batch,
        group_name="climate",
        variable_name="tp",
        bounds=manifest.get("bounds"),
    )

    paths_differ = bool(prediction_path and observed_path and Path(prediction_path) != Path(observed_path))
    predicted_forecast_month_ok = predicted_last_month == expected_forecast_month
    observed_forecast_month_ok = observed_last_month == expected_forecast_month
    observed_input_alignment_ok = observed_previous_month == expected_input_last_month
    lead_time_match = batch_lead_time_value(predicted_batch) == batch_lead_time_value(observed_batch)
    identical_area_maps = (
        abs(temperature_comparison["mae"]) < 1e-8 and abs(precipitation_comparison["mae"]) < 1e-8
    )

    return {
        "prediction_path": prediction_path,
        "observed_path": observed_path,
        "paths_differ": paths_differ,
        "predicted_timestamps": predicted_timestamps,
        "observed_timestamps": observed_timestamps,
        "expected_input_last_month": expected_input_last_month,
        "expected_forecast_month": expected_forecast_month,
        "predicted_last_month": predicted_last_month,
        "observed_previous_month": observed_previous_month,
        "observed_last_month": observed_last_month,
        "predicted_forecast_month_ok": predicted_forecast_month_ok,
        "observed_forecast_month_ok": observed_forecast_month_ok,
        "observed_input_alignment_ok": observed_input_alignment_ok,
        "lead_time_prediction": batch_lead_time_value(predicted_batch),
        "lead_time_observed": batch_lead_time_value(observed_batch),
        "lead_time_match": lead_time_match,
        "identical_area_maps_flag": identical_area_maps,
        "sanity_pass": all(
            [
                paths_differ,
                predicted_forecast_month_ok,
                observed_forecast_month_ok,
                observed_input_alignment_ok,
                lead_time_match,
            ]
        ),
    }
