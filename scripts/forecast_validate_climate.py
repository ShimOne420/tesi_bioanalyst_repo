#!/usr/bin/env python3
"""Valida il forecast clima BioAnalyst su un set di città e mesi forecastabili.

Questo script è pensato per la validazione scientifica di temperatura e precipitazione,
prima di riportare il forecast nella UI finale.

Obiettivi:

- eseguire backtest one-step su molte città e molti mesi;
- misurare errori clima in modo consistente;
- separare la validazione del clima da quella delle specie;
- produrre report tabellari facili da aprire in Excel.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

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
    resolve_selection,
    resolve_source_paths,
    resolve_torch_device,
    rescale_batch_correct,
    save_window_batches,
    shift_month,
    slugify,
    summarize_batch_for_area,
    to_month_start,
    write_forecast_tables,
    write_json,
)
from forecast_area_indicators import ensure_batched_batch


# Definiamo un set core di città grandi e climaticamente eterogenee per la validazione iniziale.
CORE_VALIDATION_CITIES = [
    "barcelona",
    "berlin",
    "london",
    "madrid",
    "milano",
    "napoli",
    "paris",
    "lisbon",
    "stockholm",
    "athens",
    "vienna",
    "warsaw",
]


# Costruiamo una CLI dedicata alla validazione del blocco clima.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validazione clima BioAnalyst su città europee.")
    parser.add_argument(
        "--cities",
        nargs="+",
        default=None,
        help="Lista città da validare. Se omesso usa il set core.",
    )
    parser.add_argument(
        "--areas-json",
        default=None,
        help="JSON con aree custom da validare. Ogni record può avere `city` oppure `lat/lon` oppure bbox completo.",
    )
    parser.add_argument(
        "--forecast-start",
        default="2019-01-01",
        help="Primo mese da prevedere nel backtest, es. 2019-01-01.",
    )
    parser.add_argument(
        "--forecast-end",
        default="2019-12-01",
        help="Ultimo mese da prevedere nel backtest, es. 2019-12-01.",
    )
    parser.add_argument(
        "--month-stride",
        type=int,
        default=1,
        help="Passo mensile della validazione. 1 = tutti i mesi, 3 = trimestrale.",
    )
    parser.add_argument("--checkpoint", choices=["small", "large"], default="small")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--half-window-deg", type=float, default=0.5)
    parser.add_argument(
        "--temp-threshold-pct",
        type=float,
        default=2.0,
        help="Soglia percentuale in Kelvin usata per il pass/fail temperatura.",
    )
    parser.add_argument(
        "--precip-threshold-pct",
        type=float,
        default=2.0,
        help="Soglia percentuale usata per il pass/fail precipitazione.",
    )
    parser.add_argument(
        "--temp-threshold-mae-c",
        type=float,
        default=2.0,
        help="Soglia assoluta in gradi Celsius usata per il pass/fail temperatura.",
    )
    parser.add_argument(
        "--precip-threshold-mae-mm",
        type=float,
        default=2.0,
        help="Soglia assoluta in millimetri usata per il pass/fail precipitazione.",
    )
    return parser


# Generiamo la lista dei mesi forecastabili, usando sempre i due mesi precedenti come input.
def build_forecast_months(start: str, end: str, month_stride: int) -> list[pd.Timestamp]:
    start_month = to_month_start(start)
    end_month = to_month_start(end)
    if end_month < start_month:
        raise SystemExit("`forecast-end` deve essere successivo o uguale a `forecast-start`.")
    if start_month < pd.Timestamp("2000-03-01"):
        raise SystemExit("Il primo forecast utile e 2000-03-01, perche servono i due mesi precedenti.")
    if end_month > pd.Timestamp("2020-12-01"):
        raise SystemExit("La validazione clima locale e limitata al blocco osservato fino a 2020-12.")
    if month_stride < 1:
        raise SystemExit("`month-stride` deve essere almeno 1.")

    months = pd.period_range(start=start_month, end=end_month, freq="M").to_timestamp()
    return list(months[::month_stride])


# Calcoliamo metriche clima stabili, evitando percentuali instabili sulla temperatura in Celsius.
def compute_climate_metrics(predicted_summary: dict[str, float], observed_summary: dict[str, float]) -> dict[str, float]:
    temp_pred_c = float(predicted_summary["temperature_mean_area_c"])
    temp_obs_c = float(observed_summary["temperature_mean_area_c"])
    precip_pred_mm = float(predicted_summary["precipitation_mean_area_mm"])
    precip_obs_mm = float(observed_summary["precipitation_mean_area_mm"])

    # Per la temperatura usiamo il relativo errore in Kelvin, cosi la percentuale resta interpretabile.
    temp_pred_k = temp_pred_c + 273.15
    temp_obs_k = temp_obs_c + 273.15
    temp_abs_error_c = abs(temp_pred_c - temp_obs_c)
    temp_pct_error_kelvin = (abs(temp_pred_k - temp_obs_k) / max(abs(temp_obs_k), 1e-6)) * 100.0

    # Per la precipitazione riportiamo sia l'errore assoluto sia una sMAPE robusta agli zeri.
    precip_abs_error_mm = abs(precip_pred_mm - precip_obs_mm)
    precip_smape_pct = (200.0 * precip_abs_error_mm) / max(abs(precip_pred_mm) + abs(precip_obs_mm), 1e-6)
    precip_pct_error = (precip_abs_error_mm / max(abs(precip_obs_mm), 1e-6)) * 100.0

    return {
        "temperature_mean_area_c_predicted": temp_pred_c,
        "temperature_mean_area_c_observed": temp_obs_c,
        "temperature_abs_error_c": temp_abs_error_c,
        "temperature_pct_error_kelvin": temp_pct_error_kelvin,
        "precipitation_mean_area_mm_predicted": precip_pred_mm,
        "precipitation_mean_area_mm_observed": precip_obs_mm,
        "precipitation_abs_error_mm": precip_abs_error_mm,
        "precipitation_pct_error": precip_pct_error,
        "precipitation_smape_pct": precip_smape_pct,
    }


# Convertiamo una selezione custom in un Namespace compatibile con la logica comune del progetto.
def build_selection_namespace(selection: dict[str, object], half_window_deg: float) -> argparse.Namespace:
    return argparse.Namespace(
        city=selection.get("city"),
        lat=selection.get("lat"),
        lon=selection.get("lon"),
        min_lat=selection.get("min_lat"),
        max_lat=selection.get("max_lat"),
        min_lon=selection.get("min_lon"),
        max_lon=selection.get("max_lon"),
        half_window_deg=selection.get("half_window_deg", half_window_deg),
        label=selection.get("label"),
    )


# Risolviamo il set di target da validare, supportando città e aree custom non urbane.
def resolve_validation_targets(args: argparse.Namespace) -> list[dict[str, object]]:
    if args.areas_json:
        areas_path = Path(args.areas_json).expanduser().resolve()
        payload = json.loads(areas_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or not payload:
            raise SystemExit("`areas-json` deve contenere una lista non vuota di selezioni.")
        return payload

    cities = args.cities or CORE_VALIDATION_CITIES
    return [{"city": city} for city in cities]


# Eseguiamo un caso one-step singolo su una citta e un mese forecast, senza salvare artefatti pesanti per ogni caso.
def run_single_case(
    *,
    selection: dict[str, object],
    forecast_month: pd.Timestamp,
    source_paths: dict[str, Path],
    scratch_dir: Path,
    checkpoint_path: Path,
    cfg,
    model,
    dataset_class,
    batch_to_device,
    build_new_batch_with_prediction,
    detach_batch,
    device: torch.device,
    half_window_deg: float,
) -> dict[str, object]:
    # Risolviamo città, punto o bbox con la stessa logica usata dal progetto.
    selection_mode, bounds, label = resolve_selection(build_selection_namespace(selection, half_window_deg))

    # Prepariamo i due mesi input e il mese target osservato del backtest.
    input_prev = shift_month(forecast_month, -2)
    input_last = shift_month(forecast_month, -1)

    # Ripuliamo la scratch dir per non accumulare batch temporanei inutili.
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    # Costruiamo i batch raw nel formato atteso dal repo ufficiale.
    saved_windows = save_window_batches(
        output_dir=scratch_dir,
        input_months=[input_prev, input_last],
        compare_month=forecast_month,
        source_paths=source_paths,
        use_atmospheric_data=True,
    )

    # Carichiamo input e target tramite il dataloader ufficiale, cosi riusiamo scaling e parsing nativi.
    dataset = dataset_class(
        data_dir=str(scratch_dir),
        scaling_settings=cfg.data.scaling,
        num_species=cfg.data.species_number,
        atmos_levels=cfg.data.atmos_levels,
        model_patch_size=cfg.model.patch_size,
    )
    x_batch_scaled = ensure_batched_batch(dataset.load_and_process_files(str(saved_windows["input_window"])))

    # Eseguiamo il forward one-step del modello sul batch locale.
    with torch.inference_mode():
        x_batch_device = batch_to_device(x_batch_scaled, device)
        predicted_dict_scaled = model(x_batch_device, model.lead_time, batch_size=1)
        predicted_batch_scaled = build_new_batch_with_prediction(x_batch_device, predicted_dict_scaled, months=1)

    # Riportiamo il forecast nello spazio originale usando la correzione di scaling locale.
    predicted_batch_original = rescale_batch_correct(
        detach_batch(predicted_batch_scaled),
        scaling_statistics=dataset.scaling_statistics,
        mode=cfg.data.scaling.mode,
        direction="original",
    )

    # Per l'osservato usiamo il target raw del mese vero, non una ricostruzione trasformata.
    raw_target = torch.load(saved_windows["target_window"], map_location="cpu", weights_only=False)
    observed_batch_original = ensure_batched_batch(raw_dict_to_batch(raw_target))

    # Riduciamo tutto agli indicatori area-level che ci interessano per la validazione clima.
    predicted_summary = summarize_batch_for_area(predicted_batch_original, bounds=bounds, species_threshold=0.5)
    observed_summary = summarize_batch_for_area(observed_batch_original, bounds=bounds, species_threshold=0.5)
    climate_metrics = compute_climate_metrics(predicted_summary, observed_summary)

    return {
        "label": label,
        "city": selection.get("city"),
        "selection_mode": selection_mode,
        "forecast_month": str(forecast_month.date()),
        "input_prev": str(input_prev.date()),
        "input_last": str(input_last.date()),
        "checkpoint": checkpoint_path.name,
        **climate_metrics,
    }


# Aggreghiamo i casi mese-per-mese in un riassunto per città e in un riassunto complessivo.
def summarize_validation_results(
    cases_df: pd.DataFrame,
    temp_threshold_pct: float,
    precip_threshold_pct: float,
    temp_threshold_mae_c: float,
    precip_threshold_mae_mm: float,
) -> tuple[pd.DataFrame, dict[str, object]]:
    per_city = (
        cases_df.groupby("label", as_index=False)
        .agg(
            city=("city", "first"),
            cases=("forecast_month", "count"),
            temperature_mae_c=("temperature_abs_error_c", "mean"),
            temperature_mean_pct_error_kelvin=("temperature_pct_error_kelvin", "mean"),
            precipitation_mae_mm=("precipitation_abs_error_mm", "mean"),
            precipitation_mean_smape_pct=("precipitation_smape_pct", "mean"),
            precipitation_mean_pct_error=("precipitation_pct_error", "mean"),
        )
        .sort_values("label")
    )

    # Classifichiamo il pass/fail del blocco clima sia con soglie percentuali sia con soglie assolute.
    per_city["temperature_pass_pct"] = per_city["temperature_mean_pct_error_kelvin"] <= temp_threshold_pct
    per_city["temperature_pass_abs"] = per_city["temperature_mae_c"] <= temp_threshold_mae_c
    per_city["temperature_pass"] = per_city["temperature_pass_pct"] & per_city["temperature_pass_abs"]
    per_city["precipitation_pass_pct"] = per_city["precipitation_mean_smape_pct"] <= precip_threshold_pct
    per_city["precipitation_pass_abs"] = per_city["precipitation_mae_mm"] <= precip_threshold_mae_mm
    per_city["precipitation_pass"] = per_city["precipitation_pass_pct"] & per_city["precipitation_pass_abs"]
    per_city["climate_pass"] = per_city["temperature_pass"] & per_city["precipitation_pass"]

    overall = {
        "cases": int(len(cases_df)),
        "cities": int(per_city["label"].nunique()),
        "temperature_mae_c_mean": float(cases_df["temperature_abs_error_c"].mean()),
        "temperature_pct_error_kelvin_mean": float(cases_df["temperature_pct_error_kelvin"].mean()),
        "precipitation_mae_mm_mean": float(cases_df["precipitation_abs_error_mm"].mean()),
        "precipitation_smape_pct_mean": float(cases_df["precipitation_smape_pct"].mean()),
        "precipitation_pct_error_mean": float(cases_df["precipitation_pct_error"].mean()),
        "temperature_pass_share_pct": float((cases_df["temperature_pct_error_kelvin"] <= temp_threshold_pct).mean()),
        "temperature_pass_share_abs": float((cases_df["temperature_abs_error_c"] <= temp_threshold_mae_c).mean()),
        "precipitation_pass_share_pct": float((cases_df["precipitation_smape_pct"] <= precip_threshold_pct).mean()),
        "precipitation_pass_share_abs": float((cases_df["precipitation_abs_error_mm"] <= precip_threshold_mae_mm).mean()),
        "city_climate_pass_share": float(per_city["climate_pass"].mean()) if len(per_city) else 0.0,
        "temperature_threshold_pct": temp_threshold_pct,
        "temperature_threshold_mae_c": temp_threshold_mae_c,
        "precipitation_threshold_pct": precip_threshold_pct,
        "precipitation_threshold_mae_mm": precip_threshold_mae_mm,
    }
    return per_city, overall


# Coordiniamo l'intera validazione clima su piu città e piu mesi forecastabili.
def main() -> None:
    args = build_parser().parse_args()

    # Carichiamo ambiente, path e device del progetto.
    load_project_env()
    biocube_dir = require_path("BIOCUBE_DIR")
    model_dir = require_path("BIOANALYST_MODEL_DIR")
    project_output_dir = require_path("PROJECT_OUTPUT_DIR", create=True)
    device = resolve_torch_device(args.device)

    # Risolviamo città, mesi forecastabili e directory output di questo run.
    validation_targets = resolve_validation_targets(args)
    forecast_months = build_forecast_months(args.forecast_start, args.forecast_end, args.month_stride)
    target_labels = []
    for item in validation_targets[:4]:
        target_labels.append(str(item.get("label") or item.get("city") or "area"))
    run_slug = slugify(
        f"climate_validation_{args.checkpoint}_{'_'.join(target_labels)}_{args.forecast_start}_{args.forecast_end}"
    )
    run_dir = resolve_forecast_output_dir(project_output_dir, run_slug)
    scratch_dir = run_dir / "_scratch_batches"
    source_paths = resolve_source_paths(biocube_dir)

    # Importiamo il repo ufficiale e prepariamo config e modello una sola volta per l'intera validazione.
    ensure_bfm_repo_on_path()
    from bfm_model.bfm.batch_utils import build_new_batch_with_prediction
    from bfm_model.bfm.dataloader_monthly import LargeClimateDataset, batch_to_device, detach_batch
    from safetensors.torch import load_file

    checkpoint_path = resolve_checkpoint_path(model_dir, args.checkpoint)
    cfg = build_local_config(batch_dir=scratch_dir, checkpoint_path=checkpoint_path, device_name=str(device))
    model = build_bfm_model_from_cfg(cfg)
    state_dict = load_file(str(checkpoint_path))
    incompatible = model.load_state_dict(state_dict, strict=False)
    model = model.to(device)
    model.eval()
    torch.set_float32_matmul_precision(cfg.training.precision_in)

    # Eseguiamo tutti i casi città x mese e raccogliamo i record per il report finale.
    records = []
    for selection in validation_targets:
        for forecast_month in forecast_months:
            target_name = selection.get("label") or selection.get("city") or "custom_area"
            print(f"[validate] target={target_name} forecast_month={forecast_month.date()}", flush=True)
            record = run_single_case(
                selection=selection,
                forecast_month=forecast_month,
                source_paths=source_paths,
                scratch_dir=scratch_dir,
                checkpoint_path=checkpoint_path,
                cfg=cfg,
                model=model,
                dataset_class=LargeClimateDataset,
                batch_to_device=batch_to_device,
                build_new_batch_with_prediction=build_new_batch_with_prediction,
                detach_batch=detach_batch,
                device=device,
                half_window_deg=args.half_window_deg,
            )
            records.append(record)

    # Costruiamo i report casi-per-caso, il riassunto per città e il summary complessivo.
    cases_df = pd.DataFrame.from_records(records).sort_values(["label", "forecast_month"])
    per_city_df, overall_summary = summarize_validation_results(
        cases_df=cases_df,
        temp_threshold_pct=args.temp_threshold_pct,
        precip_threshold_pct=args.precip_threshold_pct,
        temp_threshold_mae_c=args.temp_threshold_mae_c,
        precip_threshold_mae_mm=args.precip_threshold_mae_mm,
    )

    # Salviamo anche i metadati del run per rendere il test ripetibile e documentato.
    metadata = {
        "mode": "forecast_validate_climate",
        "checkpoint_kind": args.checkpoint,
        "checkpoint_path": str(checkpoint_path),
        "device": str(device),
        "targets": validation_targets,
        "forecast_start": args.forecast_start,
        "forecast_end": args.forecast_end,
        "month_stride": args.month_stride,
        "cases": len(records),
        "missing_keys_count": len(incompatible.missing_keys),
        "unexpected_keys_count": len(incompatible.unexpected_keys),
        "missing_keys_sample": list(incompatible.missing_keys[:10]),
        "unexpected_keys_sample": list(incompatible.unexpected_keys[:10]),
        "overall_summary": overall_summary,
    }

    # Esportiamo le tabelle in formato comodo per Excel e per il monitoraggio della validazione.
    cases_paths = write_forecast_tables(run_dir, "forecast_validation_climate_cases", cases_df)
    city_paths = write_forecast_tables(run_dir, "forecast_validation_climate_city_summary", per_city_df)
    write_json(run_dir / "forecast_validation_climate_summary.json", metadata)
    (run_dir / "forecast_validation_climate_config.yaml").write_text(OmegaConf.to_yaml(cfg), encoding="utf-8")

    # Ripuliamo la scratch dir temporanea per lasciare solo gli artefatti utili.
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir)

    # Stampiamo un riepilogo finale utile anche da terminale.
    print(json.dumps(metadata, indent=2, ensure_ascii=False))
    print(f"\nCASES XLSX: {cases_paths['xlsx']}")
    print(f"CITY SUMMARY XLSX: {city_paths['xlsx']}")


# Rendiamo lo script eseguibile dal terminale di VS Code.
if __name__ == "__main__":
    main()
