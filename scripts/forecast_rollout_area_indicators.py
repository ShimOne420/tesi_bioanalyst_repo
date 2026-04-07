#!/usr/bin/env python3
"""Esegue un rollout forecast multi-step BioAnalyst per una selezione `area + periodo`.

Lo script:

- riusa l'adapter BIOMAP già validato per costruire il batch iniziale;
- usa il modello ufficiale per produrre forecast ricorsivi a più mesi;
- aggrega ogni step forecast sull'area selezionata;
- confronta, quando possibile, il forecast con i valori osservati dello stesso mese;
- salva una tabella finale pronta per BIOMAP e per la fase 4 della roadmap.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import torch
from omegaconf import OmegaConf

from bioanalyst_model_utils import (
    PROJECT_ROOT,
    BFM_REPO_ROOT,
    build_bfm_model_from_cfg,
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
    rescale_batch_correct,
    save_window_batches,
    shift_month,
    slugify,
    summarize_batch_for_area,
    write_forecast_tables,
    write_json,
)
from forecast_area_indicators import ensure_batched_batch
from selected_area_indicators import (
    build_selected_cell_month_frame,
    compute_area_climate_monthly,
    compute_species_area_monthly,
    load_climate_datasets,
    resolve_source_paths as resolve_indicator_source_paths,
)


# Manteniamo una CLI coerente con il forecast one-step, aggiungendo solo i parametri di rollout.
def build_parser():
    parser = build_selection_parser("Rollout forecast locale BioAnalyst per area e periodo selezionati.")
    parser.add_argument(
        "--checkpoint",
        choices=["small", "large"],
        default="small",
        help="Checkpoint BioAnalyst da usare per il rollout locale.",
    )
    parser.add_argument(
        "--device",
        choices=["auto", "cpu", "cuda", "mps"],
        default="cpu",
        help="Device su cui eseguire l'inferenza locale.",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=6,
        help="Numero di step mensili del rollout, per esempio 6 o 12.",
    )
    parser.add_argument(
        "--species-threshold",
        type=float,
        default=0.5,
        help="Soglia per trasformare l'output specie del modello in conteggio area proxy.",
    )
    parser.add_argument(
        "--fast-smoke-test",
        action="store_true",
        help="Salta il blocco atmosferico e usa placeholder a zero per un rollout tecnico più rapido.",
    )
    return parser


# Calcoliamo una tabella osservata mensile sull'area per confrontare forecast e dati reali, quando disponibili.
def build_observed_area_monthly(
    biocube_dir: Path,
    bounds: dict[str, float],
    start_month: pd.Timestamp,
    end_month: pd.Timestamp,
) -> pd.DataFrame:
    indicator_sources = resolve_indicator_source_paths(biocube_dir)

    # Carichiamo i dataset climatici già filtrati su area e periodo osservabile.
    ds_temp, ds_prec, land_mask = load_climate_datasets(
        source_paths=indicator_sources,
        bounds=bounds,
        start=str(start_month.date()),
        end=str(end_month.date()),
        max_steps=None,
    )

    # Costruiamo il frame clima area mese riusando la logica già validata del progetto.
    climate_frames = []
    for time_index in range(ds_temp.sizes["valid_time"]):
        climate_frames.append(
            build_selected_cell_month_frame(
                ds_temp=ds_temp,
                ds_prec=ds_prec,
                land_mask=land_mask,
                species_lookup={},
                time_index=time_index,
            )
        )
    climate_area = compute_area_climate_monthly(pd.concat(climate_frames, ignore_index=True))

    # Calcoliamo separatamente il conteggio specie osservate sull'area.
    species_area = compute_species_area_monthly(
        species_path=indicator_sources["species"],
        bounds=bounds,
        start=str(start_month.date()),
        end=str(end_month.date()),
        max_steps=None,
    )

    observed = climate_area.merge(species_area, on="month", how="left")
    observed["forecast_month"] = observed["month"]
    return observed


# Estraiamo l'ultimo timestamp scalare da un metadata annidato del rollout.
def last_timestamp_from_metadata(timestamp_value) -> pd.Timestamp:
    value = timestamp_value
    while isinstance(value, (list, tuple)):
        value = value[-1]
    return pd.Timestamp(str(value))


# Convertiamo il rollout del modello in una tabella mensile BIOMAP leggibile.
def build_rollout_frame(
    rollout_batches: list,
    bounds: dict[str, float],
    species_threshold: float,
) -> pd.DataFrame:
    records = []
    for step_index, batch in enumerate(rollout_batches, start=1):
        summary = summarize_batch_for_area(batch, bounds=bounds, species_threshold=species_threshold)
        forecast_month = last_timestamp_from_metadata(batch.batch_metadata.timestamp)
        records.append(
            {
                "rollout_step": step_index,
                "forecast_month": str(forecast_month.date()),
                "temperature_mean_area_c_predicted": summary["temperature_mean_area_c"],
                "precipitation_mean_area_mm_predicted": summary["precipitation_mean_area_mm"],
                "species_count_area_proxy_predicted": summary["species_count_area_proxy"],
                "max_species_signal_area_predicted": summary["max_species_signal_area"],
                "cell_count_land_proxy_predicted": summary["cell_count_land_proxy"],
            }
        )
    return pd.DataFrame.from_records(records)


# Eseguiamo la pipeline rollout end-to-end e salviamo tutti gli artefatti utili alla fase 4.
def main() -> None:
    args = build_parser().parse_args()
    if args.steps < 1:
        raise SystemExit("`--steps` deve essere almeno 1.")

    # Carichiamo l'ambiente e i path esterni del progetto.
    load_project_env()
    biocube_dir = require_path("BIOCUBE_DIR")
    model_dir = require_path("BIOANALYST_MODEL_DIR")
    project_output_dir = require_path("PROJECT_OUTPUT_DIR", create=True)

    # Risolviamo area, periodo e cartella del run.
    selection_mode, bounds, label = resolve_selection(args)
    months_info = resolve_forecast_months(args.start, args.end)
    run_label = f"{slugify(label)}_{months_info['end_month'].strftime('%Y_%m')}_rollout_{args.steps}m"
    run_dir = resolve_forecast_output_dir(project_output_dir, run_label)
    batch_dir = run_dir / "batches"
    print(f"[1/8] Setup rollout pronto per `{label}` in `{run_dir}`", flush=True)

    # Costruiamo il batch iniziale sugli ultimi due mesi osservati del periodo selezionato.
    source_paths = resolve_source_paths(biocube_dir)
    input_months = [months_info["input_prev"], months_info["input_last"]]
    compare_end_month = shift_month(months_info["forecast_month"], args.steps - 1)
    compare_month = months_info["forecast_month"] if compare_end_month <= pd.Timestamp("2020-12-01") else None
    print(
        f"[2/8] Costruisco batch iniziale per {input_months[0].date()} -> {input_months[1].date()}",
        flush=True,
    )
    saved_windows = save_window_batches(
        output_dir=batch_dir,
        input_months=input_months,
        compare_month=compare_month,
        source_paths=source_paths,
        use_atmospheric_data=not args.fast_smoke_test,
    )
    print(f"[2/8] Batch iniziale salvato in `{batch_dir}`", flush=True)

    # Importiamo il codice ufficiale del modello solo dopo aver preparato il contesto locale.
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.batch_utils import build_new_batch_with_prediction
    from bfm_model.bfm.dataloader_monthly import LargeClimateDataset, batch_to_device, detach_batch
    from safetensors.torch import load_file

    # Creiamo config, loader e batch iniziale scalato.
    device = resolve_torch_device(args.device)
    checkpoint_path = resolve_checkpoint_path(model_dir, args.checkpoint)
    cfg = build_local_config(batch_dir=batch_dir, checkpoint_path=checkpoint_path, device_name=str(device))
    dataset = LargeClimateDataset(
        data_dir=str(batch_dir),
        scaling_settings=cfg.data.scaling,
        num_species=cfg.data.species_number,
        atmos_levels=cfg.data.atmos_levels,
        model_patch_size=cfg.model.patch_size,
    )
    initial_batch_scaled = ensure_batched_batch(dataset.load_and_process_files(str(saved_windows["input_window"])))
    print(f"[3/8] Batch iniziale caricato e scalato", flush=True)

    # Carichiamo il checkpoint ufficiale e inizializziamo il modello in modalità eval.
    model = build_bfm_model_from_cfg(cfg)
    state_dict = load_file(str(checkpoint_path))
    incompatible = model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    torch.set_float32_matmul_precision(cfg.training.precision_in)
    print(f"[4/8] Modello pronto, avvio rollout di {args.steps} mesi", flush=True)

    # Eseguiamo il rollout ricorsivo one-step per N mesi mantenendo il formato ufficiale dei batch.
    with torch.inference_mode():
        curr = batch_to_device(initial_batch_scaled, device)
        rollout_batches_scaled = []
        for rollout_step in range(args.steps):
            preds = model(curr, model.lead_time, batch_size=1, rollout_step=rollout_step)
            next_batch = build_new_batch_with_prediction(curr, preds)
            rollout_batches_scaled.append(next_batch)
            curr = next_batch
    print("[5/8] Rollout completato", flush=True)

    # Riportiamo ogni batch predetto nello spazio originale e costruiamo la tabella forecast.
    rollout_batches_original = [
        rescale_batch_correct(
            detach_batch(batch),
            scaling_statistics=dataset.scaling_statistics,
            mode=cfg.data.scaling.mode,
            direction="original",
        )
        for batch in rollout_batches_scaled
    ]
    rollout_frame = build_rollout_frame(
        rollout_batches=rollout_batches_original,
        bounds=bounds,
        species_threshold=args.species_threshold,
    )
    print("[6/8] Tabella forecast costruita", flush=True)

    # Se i mesi futuri sono ancora osservabili nel dataset, aggiungiamo il confronto forecast vs observed.
    forecast_start = months_info["forecast_month"]
    forecast_end = shift_month(forecast_start, args.steps - 1)
    observed_compare = None
    if forecast_start <= pd.Timestamp("2020-12-01"):
        observed_end = min(forecast_end, pd.Timestamp("2020-12-01"))
        observed_compare = build_observed_area_monthly(
            biocube_dir=biocube_dir,
            bounds=bounds,
            start_month=forecast_start,
            end_month=observed_end,
        )
        rollout_frame = rollout_frame.merge(
            observed_compare[
                [
                    "forecast_month",
                    "temperature_mean_area_c",
                    "precipitation_mean_area_mm",
                    "species_count_observed_area",
                ]
            ].rename(
                columns={
                    "temperature_mean_area_c": "temperature_mean_area_c_observed",
                    "precipitation_mean_area_mm": "precipitation_mean_area_mm_observed",
                    "species_count_observed_area": "species_count_observed_area",
                }
            ),
            on="forecast_month",
            how="left",
        )
    print("[7/8] Confronto con osservato costruito", flush=True)

    # Salviamo tabelle, config e summary finale del rollout.
    table_paths = write_forecast_tables(run_dir, f"forecast_rollout_{args.steps}m", rollout_frame)
    config_path = run_dir / "forecast_rollout_config.yaml"
    config_path.write_text(OmegaConf.to_yaml(cfg), encoding="utf-8")

    summary = {
        "mode": "bioanalyst_forecast_rollout_area_indicators",
        "label": label,
        "selection_mode": selection_mode,
        "bounds": bounds,
        "checkpoint": str(checkpoint_path),
        "checkpoint_kind": args.checkpoint,
        "device": str(device),
        "steps": args.steps,
        "fast_smoke_test": bool(args.fast_smoke_test),
        "input_months": [str(month.date()) for month in input_months],
        "forecast_start_month": str(forecast_start.date()),
        "forecast_end_month": str(forecast_end.date()),
        "compare_observed_until": str(min(forecast_end, pd.Timestamp('2020-12-01')).date())
        if observed_compare is not None
        else None,
        "missing_keys_count": len(incompatible.missing_keys),
        "unexpected_keys_count": len(incompatible.unexpected_keys),
        "missing_keys_sample": incompatible.missing_keys[:10],
        "unexpected_keys_sample": incompatible.unexpected_keys[:10],
        "forecast_table_csv": str(table_paths["csv"]),
        "forecast_table_excel_csv": str(table_paths["excel_csv"]),
        "forecast_table_xlsx": str(table_paths["xlsx"]),
    }
    write_json(run_dir / "forecast_rollout_summary.json", summary)
    print("[8/8] Output rollout salvati correttamente", flush=True)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nConfig: {config_path}")
    print(f"CSV: {table_paths['csv']}")
    print(f"CSV Excel: {table_paths['excel_csv']}")
    print(f"XLSX: {table_paths['xlsx']}")


# Rendiamo lo script eseguibile da terminale.
if __name__ == "__main__":
    main()
