#!/usr/bin/env python3
"""Esegue un forecast locale BioAnalyst per una selezione `area + periodo`.

Lo script:

- costruisce batch `.pt` compatibili con il repo ufficiale `bfm-model`;
- carica il checkpoint `small` o `large`;
- usa gli ultimi due mesi osservati del periodo scelto come input;
- produce un forecast a +1 mese aggregato sull'area selezionata;
- confronta la previsione con il mese osservato successivo, se disponibile.
"""

from __future__ import annotations

import json
from pathlib import Path

import torch
from omegaconf import OmegaConf

from bioanalyst_model_utils import (
    PROJECT_ROOT,
    BFM_REPO_ROOT,
    build_bfm_model_from_cfg,
    build_comparison_frame,
    build_local_config,
    build_selection_parser,
    ensure_bfm_repo_on_path,
    load_project_env,
    require_path,
    resolve_checkpoint_path,
    resolve_forecast_months,
    resolve_forecast_output_dir,
    resolve_selection,
    resolve_source_paths,
    resolve_torch_device,
    raw_dict_to_batch,
    rescale_batch_correct,
    save_window_batches,
    slugify,
    summarize_batch_for_area,
    write_forecast_tables,
    write_json,
)


# Costruiamo una CLI coerente con la selezione area/periodo già usata dal progetto.
def build_parser():
    parser = build_selection_parser("Forecast locale BioAnalyst per area e periodo selezionati.")
    parser.add_argument(
        "--checkpoint",
        choices=["small", "large"],
        default="small",
        help="Checkpoint BioAnalyst da usare per il test locale.",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda", "mps"],
        default="cpu",
        help="Device su cui eseguire l'inferenza locale.",
    )
    parser.add_argument(
        "--species-threshold",
        type=float,
        default=0.5,
        help="Soglia per trasformare l'output specie del modello in conteggio area proxy.",
    )
    parser.add_argument(
        "--no-compare-observed",
        action="store_true",
        help="Disabilita il confronto con il mese osservato successivo anche se disponibile.",
    )
    parser.add_argument(
        "--fast-smoke-test",
        action="store_true",
        help="Salta il blocco atmosferico e usa placeholder a zero per chiudere uno smoke test rapido del modello.",
    )
    return parser


# Il codice ufficiale del modello si aspetta metadata lat/lon con dimensione batch esplicita.
def ensure_batched_batch(batch):
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

    # Tutti i gruppi variabili devono avere batch dimension esplicita davanti a T/H/W o T/L/H/W.
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


# Eseguiamo la pipeline forecast end-to-end e salviamo tutti gli artefatti utili alla tesi.
def main() -> None:
    args = build_parser().parse_args()

    # Carichiamo l'ambiente del progetto e i path esterni.
    load_project_env()
    biocube_dir = require_path("BIOCUBE_DIR")
    model_dir = require_path("BIOANALYST_MODEL_DIR")
    project_output_dir = require_path("PROJECT_OUTPUT_DIR", create=True)

    # Risolviamo area, periodo e directory di output di questo run.
    selection_mode, bounds, label = resolve_selection(args)
    months_info = resolve_forecast_months(args.start, args.end)
    run_label = f"{slugify(label)}_{months_info['end_month'].strftime('%Y_%m')}"
    run_dir = resolve_forecast_output_dir(project_output_dir, run_label)
    batch_dir = run_dir / "batches"
    print(f"[1/7] Setup pronto per `{label}` in `{run_dir}`", flush=True)

    # Prepariamo le finestre raw del modello usando gli ultimi due mesi osservati.
    source_paths = resolve_source_paths(biocube_dir)
    input_months = [months_info["input_prev"], months_info["input_last"]]
    compare_month = months_info["forecast_month"] if months_info["compare_available"] and not args.no_compare_observed else None
    print(
        f"[2/7] Costruisco batch raw per i mesi input {input_months[0].date()} -> {input_months[1].date()}",
        flush=True,
    )
    saved_windows = save_window_batches(
        output_dir=batch_dir,
        input_months=input_months,
        compare_month=compare_month,
        source_paths=source_paths,
        use_atmospheric_data=not args.fast_smoke_test,
    )
    print(f"[2/7] Batch raw salvati in `{batch_dir}`", flush=True)

    # Agganciamo il repo ufficiale al PYTHONPATH e importiamo solo qui il codice BFM.
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.batch_utils import build_new_batch_with_prediction
    from bfm_model.bfm.dataloader_monthly import LargeClimateDataset, batch_to_device, detach_batch
    from safetensors.torch import load_file

    # Costruiamo la config locale per il modello small e risolviamo device + checkpoint.
    device = resolve_torch_device(args.device)
    checkpoint_path = resolve_checkpoint_path(model_dir, args.checkpoint)
    cfg = build_local_config(batch_dir=batch_dir, checkpoint_path=checkpoint_path, device_name=str(device))
    print(f"[3/7] Config locale costruita, checkpoint `{checkpoint_path.name}`, device `{device}`", flush=True)

    # Carichiamo il dataset locale dei batch per sfruttare scaling e parsing ufficiali.
    dataset = LargeClimateDataset(
        data_dir=str(batch_dir),
        scaling_settings=cfg.data.scaling,
        num_species=cfg.data.species_number,
        atmos_levels=cfg.data.atmos_levels,
        model_patch_size=cfg.model.patch_size,
    )
    x_batch_scaled = ensure_batched_batch(dataset.load_and_process_files(str(saved_windows["input_window"])))
    y_batch_scaled = (
        ensure_batched_batch(dataset.load_and_process_files(str(saved_windows["target_window"])))
        if "target_window" in saved_windows
        else None
    )
    print("[4/7] Batch scalati caricati dal loader ufficiale", flush=True)

    # Inizializziamo il modello small, carichiamo i pesi `safetensors` e registriamo eventuali mismatch.
    model = build_bfm_model_from_cfg(cfg)
    state_dict = load_file(str(checkpoint_path))
    incompatible = model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    torch.set_float32_matmul_precision(cfg.training.precision_in)
    print("[5/7] Modello caricato, inizio inferenza one-step", flush=True)

    # Eseguiamo un singolo forward pass sul batch locale costruito da BIOMAP.
    with torch.inference_mode():
        x_batch_device = batch_to_device(x_batch_scaled, device)
        predicted_dict_scaled = model(x_batch_device, model.lead_time, batch_size=1)
        predicted_batch_scaled = build_new_batch_with_prediction(x_batch_device, predicted_dict_scaled, months=1)
    print("[5/7] Inferenza completata", flush=True)

    # Riportiamo batch predetto e batch osservato nello spazio originale per avere output leggibili.
    predicted_batch_original = rescale_batch_correct(
        detach_batch(predicted_batch_scaled),
        scaling_statistics=dataset.scaling_statistics,
        mode=cfg.data.scaling.mode,
        direction="original",
    )
    observed_batch_original = None
    if y_batch_scaled is not None and "target_window" in saved_windows:
        raw_target = torch.load(saved_windows["target_window"], map_location="cpu", weights_only=False)
        observed_batch_original = ensure_batched_batch(raw_dict_to_batch(raw_target))
    print("[6/7] Batch riportati nello spazio originale", flush=True)

    # Aggreghiamo il forecast sull'area selezionata per ottenere indicatori finali leggibili.
    predicted_summary = summarize_batch_for_area(
        predicted_batch_original,
        bounds=bounds,
        species_threshold=args.species_threshold,
    )
    observed_summary = (
        summarize_batch_for_area(observed_batch_original, bounds=bounds, species_threshold=args.species_threshold)
        if observed_batch_original is not None
        else None
    )

    # Costruiamo una tabella forecast vs observed e salviamo gli output scaricabili.
    comparison_frame = build_comparison_frame(
        label=label,
        forecast_month=months_info["forecast_month"],
        selection_mode=selection_mode,
        bounds=bounds,
        predicted_summary=predicted_summary,
        observed_summary=observed_summary,
    )
    table_paths = write_forecast_tables(run_dir, "forecast_area_indicators", comparison_frame)

    # Scriviamo config, log e summary del run per documentare le fasi 2 e 3 della roadmap.
    config_path = run_dir / "forecast_config.yaml"
    config_path.write_text(OmegaConf.to_yaml(cfg), encoding="utf-8")

    summary = {
        "mode": "bioanalyst_forecast_area_indicators",
        "label": label,
        "selection_mode": selection_mode,
        "bounds": bounds,
        "project_root": str(PROJECT_ROOT),
        "bfm_repo_root": str(BFM_REPO_ROOT),
        "checkpoint": str(checkpoint_path),
        "checkpoint_kind": args.checkpoint,
        "device": str(device),
        "fast_smoke_test": bool(args.fast_smoke_test),
        "input_months": [str(month.date()) for month in input_months],
        "forecast_month": str(months_info["forecast_month"].date()),
        "compare_with_observed": observed_summary is not None,
        "missing_keys_count": len(incompatible.missing_keys),
        "unexpected_keys_count": len(incompatible.unexpected_keys),
        "missing_keys_sample": incompatible.missing_keys[:10],
        "unexpected_keys_sample": incompatible.unexpected_keys[:10],
        "predicted_summary": predicted_summary,
        "observed_summary": observed_summary,
        "raw_batch_input": str(saved_windows["input_window"]),
        "raw_batch_target": str(saved_windows["target_window"]) if "target_window" in saved_windows else None,
        "forecast_table_csv": str(table_paths["csv"]),
        "forecast_table_excel_csv": str(table_paths["excel_csv"]),
        "forecast_table_xlsx": str(table_paths["xlsx"]),
    }
    write_json(run_dir / "forecast_summary.json", summary)

    # Stampiamo un riepilogo finale utile anche da terminale.
    print("[7/7] Output forecast salvati correttamente", flush=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nConfig: {config_path}")
    print(f"CSV: {table_paths['csv']}")
    print(f"CSV Excel: {table_paths['excel_csv']}")
    print(f"XLSX: {table_paths['xlsx']}")


# Rendiamo lo script eseguibile da terminale.
if __name__ == "__main__":
    main()
