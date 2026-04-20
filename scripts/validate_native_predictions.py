#!/usr/bin/env python3
"""Valida run one-step BioAnalyst direttamente nello spazio nativo del modello."""

from __future__ import annotations

import argparse
import json
from argparse import Namespace
from pathlib import Path

import pandas as pd

from bioanalyst_model_utils import resolve_forecast_output_dir, write_json
from bioanalyst_native_utils import (
    build_native_run_context,
    build_native_runtime,
    compute_native_climate_comparison,
    compute_native_group_comparison,
    evaluate_native_run_sanity,
    load_native_manifest,
    prepare_native_forecast_environment,
    prepare_native_saved_windows,
    run_native_one_step,
    save_native_one_step_artifacts,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Esegue più casi one-step BioAnalyst e salva un benchmark nativo con climate, species e sanity checks.",
    )
    parser.add_argument(
        "--cases-json",
        type=Path,
        default=None,
        help="File JSON con lista di casi nel formato [{\"city\": ..., \"start\": ..., \"end\": ...}].",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="Caso nel formato city,start,end. Esempio: madrid,2019-11-01,2019-12-01",
    )
    parser.add_argument("--checkpoint", choices=["small", "large"], default="small")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="cpu")
    parser.add_argument("--error-threshold-pct", type=float, default=3.0)
    parser.add_argument("--species-top-n", type=int, default=5)
    parser.add_argument("--half-window-deg", type=float, default=0.5)
    parser.add_argument("--amp-bf16", action="store_true", help="Usa autocast bfloat16 su CUDA per ridurre memoria.")
    parser.add_argument("--output-label", default=None, help="Etichetta della cartella riassuntiva finale.")
    return parser


def parse_case(raw_case: str) -> dict[str, str]:
    parts = [part.strip() for part in raw_case.split(",")]
    if len(parts) != 3:
        raise SystemExit(f"Caso non valido: `{raw_case}`. Usa `city,start,end`.")
    return {
        "city": parts[0],
        "start": parts[1],
        "end": parts[2],
    }


def load_cases_from_json(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit("Il file JSON dei casi deve contenere una lista.")
    cases = []
    for item in payload:
        if not all(key in item for key in ("city", "start", "end")):
            raise SystemExit("Ogni caso nel JSON deve avere `city`, `start`, `end`.")
        cases.append(
            {
                "city": str(item["city"]),
                "start": str(item["start"]),
                "end": str(item["end"]),
            }
        )
    return cases


def build_case_args(case: dict[str, str], checkpoint: str, device: str, half_window_deg: float) -> Namespace:
    return Namespace(
        start=case["start"],
        end=case["end"],
        label=None,
        city=case["city"],
        lat=None,
        lon=None,
        half_window_deg=half_window_deg,
        min_lat=None,
        max_lat=None,
        min_lon=None,
        max_lon=None,
        checkpoint=checkpoint,
        device=device,
    )


def build_case_record(
    *,
    case: dict[str, str],
    context,
    manifest: dict,
    climate: dict[str, object],
    species: dict[str, object],
    sanity: dict[str, object],
    error_threshold_pct: float,
) -> dict[str, object]:
    temperature = climate["temperature_c"]
    precipitation = climate["precipitation_mm"]
    species_pass = float(species["mean_error_pct"]) <= error_threshold_pct

    return {
        "city": context.label,
        "case_start": case["start"],
        "case_end": case["end"],
        "forecast_month": manifest["forecast_month"],
        "selection_mode": context.selection_mode,
        "checkpoint_kind": manifest["checkpoint_kind"],
        "device": manifest["device"],
        "temperature_predicted_mean_c": temperature["predicted_mean"],
        "temperature_observed_mean_c": temperature["observed_mean"],
        "temperature_bias_c": temperature["bias"],
        "temperature_mae_c": temperature["mae"],
        "temperature_rmse_c": temperature["rmse"],
        "temperature_error_pct_kelvin": temperature["error_pct"],
        "temperature_pass_3pct": float(temperature["error_pct"]) <= error_threshold_pct,
        "precipitation_predicted_mean_mm": precipitation["predicted_mean"],
        "precipitation_observed_mean_mm": precipitation["observed_mean"],
        "precipitation_bias_mm": precipitation["bias"],
        "precipitation_mae_mm": precipitation["mae"],
        "precipitation_rmse_mm": precipitation["rmse"],
        "precipitation_error_pct": precipitation["error_pct"],
        "precipitation_pass_3pct": float(precipitation["error_pct"]) <= error_threshold_pct,
        "species_variable_count": species["variable_count"],
        "species_mean_predicted": species["mean_predicted"],
        "species_mean_observed": species["mean_observed"],
        "species_mean_bias": species["mean_bias"],
        "species_mean_mae": species["mean_mae"],
        "species_mean_rmse": species["mean_rmse"],
        "species_mean_error_pct": species["mean_error_pct"],
        "species_pass_3pct_proxy": species_pass,
        "prediction_path_equals_observed_path": not bool(sanity["paths_differ"]),
        "predicted_forecast_month_ok": bool(sanity["predicted_forecast_month_ok"]),
        "observed_forecast_month_ok": bool(sanity["observed_forecast_month_ok"]),
        "observed_input_alignment_ok": bool(sanity["observed_input_alignment_ok"]),
        "lead_time_match": bool(sanity["lead_time_match"]),
        "identical_area_maps_flag": bool(sanity["identical_area_maps_flag"]),
        "sanity_pass": bool(sanity["sanity_pass"]),
        "run_dir": str(context.run_dir),
    }


def build_species_rows(*, city: str, forecast_month: str, species: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for rank, item in enumerate(species["top_variables_by_mae"], start=1):
        rows.append(
            {
                "city": city,
                "forecast_month": forecast_month,
                "rank_by_mae": rank,
                "variable": item["variable"],
                "unit": item["unit"],
                "predicted_mean": item["predicted_mean"],
                "observed_mean": item["observed_mean"],
                "bias": item["bias"],
                "mae": item["mae"],
                "rmse": item["rmse"],
                "error_pct": item["error_pct"],
            }
        )
    return rows


def write_validation_outputs(
    output_dir: Path,
    cases_frame: pd.DataFrame,
    by_city_frame: pd.DataFrame,
    species_frame: pd.DataFrame,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = output_dir / "native_prediction_validation.xlsx"
    cases_csv = output_dir / "native_prediction_validation_cases.csv"
    species_csv = output_dir / "native_prediction_validation_species_top.csv"
    summary_json = output_dir / "native_prediction_validation_summary.json"

    cases_frame.to_csv(cases_csv, index=False)
    species_frame.to_csv(species_csv, index=False)
    with pd.ExcelWriter(xlsx_path) as writer:
        cases_frame.to_excel(writer, sheet_name="cases", index=False)
        by_city_frame.to_excel(writer, sheet_name="by_city", index=False)
        species_frame.to_excel(writer, sheet_name="species_top", index=False)

    summary_payload = {
        "case_count": int(len(cases_frame)),
        "city_count": int(cases_frame["city"].nunique()) if not cases_frame.empty else 0,
        "sanity_pass_count": int(cases_frame["sanity_pass"].sum()) if not cases_frame.empty else 0,
        "identical_area_maps_count": int(cases_frame["identical_area_maps_flag"].sum()) if not cases_frame.empty else 0,
        "temperature_mean_error_pct_kelvin": float(cases_frame["temperature_error_pct_kelvin"].mean()) if not cases_frame.empty else 0.0,
        "precipitation_mean_error_pct": float(cases_frame["precipitation_error_pct"].mean()) if not cases_frame.empty else 0.0,
        "species_mean_error_pct": float(cases_frame["species_mean_error_pct"].mean()) if not cases_frame.empty else 0.0,
        "temperature_pass_rate_pct": float(cases_frame["temperature_pass_3pct"].mean() * 100.0) if not cases_frame.empty else 0.0,
        "precipitation_pass_rate_pct": float(cases_frame["precipitation_pass_3pct"].mean() * 100.0) if not cases_frame.empty else 0.0,
        "species_pass_rate_pct_proxy": float(cases_frame["species_pass_3pct_proxy"].mean() * 100.0) if not cases_frame.empty else 0.0,
    }
    write_json(summary_json, summary_payload)

    return {
        "xlsx": xlsx_path,
        "cases_csv": cases_csv,
        "species_csv": species_csv,
        "summary_json": summary_json,
    }


def main() -> None:
    args = build_parser().parse_args()
    env = prepare_native_forecast_environment()
    cases = []
    if args.cases_json is not None:
        cases.extend(load_cases_from_json(args.cases_json.resolve()))
    cases.extend(parse_case(raw_case) for raw_case in args.case)
    if not cases:
        raise SystemExit("Specifica almeno un caso con `--case` oppure `--cases-json`.")

    case_records = []
    species_rows = []
    for index, case in enumerate(cases, start=1):
        print(f"[case {index}/{len(cases)}] {case['city']} {case['start']} -> {case['end']}", flush=True)
        case_args = build_case_args(case, args.checkpoint, args.device, args.half_window_deg)
        context = build_native_run_context(
            args=case_args,
            project_output_dir=env["project_output_dir"],
            model_dir=env["model_dir"],
            run_suffix="native_one_step_validation",
        )
        compare_month = context.months_info["forecast_month"] if context.months_info["compare_available"] else None
        if compare_month is None:
            raise SystemExit(f"Il caso `{case['city']}` non ha target osservato disponibile per il confronto.")

        saved_windows = prepare_native_saved_windows(
            context=context,
            source_paths=env["source_paths"],
            compare_month=compare_month,
            use_atmospheric_data=True,
        )
        runtime = build_native_runtime(
            batch_dir=context.batch_dir,
            checkpoint_path=context.checkpoint_path,
            device=context.device,
        )
        result = run_native_one_step(
            context=context,
            runtime=runtime,
            saved_windows=saved_windows,
            use_amp_bf16=args.amp_bf16,
        )
        save_native_one_step_artifacts(
            context=context,
            runtime=runtime,
            result=result,
        )

        manifest = load_native_manifest(context.run_dir)
        climate = compute_native_climate_comparison(
            result.predicted_batch_original,
            result.observed_batch_original,
            bounds=context.bounds,
        )
        species = compute_native_group_comparison(
            result.predicted_batch_original,
            result.observed_batch_original,
            group_name="species",
            bounds=context.bounds,
            top_n=args.species_top_n,
        )
        sanity = evaluate_native_run_sanity(
            manifest,
            result.predicted_batch_original,
            result.observed_batch_original,
        )

        case_records.append(
            build_case_record(
                case=case,
                context=context,
                manifest=manifest,
                climate=climate,
                species=species,
                sanity=sanity,
                error_threshold_pct=args.error_threshold_pct,
            )
        )
        species_rows.extend(
            build_species_rows(
                city=context.label,
                forecast_month=manifest["forecast_month"],
                species=species,
            )
        )

    cases_frame = pd.DataFrame.from_records(case_records)
    by_city_frame = (
        cases_frame.groupby("city", as_index=False)
        .agg(
            case_count=("city", "count"),
            sanity_pass_rate_pct=("sanity_pass", lambda values: float(pd.Series(values).mean() * 100.0)),
            temperature_mean_error_pct_kelvin=("temperature_error_pct_kelvin", "mean"),
            precipitation_mean_error_pct=("precipitation_error_pct", "mean"),
            species_mean_error_pct=("species_mean_error_pct", "mean"),
            identical_area_maps_count=("identical_area_maps_flag", "sum"),
        )
        .sort_values("city")
    )
    species_frame = pd.DataFrame.from_records(species_rows)

    output_label = args.output_label or f"native_prediction_validation_{args.checkpoint}_{args.device}_{len(cases)}cases"
    validation_dir = resolve_forecast_output_dir(env["project_output_dir"], output_label)
    output_paths = write_validation_outputs(validation_dir, cases_frame, by_city_frame, species_frame)

    print(
        json.dumps(
            {
                "cases": len(cases),
                "output_dir": str(validation_dir),
                "outputs": {key: str(value) for key, value in output_paths.items()},
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
