#!/usr/bin/env python3
"""Esegue un backtesting one-step del forecast BioAnalyst su una o più città.

Questo script serve per la fase 5 della roadmap:

- verifica che il roundtrip raw -> scaled -> original sia coerente;
- chiarisce il significato dei `missing_keys` del checkpoint;
- esegue forecast one-step su casi reali;
- salva un report tabellare con errori e note diagnostiche.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import torch
from omegaconf import OmegaConf

from bioanalyst_model_utils import (
    build_bfm_model_from_cfg,
    build_local_config,
    ensure_bfm_repo_on_path,
    load_project_env,
    raw_dict_to_batch,
    require_path,
    resolve_checkpoint_path,
    resolve_forecast_output_dir,
    resolve_forecast_months,
    resolve_selection,
    resolve_source_paths,
    resolve_torch_device,
    rescale_batch_correct,
    save_window_batches,
    slugify,
    summarize_batch_for_area,
    write_forecast_tables,
    write_json,
)
from forecast_area_indicators import ensure_batched_batch


# Definiamo una CLI piccola e orientata al backtesting su una o più città.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backtesting one-step BioAnalyst su città europee.")
    parser.add_argument(
        "--cities",
        nargs="+",
        default=["milano", "madrid"],
        help="Lista di città su cui eseguire il backtesting.",
    )
    parser.add_argument("--start", default="2019-01-01", help="Mese iniziale osservato.")
    parser.add_argument("--end", default="2019-12-01", help="Mese finale osservato.")
    parser.add_argument("--checkpoint", choices=["small", "large"], default="small")
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="cpu")
    parser.add_argument("--half-window-deg", type=float, default=0.5)
    parser.add_argument("--species-threshold", type=float, default=0.5)
    return parser


# Classifichiamo i missing keys per capire se sono un problema reale o un alias interno del modello.
def classify_missing_keys(incompatible, state_dict: dict[str, torch.Tensor]) -> dict[str, object]:
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


# Misuriamo quanto il nostro unscale corretto ricostruisce i valori raw del batch target.
def compute_roundtrip_metrics(raw_batch, corrected_batch, bounds: dict[str, float]) -> dict[str, float]:
    latitudes = corrected_batch.batch_metadata.latitudes.detach().cpu().numpy()
    longitudes = corrected_batch.batch_metadata.longitudes.detach().cpu().numpy()
    if latitudes.ndim > 1:
        latitudes = latitudes[0]
    if longitudes.ndim > 1:
        longitudes = longitudes[0]

    lat_mask = (latitudes >= bounds["min_lat"]) & (latitudes <= bounds["max_lat"])
    lon_mask = (longitudes >= bounds["min_lon"]) & (longitudes <= bounds["max_lon"])

    raw_t2m = raw_batch["climate_variables"]["t2m"][-1].detach().cpu().numpy()[lat_mask][:, lon_mask]
    raw_tp = raw_batch["climate_variables"]["tp"][-1].detach().cpu().numpy()[lat_mask][:, lon_mask]

    corrected_t2m = corrected_batch.climate_variables["t2m"].detach().cpu().numpy()[0, -1][lat_mask][:, lon_mask]
    corrected_tp = corrected_batch.climate_variables["tp"].detach().cpu().numpy()[0, -1][lat_mask][:, lon_mask]

    return {
        "roundtrip_t2m_mae_kelvin": float(abs(raw_t2m - corrected_t2m).mean()),
        "roundtrip_tp_mae_meters": float(abs(raw_tp - corrected_tp).mean()),
        "roundtrip_t2m_max_abs_kelvin": float(abs(raw_t2m - corrected_t2m).max()),
        "roundtrip_tp_max_abs_meters": float(abs(raw_tp - corrected_tp).max()),
    }


# Eseguiamo il backtest su una singola città e restituiamo un record pronto per il report finale.
def run_backtest_for_city(
    city: str,
    biocube_dir: Path,
    model_dir: Path,
    output_dir: Path,
    checkpoint: str,
    device: torch.device,
    species_threshold: float,
    start: str,
    end: str,
    half_window_deg: float,
) -> tuple[dict[str, object], dict[str, object]]:
    selection_mode, bounds, label = resolve_selection(
        SimpleNamespace(
            city=city,
            lat=None,
            lon=None,
            min_lat=None,
            max_lat=None,
            min_lon=None,
            max_lon=None,
            half_window_deg=half_window_deg,
            label=None,
        )
    )
    months_info = resolve_forecast_months(start, end)
    source_paths = resolve_source_paths(biocube_dir)

    # Costruiamo una cartella dedicata al caso di backtest e salviamo le finestre raw.
    run_label = f"{slugify(label)}_{months_info['end_month'].strftime('%Y_%m')}_phase5_backtest"
    run_dir = resolve_forecast_output_dir(output_dir, run_label)
    batch_dir = run_dir / "batches"
    saved_windows = save_window_batches(
        output_dir=batch_dir,
        input_months=[months_info["input_prev"], months_info["input_last"]],
        compare_month=months_info["forecast_month"],
        source_paths=source_paths,
        use_atmospheric_data=True,
    )

    # Prepariamo config, dataset scalato e batch input/target.
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.batch_utils import build_new_batch_with_prediction
    from bfm_model.bfm.dataloader_monthly import LargeClimateDataset, batch_to_device, detach_batch
    from safetensors.torch import load_file

    checkpoint_path = resolve_checkpoint_path(model_dir, checkpoint)
    cfg = build_local_config(batch_dir=batch_dir, checkpoint_path=checkpoint_path, device_name=str(device))
    dataset = LargeClimateDataset(
        data_dir=str(batch_dir),
        scaling_settings=cfg.data.scaling,
        num_species=cfg.data.species_number,
        atmos_levels=cfg.data.atmos_levels,
        model_patch_size=cfg.model.patch_size,
    )
    x_batch_scaled = ensure_batched_batch(dataset.load_and_process_files(str(saved_windows["input_window"])))
    y_batch_scaled = ensure_batched_batch(dataset.load_and_process_files(str(saved_windows["target_window"])))

    # Carichiamo il modello solo per questo caso e raccogliamo il significato dei missing keys.
    model = build_bfm_model_from_cfg(cfg)
    state_dict = load_file(str(checkpoint_path))
    incompatible = model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    torch.set_float32_matmul_precision(cfg.training.precision_in)

    # Eseguiamo il forward one-step e riportiamo forecast e target nello spazio originale corretto.
    with torch.inference_mode():
        x_batch_device = batch_to_device(x_batch_scaled, device)
        predicted_dict_scaled = model(x_batch_device, model.lead_time, batch_size=1)
        predicted_batch_scaled = build_new_batch_with_prediction(x_batch_device, predicted_dict_scaled, months=1)

    predicted_batch_original = rescale_batch_correct(
        detach_batch(predicted_batch_scaled),
        scaling_statistics=dataset.scaling_statistics,
        mode=cfg.data.scaling.mode,
        direction="original",
    )
    corrected_target_original = rescale_batch_correct(
        y_batch_scaled,
        scaling_statistics=dataset.scaling_statistics,
        mode=cfg.data.scaling.mode,
        direction="original",
    )

    # Per il confronto observed usiamo il raw target, che rappresenta il dato fisico di riferimento.
    raw_target = torch.load(saved_windows["target_window"], map_location="cpu", weights_only=False)
    raw_target_batch = ensure_batched_batch(raw_dict_to_batch(raw_target))

    predicted_summary = summarize_batch_for_area(predicted_batch_original, bounds, species_threshold=species_threshold)
    observed_summary = summarize_batch_for_area(raw_target_batch, bounds, species_threshold=species_threshold)
    roundtrip_metrics = compute_roundtrip_metrics(raw_target, corrected_target_original, bounds)
    key_diagnostics = classify_missing_keys(incompatible, state_dict)

    result = {
        "label": label,
        "selection_mode": selection_mode,
        "forecast_month": str(months_info["forecast_month"].date()),
        "temperature_mean_area_c_predicted": predicted_summary["temperature_mean_area_c"],
        "temperature_mean_area_c_observed": observed_summary["temperature_mean_area_c"],
        "temperature_abs_error_c": abs(predicted_summary["temperature_mean_area_c"] - observed_summary["temperature_mean_area_c"]),
        "precipitation_mean_area_mm_predicted": predicted_summary["precipitation_mean_area_mm"],
        "precipitation_mean_area_mm_observed": observed_summary["precipitation_mean_area_mm"],
        "precipitation_abs_error_mm": abs(
            predicted_summary["precipitation_mean_area_mm"] - observed_summary["precipitation_mean_area_mm"]
        ),
        "species_count_area_proxy_predicted": predicted_summary["species_count_area_proxy"],
        "species_count_area_proxy_observed": observed_summary["species_count_area_proxy"],
        "species_proxy_abs_error": abs(
            predicted_summary["species_count_area_proxy"] - observed_summary["species_count_area_proxy"]
        ),
        "max_species_signal_area_predicted": predicted_summary["max_species_signal_area"],
        "max_species_signal_area_observed": observed_summary["max_species_signal_area"],
        **roundtrip_metrics,
        **key_diagnostics,
        "raw_batch_input": str(saved_windows["input_window"]),
        "raw_batch_target": str(saved_windows["target_window"]),
    }

    details = {
        "label": label,
        "bounds": bounds,
        "checkpoint": str(checkpoint_path),
        "device": str(device),
        "input_months": [str(months_info["input_prev"].date()), str(months_info["input_last"].date())],
        "forecast_month": str(months_info["forecast_month"].date()),
        "predicted_summary": predicted_summary,
        "observed_summary": observed_summary,
        "roundtrip_metrics": roundtrip_metrics,
        "missing_key_diagnostics": key_diagnostics,
        "config_path": str(run_dir / "forecast_backtest_config.yaml"),
    }
    (run_dir / "forecast_backtest_config.yaml").write_text(OmegaConf.to_yaml(cfg), encoding="utf-8")
    write_json(run_dir / "forecast_backtest_detail.json", details)

    return result, details


# Eseguiamo il backtesting sui casi richiesti e salviamo una tabella finale per la fase 5.
def main() -> None:
    args = build_parser().parse_args()

    # Carichiamo l'ambiente del progetto e i path esterni.
    load_project_env()
    biocube_dir = require_path("BIOCUBE_DIR")
    model_dir = require_path("BIOANALYST_MODEL_DIR")
    project_output_dir = require_path("PROJECT_OUTPUT_DIR", create=True)
    device = resolve_torch_device(args.device)

    results = []
    details_by_city = {}
    for city in args.cities:
        result, details = run_backtest_for_city(
            city=city,
            biocube_dir=biocube_dir,
            model_dir=model_dir,
            output_dir=project_output_dir,
            checkpoint=args.checkpoint,
            device=device,
            species_threshold=args.species_threshold,
            start=args.start,
            end=args.end,
            half_window_deg=args.half_window_deg,
        )
        results.append(result)
        details_by_city[city] = details

    report_df = pd.DataFrame.from_records(results).sort_values("label")
    report_dir = resolve_forecast_output_dir(project_output_dir, f"phase5_backtest_{slugify('_'.join(args.cities))}")
    table_paths = write_forecast_tables(report_dir, "forecast_backtest_one_step", report_df)

    summary = {
        "mode": "phase5_forecast_backtest_one_step",
        "checkpoint_kind": args.checkpoint,
        "device": str(device),
        "cities": args.cities,
        "start": args.start,
        "end": args.end,
        "half_window_deg": args.half_window_deg,
        "table_csv": str(table_paths["csv"]),
        "table_excel_csv": str(table_paths["excel_csv"]),
        "table_xlsx": str(table_paths["xlsx"]),
    }
    write_json(report_dir / "forecast_backtest_summary.json", summary)
    write_json(report_dir / "forecast_backtest_details.json", details_by_city)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nCSV: {table_paths['csv']}")
    print(f"CSV Excel: {table_paths['excel_csv']}")
    print(f"XLSX: {table_paths['xlsx']}")


# Rendiamo lo script eseguibile da terminale.
if __name__ == "__main__":
    main()
