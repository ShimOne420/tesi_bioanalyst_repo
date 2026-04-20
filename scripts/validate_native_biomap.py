#!/usr/bin/env python3
"""Esegue più run one-step nativi e costruisce un Excel di validazione BIOMAP."""

from __future__ import annotations

import argparse
import json
from argparse import Namespace
from pathlib import Path

import pandas as pd

from bioanalyst_model_utils import resolve_forecast_output_dir, summarize_batch_for_area, write_json
from bioanalyst_native_utils import (
    build_native_run_context,
    build_native_runtime,
    prepare_native_forecast_environment,
    prepare_native_saved_windows,
    run_native_one_step,
    save_native_one_step_artifacts,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Valida più casi one-step BioAnalyst e salva un Excel con predicted, observed ed errori BIOMAP.",
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
    parser.add_argument("--species-threshold", type=float, default=0.5)
    parser.add_argument("--error-threshold-pct", type=float, default=3.0)
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


def build_case_args(case: dict[str, str], checkpoint: str, device: str) -> Namespace:
    return Namespace(
        start=case["start"],
        end=case["end"],
        label=None,
        city=case["city"],
        lat=None,
        lon=None,
        half_window_deg=0.5,
        min_lat=None,
        max_lat=None,
        min_lon=None,
        max_lon=None,
        checkpoint=checkpoint,
        device=device,
    )


def pct_error(predicted: float, observed: float) -> float:
    if abs(observed) < 1e-12:
        return 0.0 if abs(predicted) < 1e-12 else 100.0
    return abs(predicted - observed) / abs(observed) * 100.0


def temperature_pct_error_kelvin(predicted_c: float, observed_c: float) -> float:
    return pct_error(predicted_c + 273.15, observed_c + 273.15)


def build_validation_record(
    *,
    case: dict[str, str],
    context,
    predicted_summary: dict[str, float | int],
    observed_summary: dict[str, float | int],
    run_dir: Path,
    error_threshold_pct: float,
) -> dict[str, object]:
    temp_abs = abs(predicted_summary["temperature_mean_area_c"] - observed_summary["temperature_mean_area_c"])
    temp_pct = temperature_pct_error_kelvin(
        predicted_summary["temperature_mean_area_c"],
        observed_summary["temperature_mean_area_c"],
    )
    precip_abs = abs(
        predicted_summary["precipitation_mean_area_mm"] - observed_summary["precipitation_mean_area_mm"]
    )
    precip_pct = pct_error(
        predicted_summary["precipitation_mean_area_mm"],
        observed_summary["precipitation_mean_area_mm"],
    )
    species_abs = abs(
        float(predicted_summary["species_count_area_proxy"]) - float(observed_summary["species_count_area_proxy"])
    )
    species_pct = pct_error(
        float(predicted_summary["species_count_area_proxy"]),
        float(observed_summary["species_count_area_proxy"]),
    )

    temperature_pass = temp_pct <= error_threshold_pct
    precipitation_pass = precip_pct <= error_threshold_pct
    species_pass = species_pct <= error_threshold_pct

    return {
        "city": context.label,
        "case_start": case["start"],
        "case_end": case["end"],
        "forecast_month": str(context.months_info["forecast_month"].date()),
        "selection_mode": context.selection_mode,
        "temperature_predicted_c": predicted_summary["temperature_mean_area_c"],
        "temperature_observed_c": observed_summary["temperature_mean_area_c"],
        "temperature_abs_error_c": temp_abs,
        "temperature_error_pct_kelvin": temp_pct,
        "temperature_pass_3pct": temperature_pass,
        "precipitation_predicted_mm": predicted_summary["precipitation_mean_area_mm"],
        "precipitation_observed_mm": observed_summary["precipitation_mean_area_mm"],
        "precipitation_abs_error_mm": precip_abs,
        "precipitation_error_pct": precip_pct,
        "precipitation_pass_3pct": precipitation_pass,
        "species_predicted_proxy": predicted_summary["species_count_area_proxy"],
        "species_observed_proxy": observed_summary["species_count_area_proxy"],
        "species_abs_error_proxy": species_abs,
        "species_error_pct_proxy": species_pct,
        "species_pass_3pct": species_pass,
        "overall_pass_3pct": temperature_pass and precipitation_pass and species_pass,
        "cell_count_land_proxy": predicted_summary["cell_count_land_proxy"],
        "run_dir": str(run_dir),
    }


def write_validation_workbook(output_dir: Path, cases_frame: pd.DataFrame, by_city_frame: pd.DataFrame) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    xlsx_path = output_dir / "native_biomap_validation.xlsx"
    csv_path = output_dir / "native_biomap_validation_cases.csv"
    json_path = output_dir / "native_biomap_validation_summary.json"

    cases_frame.to_csv(csv_path, index=False)
    with pd.ExcelWriter(xlsx_path) as writer:
        cases_frame.to_excel(writer, sheet_name="cases", index=False)
        by_city_frame.to_excel(writer, sheet_name="by_city", index=False)

    summary_payload = {
        "case_count": int(len(cases_frame)),
        "city_count": int(by_city_frame["city"].nunique()) if not by_city_frame.empty else 0,
        "overall_pass_count": int(cases_frame["overall_pass_3pct"].sum()) if not cases_frame.empty else 0,
        "overall_pass_rate_pct": float(cases_frame["overall_pass_3pct"].mean() * 100.0) if not cases_frame.empty else 0.0,
        "temperature_mean_error_pct_kelvin": float(cases_frame["temperature_error_pct_kelvin"].mean()) if not cases_frame.empty else 0.0,
        "precipitation_mean_error_pct": float(cases_frame["precipitation_error_pct"].mean()) if not cases_frame.empty else 0.0,
        "species_mean_error_pct_proxy": float(cases_frame["species_error_pct_proxy"].mean()) if not cases_frame.empty else 0.0,
    }
    write_json(json_path, summary_payload)

    return {
        "xlsx": xlsx_path,
        "csv": csv_path,
        "json": json_path,
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

    records = []
    for index, case in enumerate(cases, start=1):
        print(f"[case {index}/{len(cases)}] {case['city']} {case['start']} -> {case['end']}", flush=True)
        case_args = build_case_args(case, args.checkpoint, args.device)
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

        predicted_summary = summarize_batch_for_area(
            result.predicted_batch_original,
            context.bounds,
            species_threshold=args.species_threshold,
        )
        observed_summary = summarize_batch_for_area(
            result.observed_batch_original,
            context.bounds,
            species_threshold=args.species_threshold,
        )

        records.append(
            build_validation_record(
                case=case,
                context=context,
                predicted_summary=predicted_summary,
                observed_summary=observed_summary,
                run_dir=context.run_dir,
                error_threshold_pct=args.error_threshold_pct,
            )
        )

    cases_frame = pd.DataFrame.from_records(records)
    by_city_frame = (
        cases_frame.groupby("city", as_index=False)
        .agg(
            case_count=("city", "count"),
            temperature_mean_abs_error_c=("temperature_abs_error_c", "mean"),
            temperature_mean_error_pct_kelvin=("temperature_error_pct_kelvin", "mean"),
            precipitation_mean_abs_error_mm=("precipitation_abs_error_mm", "mean"),
            precipitation_mean_error_pct=("precipitation_error_pct", "mean"),
            species_mean_abs_error_proxy=("species_abs_error_proxy", "mean"),
            species_mean_error_pct_proxy=("species_error_pct_proxy", "mean"),
            overall_pass_rate_pct=("overall_pass_3pct", lambda values: float(pd.Series(values).mean() * 100.0)),
        )
        .sort_values("city")
    )

    output_label = args.output_label or f"native_validation_{args.checkpoint}_{args.device}_{len(cases)}cases"
    validation_dir = resolve_forecast_output_dir(env["project_output_dir"], output_label)
    output_paths = write_validation_workbook(validation_dir, cases_frame, by_city_frame)

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
