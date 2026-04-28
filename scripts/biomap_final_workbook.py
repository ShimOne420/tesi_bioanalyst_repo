#!/usr/bin/env python3
"""Build and update the final BIOMAP workbook from native BioAnalyst runs.

Design note:
- the workbook is always the same file;
- summary sheets are cumulative across all discovered runs;
- per-feature sheets show the latest selected run in cell-by-cell detail.

Keeping every Europe-wide cell of every run for every variable inside one
single Excel workbook would exceed practical spreadsheet limits very quickly.
This module therefore keeps the workbook usable while still updating the same
artifact after each run.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_FORECAST_ROOT = REPO_ROOT / "outputs" / "local_preview" / "model_forecast"
OUT_DIR = MODEL_FORECAST_ROOT / "SINTESI_AFFIDABILITA_MODEL_FORECAST_2017_2020"
DEFAULT_WORKBOOK_PATH = OUT_DIR / "BIOMAP_FINAL_FEATURE_ANALYSIS_NATIVE_BIOANALYST.xlsx"
DEFAULT_REPORT_PATH = OUT_DIR / "REPORT_OPERATIVO_WORKBOOK_UNICO.md"

os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / ".matplotlib-cache"))

import analyze_latest_native_tests as ant  # noqa: E402


BIOMAP_FEATURES = {
    ("climate", "t2m"): ("temperature_stress", "core_forecast_indicator", "Damage/restoration climate pressure"),
    ("climate", "tp"): ("precipitation_water_stress", "secondary_diagnostic", "Hydrological stress and drought/wetness context"),
    ("climate", "d2m"): ("humidity_dewpoint", "diagnostic", "Climate stress support variable"),
    ("vegetation", "NDVI"): ("vegetation_condition", "promising_diagnostic", "Restoration greenness / vegetation condition"),
    ("forest", "Forest"): ("forest_context", "context_layer", "Forest damage/restoration context"),
    ("agriculture", "Agriculture"): ("agriculture_pressure", "context_layer", "Anthropic land pressure"),
    ("agriculture", "Cropland"): ("cropland_pressure", "context_layer", "Anthropic land pressure"),
    ("agriculture", "Arable"): ("arable_pressure", "context_layer", "Anthropic land pressure"),
    ("edaphic", "swvl1"): ("soil_water_stress", "diagnostic", "Shallow soil moisture support"),
    ("edaphic", "swvl2"): ("soil_water_stress", "diagnostic", "Deeper soil moisture support"),
    ("land", "Land"): ("land_mask_context", "technical_context", "Mask/support variable"),
    ("redlist", "RLI"): ("redlist_context", "context_layer", "Conservation-risk context"),
    ("misc", "avg_slhtf"): ("energy_balance_context", "diagnostic", "Surface latent heat flux support"),
    ("misc", "avg_pevr"): ("evaporation_context", "diagnostic", "Potential evaporation rate support"),
    ("species_proxy", "species_sum_proxy"): ("biodiversity_proxy", "exploratory", "Native species proxy, not final richness"),
    ("species_proxy", "species_count_threshold_0_1"): ("biodiversity_proxy", "exploratory", "Thresholded species-count proxy"),
    ("species_proxy", "species_count_threshold_0_5"): ("biodiversity_proxy", "exploratory", "Thresholded species-count proxy"),
}


SPECIAL_SHEET_NAMES = {
    ("climate", "t2m"): "Temperature_t2m",
    ("climate", "tp"): "Precipitation_tp",
    ("vegetation", "NDVI"): "Vegetation_NDVI",
    ("edaphic", "swvl1"): "Edaphic_swvl1",
    ("edaphic", "swvl2"): "Edaphic_swvl2",
    ("agriculture", "Cropland"): "Agriculture_Cropland",
}


MAIN_DETAIL_FEATURES = {
    ("climate", "t2m"),
    ("climate", "tp"),
    ("vegetation", "NDVI"),
    ("edaphic", "swvl1"),
    ("edaphic", "swvl2"),
    ("agriculture", "Cropland"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggiorna il workbook finale BIOMAP dal run BioAnalyst native.")
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Run da usare per i fogli di dettaglio latest-run. Se omesso usa l'ultimo run trovato.",
    )
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=MODEL_FORECAST_ROOT,
        help="Cartella radice da scansionare per i run storici.",
    )
    parser.add_argument(
        "--workbook-path",
        type=Path,
        default=DEFAULT_WORKBOOK_PATH,
        help="Workbook BIOMAP finale da aggiornare.",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="Documento operativo da aggiornare insieme al workbook.",
    )
    return parser


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_timestamp(value: str | None) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        return pd.Timestamp(value)
    except Exception:
        return None


def iter_run_dirs(root: Path) -> list[Path]:
    run_dirs: list[Path] = []
    for manifest_path in sorted(root.rglob("forecast_native_manifest.json")):
        run_dir = manifest_path.parent
        parts = set(run_dir.parts)
        if "SINTESI_AFFIDABILITA_MODEL_FORECAST_2017_2020" in parts:
            continue
        if any("analysis_report" in part for part in run_dir.parts):
            continue
        if not (run_dir / "native_prediction_original.pt").exists():
            continue
        if not (run_dir / "native_target_original.pt").exists():
            continue
        run_dirs.append(run_dir)
    run_dirs = list(dict.fromkeys(run_dirs))
    run_dirs.sort(
        key=lambda path: (
            safe_timestamp(load_json(path / "forecast_native_manifest.json").get("forecast_month")) or pd.Timestamp.max,
            path.name.lower(),
        )
    )
    return run_dirs


def workbook_sheet_name(group: str, variable: str, used_names: set[str]) -> str:
    if group == "species":
        base = f"Species_{variable}"
    else:
        base = SPECIAL_SHEET_NAMES.get((group, variable), f"{group}_{variable}")
    base = re.sub(r"[^A-Za-z0-9_]+", "_", base).strip("_") or "Sheet"
    base = base[:31]
    candidate = base
    counter = 2
    while candidate in used_names:
        suffix = f"_{counter}"
        candidate = f"{base[: 31 - len(suffix)]}{suffix}"
        counter += 1
    used_names.add(candidate)
    return candidate


def slug_text(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value)).strip("_").lower()


def detail_run_id(manifest: dict[str, Any], run_dir: Path) -> str:
    forecast_month = str(manifest.get("forecast_month") or "unknown").replace("-", "_")
    checkpoint = slug_text(manifest.get("checkpoint_kind") or "ckpt")
    input_mode = slug_text(manifest.get("input_mode") or "input")
    label = slug_text(run_label(manifest, run_dir))[:40]
    return f"{forecast_month}_{checkpoint}_{input_mode}_{label}"


def run_label(manifest: dict[str, Any], run_dir: Path) -> str:
    label = manifest.get("label") or run_dir.name
    return str(label)


def readiness(group: str, variable: str, mae: float, bias: float, corr: float, rel_mae: float) -> str:
    if (group, variable) == ("climate", "t2m"):
        if mae <= 2.0 and abs(bias) <= 1.0 and corr >= 0.90:
            return "ready_high"
        if mae <= 3.5 and abs(bias) <= 3.0 and corr >= 0.75:
            return "usable_medium"
        return "needs_calibration"
    if (group, variable) == ("climate", "tp"):
        if corr >= 0.60 and rel_mae <= 100 and abs(bias) <= 2.0:
            return "diagnostic_medium"
        return "weak_precipitation"
    if group == "species_proxy":
        return "exploratory_not_final"
    if group == "species":
        return "exploratory_species_map"
    if (group, variable) == ("vegetation", "NDVI"):
        return "diagnostic_promising" if corr >= 0.70 else "diagnostic_uncertain"
    if group in {"forest", "agriculture", "redlist"}:
        return "context_spatially_consistent" if corr >= 0.70 else "context_uncertain"
    if group in {"edaphic", "misc"}:
        return "diagnostic_spatially_consistent" if corr >= 0.75 else "diagnostic_uncertain"
    return "native_metric_only"


def add_biomap_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    domains = []
    uses = []
    interpretations = []
    statuses = []
    for _, row in output.iterrows():
        key = (row["group"], row["variable"])
        domain, use, interpretation = BIOMAP_FEATURES.get(
            key,
            ("native_bioanalyst_variable", "exploratory_native", "Use only after variable-specific validation"),
        )
        domains.append(domain)
        uses.append(use)
        interpretations.append(interpretation)
        statuses.append(
            readiness(
                row["group"],
                row["variable"],
                float(row.get("mae", math.nan)),
                float(row.get("bias", math.nan)),
                float(row.get("correlation", math.nan)),
                float(row.get("relative_mae_pct", math.nan)),
            )
        )
    output["biomap_domain"] = domains
    output["biomap_use"] = uses
    output["biomap_interpretation"] = interpretations
    output["biomap_readiness"] = statuses
    return output


def binary_scores(pred: np.ndarray, obs: np.ndarray) -> dict[str, float | int]:
    tp = int(np.logical_and(pred, obs).sum())
    fp = int(np.logical_and(pred, ~obs).sum())
    fn = int(np.logical_and(~pred, obs).sum())
    tn = int(np.logical_and(~pred, ~obs).sum())
    precision = math.nan if tp + fp == 0 else tp / (tp + fp)
    recall = math.nan if tp + fn == 0 else tp / (tp + fn)
    f1 = math.nan if 2 * tp + fp + fn == 0 else (2 * tp) / (2 * tp + fp + fn)
    jaccard = math.nan if tp + fp + fn == 0 else tp / (tp + fp + fn)
    sorensen = f1
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "jaccard_similarity": jaccard,
        "sorensen_similarity": sorensen,
    }


def continuous_scores(pred: np.ndarray, obs: np.ndarray) -> dict[str, float | int]:
    mask = np.isfinite(pred) & np.isfinite(obs)
    pred = pred[mask].astype(float)
    obs = obs[mask].astype(float)
    if pred.size == 0:
        return {
            "predicted_mean": math.nan,
            "observed_mean": math.nan,
            "mae": math.nan,
            "rmse": math.nan,
            "bias": math.nan,
            "correlation": math.nan,
            "relative_mae_pct": math.nan,
            "cell_count": 0,
        }
    diff = pred - obs
    corr = math.nan
    if pred.size > 1 and np.std(pred) > 0 and np.std(obs) > 0:
        corr = float(np.corrcoef(pred, obs)[0, 1])
    observed_abs_mean = abs(float(np.mean(obs)))
    mae = float(np.mean(np.abs(diff)))
    return {
        "predicted_mean": float(np.mean(pred)),
        "observed_mean": float(np.mean(obs)),
        "mae": mae,
        "rmse": float(np.sqrt(np.mean(diff**2))),
        "bias": float(np.mean(diff)),
        "correlation": corr,
        "relative_mae_pct": math.nan if observed_abs_mean <= 1e-12 else mae / observed_abs_mean * 100.0,
        "cell_count": int(pred.size),
    }


def compute_species_summary(runs: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for run_dir in runs:
        manifest = load_json(run_dir / "forecast_native_manifest.json")
        pred_batch = ant.load_batch(run_dir / "native_prediction_original.pt")
        obs_batch = ant.load_batch(run_dir / "native_target_original.pt")
        lat_flip, lon_flip = ant.prediction_alignment_flags(manifest)
        pred_stack = ant.species_stack(pred_batch)
        obs_stack = ant.species_stack(obs_batch)
        pred_stack = np.stack(
            [ant.align_prediction(item, latitude_flip=lat_flip, longitude_flip=lon_flip) for item in pred_stack],
            axis=0,
        )
        for threshold in [0.1, 0.5]:
            pred_bin = pred_stack >= threshold
            obs_bin = obs_stack >= threshold
            pred_richness = pred_bin.sum(axis=0)
            obs_richness = obs_bin.sum(axis=0)
            row = {
                "run_dir": str(run_dir),
                "label": run_label(manifest, run_dir),
                "forecast_month": manifest.get("forecast_month"),
                "checkpoint": manifest.get("checkpoint_kind"),
                "input_mode": manifest.get("input_mode"),
                "threshold": threshold,
                **binary_scores(pred_bin, obs_bin),
            }
            row.update({f"richness_{key}": value for key, value in continuous_scores(pred_richness.reshape(-1), obs_richness.reshape(-1)).items()})
            rows.append(row)
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["forecast_month_dt"] = pd.to_datetime(frame["forecast_month"])
        frame = frame.sort_values(["forecast_month_dt", "threshold", "label"]).drop(columns=["forecast_month_dt"])
    return frame


def load_all_metrics(runs: list[Path], current_batches: dict[Path, tuple[Any, Any, dict[str, Any]]] | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cached = current_batches or {}
    for run_dir in runs:
        if run_dir in cached:
            prediction_batch, observed_batch, manifest = cached[run_dir]
        else:
            manifest = load_json(run_dir / "forecast_native_manifest.json")
            prediction_batch = ant.load_batch(run_dir / "native_prediction_original.pt")
            observed_batch = ant.load_batch(run_dir / "native_target_original.pt")
        rows.extend(ant.variable_metrics_for_run(run_dir, prediction_batch, observed_batch, manifest))
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["forecast_month_dt"] = pd.to_datetime(frame["forecast_month"], errors="coerce")
    frame["year"] = frame["forecast_month_dt"].dt.year
    frame["month"] = frame["forecast_month_dt"].dt.month
    frame["month_name"] = frame["forecast_month_dt"].dt.strftime("%b")
    frame["feature_key"] = frame["group"].astype(str) + "." + frame["variable"].astype(str)
    frame["r2_corr_squared"] = frame["correlation"] ** 2
    frame["label"] = frame["run_dir"].map(lambda item: run_label(load_json(Path(item) / "forecast_native_manifest.json"), Path(item)))
    return add_biomap_columns(frame.sort_values(["forecast_month_dt", "group", "variable", "level_index"], na_position="last"))


def build_feature_summary(metrics: pd.DataFrame, species_metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_summary = (
        metrics.groupby(["group", "variable", "unit", "biomap_domain", "biomap_use"], dropna=False)
        .agg(
            n_runs=("run_dir", "nunique"),
            n_months=("forecast_month", "nunique"),
            predicted_mean=("predicted_mean", "mean"),
            observed_mean=("observed_mean", "mean"),
            mean_mae=("mae", "mean"),
            mean_rmse=("rmse", "mean"),
            mean_bias=("bias", "mean"),
            mean_abs_bias=("bias", lambda series: float(np.nanmean(np.abs(series)))),
            mean_corr=("correlation", "mean"),
            median_corr=("correlation", "median"),
            mean_r2_corr_squared=("r2_corr_squared", "mean"),
            mean_relative_mae_pct=("relative_mae_pct", "mean"),
            ready_or_usable_runs=("biomap_readiness", lambda series: int(series.isin([
                "ready_high",
                "usable_medium",
                "diagnostic_medium",
                "diagnostic_promising",
                "context_spatially_consistent",
                "diagnostic_spatially_consistent",
            ]).sum())),
        )
        .reset_index()
    )
    feature_summary["readiness_ratio"] = feature_summary["ready_or_usable_runs"] / feature_summary["n_runs"].replace(0, np.nan)
    feature_summary = feature_summary.sort_values(["readiness_ratio", "mean_corr"], ascending=[False, False], na_position="last")

    if species_metrics.empty:
        species_summary = pd.DataFrame()
    else:
        species_summary = (
            species_metrics.groupby("threshold")
            .agg(
                n_runs=("run_dir", "nunique"),
                n_months=("forecast_month", "nunique"),
                mean_precision=("precision", "mean"),
                mean_recall=("recall", "mean"),
                mean_f1=("f1_score", "mean"),
                mean_sorensen=("sorensen_similarity", "mean"),
                mean_jaccard=("jaccard_similarity", "mean"),
                mean_richness_mae=("richness_mae", "mean"),
                mean_richness_bias=("richness_bias", "mean"),
                mean_richness_corr=("richness_correlation", "mean"),
                mean_richness_relative_mae_pct=("richness_relative_mae_pct", "mean"),
            )
            .reset_index()
        )
    return feature_summary, species_summary


def build_indicator_map(feature_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in feature_summary.iterrows():
        if row["readiness_ratio"] >= 0.8:
            validation_state = "high_or_context_ready"
        elif row["readiness_ratio"] >= 0.4:
            validation_state = "medium_promising"
        elif row["biomap_use"] in {"context_layer", "diagnostic"}:
            validation_state = "context_or_diagnostic"
        else:
            validation_state = "exploratory"
        rows.append(
            {
                "group": row["group"],
                "variable": row["variable"],
                "biomap_domain": row["biomap_domain"],
                "biomap_use": row["biomap_use"],
                "validation_state": validation_state,
                "n_runs": row["n_runs"],
                "n_months": row["n_months"],
                "mean_mae": row["mean_mae"],
                "mean_rmse": row["mean_rmse"],
                "mean_bias": row["mean_bias"],
                "mean_corr": row["mean_corr"],
                "mean_relative_mae_pct": row["mean_relative_mae_pct"],
                "readiness_ratio": row["readiness_ratio"],
            }
        )
    return pd.DataFrame(rows).sort_values(["readiness_ratio", "mean_corr"], ascending=[False, False], na_position="last")


def coverage_from_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return pd.DataFrame(columns=["scope", "year", "run_count", "n_months", "months", "variables"])
    run_index = metrics[["run_dir", "forecast_month", "year", "group", "variable"]].drop_duplicates()
    rows = []
    for year, frame in run_index.groupby("year"):
        months = sorted(frame["forecast_month"].dropna().unique().tolist())
        variables = sorted((frame["group"] + "." + frame["variable"]).dropna().unique().tolist())
        rows.append(
            {
                "scope": "year",
                "year": int(year),
                "run_count": int(frame["run_dir"].nunique()),
                "n_months": int(len(months)),
                "months": ", ".join(months),
                "variables": ", ".join(variables[:40]) + (" ..." if len(variables) > 40 else ""),
            }
        )
    all_months = sorted(run_index["forecast_month"].dropna().unique().tolist())
    all_variables = sorted((run_index["group"] + "." + run_index["variable"]).dropna().unique().tolist())
    rows.append(
        {
            "scope": "overall",
            "year": "all",
            "run_count": int(run_index["run_dir"].nunique()),
            "n_months": int(len(all_months)),
            "months": ", ".join(all_months),
            "variables": ", ".join(all_variables[:60]) + (" ..." if len(all_variables) > 60 else ""),
        }
    )
    return pd.DataFrame(rows)


def metric_guide() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("observed", "Valore osservato/target BioCube", "per-cell latest run", "valore target sulla cella"),
            ("predicted", "Valore predetto dal modello", "per-cell latest run", "valore forecast sulla cella"),
            ("difference", "predicted - observed", "per-cell latest run", "errore con segno"),
            ("abs_error", "abs(predicted - observed)", "per-cell latest run", "errore assoluto sulla cella"),
            ("MAE", "mean(abs(predicted - observed))", "continuous variables", "errore assoluto medio"),
            ("RMSE", "sqrt(mean((predicted - observed)^2))", "continuous variables", "penalizza di piu gli errori grandi"),
            ("bias", "mean(predicted - observed)", "continuous variables", "positivo = sovrastima; negativo = sottostima"),
            ("correlation", "corr(predicted, observed)", "continuous variables", "misura il pattern, non il valore assoluto"),
            ("relative_mae_pct", "100 * MAE / abs(mean(observed))", "continuous variables", "metrica percentuale di errore"),
            ("tp", "true positives", "species binary metrics", "presenze predette e osservate"),
            ("fp", "false positives", "species binary metrics", "presenze predette ma non osservate"),
            ("fn", "false negatives", "species binary metrics", "presenze osservate ma non predette"),
            ("F1", "2TP / (2TP + FP + FN)", "species binary metrics", "equilibrio precision/recall"),
            ("Jaccard", "TP / (TP + FP + FN)", "species binary metrics", "intersezione su unione"),
            ("Sorensen", "2TP / (2TP + FP + FN)", "species binary metrics", "equivalente a Dice/F1 per insiemi binari"),
        ],
        columns=["metric", "formula", "best_for", "meaning"],
    )


def base_grid_frame(latitudes: np.ndarray, longitudes: np.ndarray, bounds: dict[str, float] | None) -> pd.DataFrame:
    latitudes = np.asarray(latitudes, dtype=np.float32)
    longitudes = np.asarray(longitudes, dtype=np.float32)
    lat_column = np.repeat(latitudes, longitudes.size).astype(np.float32)
    lon_column = np.tile(longitudes, latitudes.size).astype(np.float32)
    frame = pd.DataFrame({"lat": lat_column, "lon": lon_column})
    if bounds:
        frame["inside_selected_area"] = (
            (frame["lat"] >= float(bounds["min_lat"]))
            & (frame["lat"] <= float(bounds["max_lat"]))
            & (frame["lon"] >= float(bounds["min_lon"]))
            & (frame["lon"] <= float(bounds["max_lon"]))
        )
    return frame


def feature_binary_metrics(group: str, pred_display: np.ndarray, obs_display: np.ndarray) -> dict[str, Any]:
    if group != "species":
        return {}
    return {
        "binary_threshold": 0.5,
        **binary_scores(pred_display >= 0.5, obs_display >= 0.5),
    }


def build_feature_sheet(
    *,
    run_dir: Path,
    manifest: dict[str, Any],
    prediction_batch: Any,
    observed_batch: Any,
    group: str,
    variable: str,
) -> pd.DataFrame:
    latitudes = ant.as_1d(prediction_batch.batch_metadata.latitudes)
    longitudes = ant.as_1d(prediction_batch.batch_metadata.longitudes)
    bounds = manifest.get("bounds")
    lat_flip, lon_flip = ant.prediction_alignment_flags(manifest)

    pred_group = ant.get_group(prediction_batch, group)
    obs_group = ant.get_group(observed_batch, group)
    pred_tensor = pred_group[variable]
    obs_tensor = obs_group[variable]

    frames: list[pd.DataFrame] = []
    pred_maps = ant.selected_maps(pred_tensor)
    obs_maps = ant.selected_maps(obs_tensor)
    metadata = {
        "run_dir": str(run_dir),
        "label": run_label(manifest, run_dir),
        "forecast_month": manifest.get("forecast_month"),
        "checkpoint": manifest.get("checkpoint_kind"),
        "input_mode": manifest.get("input_mode"),
        "group": group,
        "variable": variable,
        "source_status": manifest.get("group_source_status", {}).get(group),
    }

    for (level_index, pred_map_native), (_, obs_map_native) in zip(pred_maps, obs_maps):
        pred_map_native = ant.align_prediction(pred_map_native, latitude_flip=lat_flip, longitude_flip=lon_flip)
        pred_display, unit = ant.convert_display_values(variable, pred_map_native)
        obs_display, _ = ant.convert_display_values(variable, obs_map_native)
        metrics = ant.compute_metrics(pred_display, obs_display)
        binary_metrics = feature_binary_metrics(group, pred_display, obs_display)

        frame = base_grid_frame(latitudes, longitudes, bounds)
        frame["observed"] = obs_display.reshape(-1).astype(np.float32)
        frame["predicted"] = pred_display.reshape(-1).astype(np.float32)
        frame["difference"] = (pred_display - obs_display).reshape(-1).astype(np.float32)
        frame["abs_error"] = np.abs(frame["difference"]).astype(np.float32)
        frame["unit"] = unit
        frame["level_index"] = level_index
        frame["pressure_level"] = ant.pressure_level_label(prediction_batch, level_index)
        for key, value in metadata.items():
            frame[key] = value
        for key, value in metrics.items():
            frame[key] = value
        frame["biomap_readiness"] = readiness(group, variable, metrics["mae"], metrics["bias"], metrics["correlation"], metrics["relative_mae_pct"])
        if binary_metrics:
            for key, value in binary_metrics.items():
                frame[key] = value
        frames.append(frame)

    output = pd.concat(frames, ignore_index=True)
    lead_columns = [
        "forecast_month",
        "label",
        "group",
        "variable",
        "unit",
        "lat",
        "lon",
        "inside_selected_area",
        "level_index",
        "pressure_level",
        "observed",
        "predicted",
        "difference",
        "abs_error",
        "mae",
        "rmse",
        "bias",
        "correlation",
        "relative_mae_pct",
        "biomap_readiness",
        "checkpoint",
        "input_mode",
        "source_status",
        "run_dir",
    ]
    extra_columns = [column for column in output.columns if column not in lead_columns]
    return output[lead_columns + extra_columns]


def build_latest_feature_sheets(
    *,
    run_dirs: list[Path],
    current_run_dir: Path,
    current_manifest: dict[str, Any],
    current_prediction_batch: Any,
    current_observed_batch: Any,
) -> OrderedDict[str, pd.DataFrame]:
    used_names: set[str] = {
        "Dashboard_BIOMAP",
        "BIOMAP_Indicator_Map",
        "Coverage",
        "Metric_Guide",
        "All_Variables",
        "Species_Biodiversity",
    }
    detail_specs: list[tuple[str, str, str]] = []
    current_species = ant.get_group(current_prediction_batch, "species")
    for group_name, variable in sorted(MAIN_DETAIL_FEATURES):
        pred_group = ant.get_group(current_prediction_batch, group_name)
        obs_group = ant.get_group(current_observed_batch, group_name)
        if variable in pred_group and variable in obs_group:
            detail_specs.append((workbook_sheet_name(group_name, variable, used_names), group_name, variable))
    for variable in sorted(current_species):
        detail_specs.append((workbook_sheet_name("species", variable, used_names), "species", variable))

    base_bounds = current_manifest.get("bounds")
    base_latitudes = ant.as_1d(current_prediction_batch.batch_metadata.latitudes)
    base_longitudes = ant.as_1d(current_prediction_batch.batch_metadata.longitudes)
    base_sheet_frames: OrderedDict[str, pd.DataFrame] = OrderedDict()
    sheet_meta: dict[str, tuple[str, str]] = {}
    for sheet_name, group_name, variable in detail_specs:
        pred_group = ant.get_group(current_prediction_batch, group_name)
        pred_tensor = pred_group[variable]
        pred_maps = ant.selected_maps(pred_tensor)
        unit = ant.convert_display_values(variable, pred_maps[0][1])[1]
        frame = base_grid_frame(base_latitudes, base_longitudes, base_bounds)
        frame["group"] = group_name
        frame["variable"] = variable
        frame["unit"] = unit
        base_sheet_frames[sheet_name] = frame
        sheet_meta[sheet_name] = (group_name, variable)

    cached_batches: dict[Path, tuple[Any, Any, dict[str, Any]]] = {
        current_run_dir: (current_prediction_batch, current_observed_batch, current_manifest)
    }
    total_runs = len(run_dirs)
    for run_index, run_dir in enumerate(run_dirs, start=1):
        print(f"[workbook] Preparo colonne cumulativi dal run {run_index}/{total_runs}: {run_dir.name}", flush=True)
        if run_dir in cached_batches:
            prediction_batch, observed_batch, manifest = cached_batches[run_dir]
        else:
            manifest = load_json(run_dir / "forecast_native_manifest.json")
            prediction_batch = ant.load_batch(run_dir / "native_prediction_original.pt")
            observed_batch = ant.load_batch(run_dir / "native_target_original.pt")
            cached_batches[run_dir] = (prediction_batch, observed_batch, manifest)

        latitudes = ant.as_1d(prediction_batch.batch_metadata.latitudes)
        longitudes = ant.as_1d(prediction_batch.batch_metadata.longitudes)
        if latitudes.shape != base_latitudes.shape or longitudes.shape != base_longitudes.shape:
            continue
        if not np.allclose(latitudes, base_latitudes) or not np.allclose(longitudes, base_longitudes):
            continue

        run_id = detail_run_id(manifest, run_dir)
        lat_flip, lon_flip = ant.prediction_alignment_flags(manifest)
        for sheet_name, frame in base_sheet_frames.items():
            group_name, variable = sheet_meta[sheet_name]
            pred_group = ant.get_group(prediction_batch, group_name)
            obs_group = ant.get_group(observed_batch, group_name)
            if variable not in pred_group or variable not in obs_group:
                continue
            pred_map_native = ant.selected_maps(pred_group[variable])[0][1]
            obs_map_native = ant.selected_maps(obs_group[variable])[0][1]
            pred_map_native = ant.align_prediction(pred_map_native, latitude_flip=lat_flip, longitude_flip=lon_flip)
            pred_display, _ = ant.convert_display_values(variable, pred_map_native)
            obs_display, _ = ant.convert_display_values(variable, obs_map_native)
            metrics = ant.compute_metrics(pred_display, obs_display)

            frame[f"observed__{run_id}"] = obs_display.reshape(-1).astype(np.float32)
            frame[f"predicted__{run_id}"] = pred_display.reshape(-1).astype(np.float32)
            frame[f"difference__{run_id}"] = (pred_display - obs_display).reshape(-1).astype(np.float32)
            frame[f"abs_error__{run_id}"] = np.abs(pred_display - obs_display).reshape(-1).astype(np.float32)
            frame[f"mae__{run_id}"] = metrics["mae"]
            frame[f"rmse__{run_id}"] = metrics["rmse"]
            frame[f"bias__{run_id}"] = metrics["bias"]
            frame[f"correlation__{run_id}"] = metrics["correlation"]
            frame[f"relative_mae_pct__{run_id}"] = metrics["relative_mae_pct"]
            frame[f"biomap_readiness__{run_id}"] = readiness(
                group_name,
                variable,
                metrics["mae"],
                metrics["bias"],
                metrics["correlation"],
                metrics["relative_mae_pct"],
            )

            if group_name == "species":
                binary = feature_binary_metrics(group_name, pred_display, obs_display)
                frame[f"tp__{run_id}"] = binary["tp"]
                frame[f"fp__{run_id}"] = binary["fp"]
                frame[f"fn__{run_id}"] = binary["fn"]
                frame[f"tn__{run_id}"] = binary["tn"]
                frame[f"precision__{run_id}"] = binary["precision"]
                frame[f"recall__{run_id}"] = binary["recall"]
                frame[f"f1_score__{run_id}"] = binary["f1_score"]
                frame[f"jaccard_similarity__{run_id}"] = binary["jaccard_similarity"]
                frame[f"sorensen_similarity__{run_id}"] = binary["sorensen_similarity"]

    return base_sheet_frames


def write_workbook(path: Path, sheets: OrderedDict[str, pd.DataFrame]) -> Path:
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Font, PatternFill

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.stem}.tmp.xlsx")
    workbook = Workbook(write_only=True)
    header_fill = PatternFill("solid", fgColor="17324D")
    header_font = Font(color="FFFFFF", bold=True)
    total_sheets = len(sheets)

    for sheet_index, (sheet_name, frame) in enumerate(sheets.items(), start=1):
        print(
            f"[workbook] Scrivo foglio {sheet_index}/{total_sheets}: {sheet_name} "
            f"({len(frame):,} righe x {len(frame.columns):,} colonne)",
            flush=True,
        )
        worksheet = workbook.create_sheet(title=sheet_name[:31])
        header_row = []
        for column_name in frame.columns:
            cell = WriteOnlyCell(worksheet, value=column_name)
            cell.fill = header_fill
            cell.font = header_font
            header_row.append(cell)
        worksheet.append(header_row)

        for row_index, row in enumerate(frame.itertuples(index=False, name=None), start=1):
            values = []
            for value in row:
                if isinstance(value, pd.Timestamp):
                    values.append(value.strftime("%Y-%m-%d"))
                elif pd.isna(value):
                    values.append(None)
                else:
                    values.append(value)
            worksheet.append(values)
            if row_index % 10000 == 0:
                print(
                    f"[workbook]   {sheet_name}: {row_index:,}/{len(frame):,} righe scritte",
                    flush=True,
                )
    workbook.save(temp_path)
    try:
        temp_path.replace(path)
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        temp_path.replace(fallback)
        return fallback


def write_operational_report(
    *,
    path: Path,
    workbook_path: Path,
    latest_run_dir: Path,
    latest_manifest: dict[str, Any],
    metrics: pd.DataFrame,
    feature_sheets: OrderedDict[str, pd.DataFrame],
) -> None:
    feature_count = int(metrics[["group", "variable"]].drop_duplicates().shape[0]) if not metrics.empty else 0
    months = ", ".join(sorted(metrics["forecast_month"].dropna().unique().tolist())) if not metrics.empty else ""
    lines = [
        "# Report operativo workbook unico BIOMAP",
        "",
        "## Cosa fa ora la pipeline",
        "",
        "- aggiorna sempre lo stesso workbook finale BIOMAP;",
        "- mantiene fogli cumulativi di sintesi (`Coverage`, `Metric_Guide`, `Dashboard_BIOMAP`, `BIOMAP_Indicator_Map`, `All_Variables`, `Species_Biodiversity`);",
        "- aggiorna i fogli di dettaglio cella-per-cella nello stesso workbook, aggiungendo nuovi dati run-per-run solo per le variabili principali BIOMAP e per tutte le specie native;",
        "- conserva i plot PNG del singolo run gia creati dalla pipeline forecast.",
        "",
        "## Scelta tecnica adottata",
        "",
        "Nei fogli di dettaglio le righe restano ancorate alla griglia `lat/lon`, mentre ogni nuovo run aggiunge nuove colonne `observed__...`, `predicted__...`, `difference__...`, `MAE__...`, `RMSE__...`, `bias__...`, `correlation__...`, `relative_mae_pct__...`.",
        "",
        "La parte storica completa resta anche nei fogli di sintesi. L'aggiunta per colonne, invece che per nuove righe a ogni run, evita di superare troppo presto i limiti pratici di Excel sui test Europe-wide.",
        "",
        "Variabili principali incluse nei fogli di dettaglio:",
        "- `Temperature_t2m`",
        "- `Precipitation_tp`",
        "- `Vegetation_NDVI`",
        "- `Edaphic_swvl1`",
        "- `Edaphic_swvl2`",
        "- `Agriculture_Cropland`",
        "- piu un foglio `Species_<id>` per ogni specie nativa disponibile",
        "",
        "## Run corrente usato come riferimento della griglia",
        "",
        f"- run_dir: `{latest_run_dir}`",
        f"- label: `{run_label(latest_manifest, latest_run_dir)}`",
        f"- forecast_month: `{latest_manifest.get('forecast_month')}`",
        f"- checkpoint: `{latest_manifest.get('checkpoint_kind')}`",
        f"- input_mode: `{latest_manifest.get('input_mode')}`",
        "",
        "## Copertura cumulativa attuale",
        "",
        f"- mesi presenti nelle metriche cumulative: `{months}`",
        f"- feature distinte nelle metriche cumulative: `{feature_count}`",
        f"- fogli di dettaglio creati/aggiornati: `{len(feature_sheets)}`",
        f"- workbook scritto in: `{workbook_path}`",
        "",
        "## Prossimi step consigliati",
        "",
        "1. Agganciare anche l'export tabellare multi-feature del singolo run dentro `exports/reliable_features/`.",
        "2. Valutare un archivio CSV/Parquet storico cella-per-cella fuori da Excel, cosi da tenere storico completo senza limiti di workbook.",
        "3. Migliorare i fogli specie con metriche threshold-specific piu esplicite per singola specie, se ti serve una lettura biologica piu fine.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def update_biomap_final_workbook(
    *,
    current_run_dir: Path | None = None,
    prediction_batch: Any | None = None,
    observed_batch: Any | None = None,
    manifest: dict[str, Any] | None = None,
    runs_root: Path = MODEL_FORECAST_ROOT,
    workbook_path: Path | None = DEFAULT_WORKBOOK_PATH,
    report_path: Path | None = DEFAULT_REPORT_PATH,
) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    workbook_path = workbook_path or DEFAULT_WORKBOOK_PATH
    report_path = report_path or DEFAULT_REPORT_PATH
    print(f"[workbook] Scansiono run storici in: {runs_root}", flush=True)
    run_dirs = iter_run_dirs(runs_root)
    if current_run_dir is not None and current_run_dir not in run_dirs:
        run_dirs.append(current_run_dir)
        run_dirs.sort(
            key=lambda path: (
                safe_timestamp(load_json(path / "forecast_native_manifest.json").get("forecast_month")) or pd.Timestamp.max,
                path.name.lower(),
            )
        )
    if not run_dirs:
        raise RuntimeError(f"Nessun run valido trovato sotto {runs_root}")
    print(f"[workbook] Run validi trovati: {len(run_dirs)}", flush=True)

    if current_run_dir is None:
        current_run_dir = run_dirs[-1]
    if manifest is None:
        manifest = load_json(current_run_dir / "forecast_native_manifest.json")
    if prediction_batch is None:
        prediction_batch = ant.load_batch(current_run_dir / "native_prediction_original.pt")
    if observed_batch is None:
        observed_batch = ant.load_batch(current_run_dir / "native_target_original.pt")

    cached_batches = {current_run_dir: (prediction_batch, observed_batch, manifest)}
    print("[workbook] Calcolo metriche cumulative", flush=True)
    all_metrics = load_all_metrics(run_dirs, current_batches=cached_batches)
    print("[workbook] Calcolo metriche specie", flush=True)
    species_metrics = compute_species_summary(run_dirs)
    print("[workbook] Costruisco fogli di sintesi", flush=True)
    feature_summary, species_summary = build_feature_summary(all_metrics, species_metrics)
    indicator_map = build_indicator_map(feature_summary)
    print("[workbook] Costruisco fogli di dettaglio", flush=True)
    detail_sheets = build_latest_feature_sheets(
        run_dirs=run_dirs,
        current_run_dir=current_run_dir,
        current_manifest=manifest,
        current_prediction_batch=prediction_batch,
        current_observed_batch=observed_batch,
    )

    sheets: OrderedDict[str, pd.DataFrame] = OrderedDict()
    sheets["Dashboard_BIOMAP"] = feature_summary
    sheets["BIOMAP_Indicator_Map"] = indicator_map
    sheets["Coverage"] = coverage_from_metrics(all_metrics)
    sheets["Metric_Guide"] = metric_guide()
    sheets["Species_Biodiversity"] = species_metrics
    sheets["All_Variables"] = all_metrics
    for name, frame in detail_sheets.items():
        sheets[name] = frame

    all_metrics.to_csv(OUT_DIR / "biomap_final_all_metrics.csv", index=False, encoding="utf-8-sig")
    species_metrics.to_csv(OUT_DIR / "biomap_final_species_metrics.csv", index=False, encoding="utf-8-sig")
    feature_summary.to_csv(OUT_DIR / "biomap_final_feature_readiness.csv", index=False, encoding="utf-8-sig")
    indicator_map.to_csv(OUT_DIR / "biomap_final_indicator_map.csv", index=False, encoding="utf-8-sig")
    if not species_summary.empty:
        species_summary.to_csv(OUT_DIR / "biomap_final_species_summary.csv", index=False, encoding="utf-8-sig")

    print("[workbook] Scrittura workbook Excel", flush=True)
    written_workbook = write_workbook(workbook_path, sheets)
    print(f"[workbook] Workbook scritto: {written_workbook}", flush=True)
    write_operational_report(
        path=report_path,
        workbook_path=written_workbook,
        latest_run_dir=current_run_dir,
        latest_manifest=manifest,
        metrics=all_metrics,
        feature_sheets=detail_sheets,
    )
    return {
        "workbook": str(written_workbook),
        "report": str(report_path),
        "runs_used": len(run_dirs),
        "latest_run": str(current_run_dir),
        "detail_sheet_count": len(detail_sheets),
        "summary_sheet_count": 6,
    }


def main() -> None:
    args = build_parser().parse_args()
    result = update_biomap_final_workbook(
        current_run_dir=args.run_dir.resolve() if args.run_dir else None,
        runs_root=args.runs_root.resolve(),
        workbook_path=args.workbook_path.resolve(),
        report_path=args.report_path.resolve(),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
