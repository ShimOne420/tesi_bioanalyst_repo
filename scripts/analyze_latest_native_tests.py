#!/usr/bin/env python3
"""Analizza i run stagionali BioAnalyst native e crea report leggibili.

Lo script e' volutamente separato dal runner del modello:
- non modifica i .pt nativi;
- applica il riallineamento nord-sud solo alle prediction usate per export/metriche;
- crea CSV con separatore `;` e decimale `,`, piu comodi per Excel in locale italiano;
- produce tabelle, grafici e un report Markdown per i test selezionati.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import types
from collections import namedtuple
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch


GROUP_FIELDS = {
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

CORE_VARIABLES = {
    ("climate", "t2m"): "Temperatura 2m",
    ("climate", "tp"): "Precipitazione totale",
    ("climate", "d2m"): "Dew point 2m",
    ("vegetation", "ndvi"): "NDVI / vegetation proxy",
    ("forest", "forest"): "Forest proxy",
    ("agriculture", "agriculture"): "Agriculture proxy",
}


def install_pickle_compat_modules() -> None:
    """Permette di leggere i Batch .pt senza importare tutto bfm-model."""
    if "bfm_model.bfm.dataloader_monthly" in sys.modules:
        return

    bfm_model = types.ModuleType("bfm_model")
    bfm = types.ModuleType("bfm_model.bfm")
    dataloader = types.ModuleType("bfm_model.bfm.dataloader_monthly")
    batch = namedtuple(
        "Batch",
        [
            "batch_metadata",
            "surface_variables",
            "edaphic_variables",
            "atmospheric_variables",
            "climate_variables",
            "species_variables",
            "vegetation_variables",
            "land_variables",
            "agriculture_variables",
            "forest_variables",
            "redlist_variables",
            "misc_variables",
        ],
        module="bfm_model.bfm.dataloader_monthly",
    )
    metadata = namedtuple(
        "Metadata",
        ["latitudes", "longitudes", "timestamp", "lead_time", "pressure_levels", "species_list"],
        module="bfm_model.bfm.dataloader_monthly",
    )
    dataloader.Batch = batch
    dataloader.Metadata = metadata
    sys.modules["bfm_model"] = bfm_model
    sys.modules["bfm_model.bfm"] = bfm
    sys.modules["bfm_model.bfm.dataloader_monthly"] = dataloader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analizza test BioAnalyst native e crea report leggibili.")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path("outputs/local_preview/model_forecast/ultimi test"),
        help="Cartella che contiene i run stagionali.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Cartella report finale. Default: base-dir/analysis_report_<anno|all>.",
    )
    parser.add_argument(
        "--forecast-year",
        type=int,
        default=None,
        help="Include solo i run il cui forecast_month appartiene a questo anno.",
    )
    parser.add_argument(
        "--include-large",
        action="store_true",
        help="Include anche eventuali run large nelle metriche complete.",
    )
    return parser


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_batch(path: Path):
    install_pickle_compat_modules()
    return torch.load(path, map_location="cpu", weights_only=False)


def as_1d(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    array = np.asarray(value, dtype=np.float32)
    if array.ndim > 1:
        array = array[0]
    return array


def tensor_to_numpy(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        return value.detach().cpu().numpy()
    return np.asarray(value)


def selected_maps(tensor: torch.Tensor, *, time_index: int = -1) -> list[tuple[int | None, np.ndarray]]:
    """Estrae mappe 2D. Per atmospheric restituisce una mappa per livello."""
    array = tensor_to_numpy(tensor)
    if array.ndim == 2:
        return [(None, array.astype(np.float32))]
    if array.ndim == 3:
        return [(None, array[time_index].astype(np.float32))]
    if array.ndim == 4:
        return [(None, array[0, time_index].astype(np.float32))]
    if array.ndim == 5:
        return [(level, array[0, time_index, level].astype(np.float32)) for level in range(array.shape[2])]
    raise ValueError(f"Shape non supportata: {array.shape}")


def prediction_alignment_flags(manifest: dict[str, Any]) -> tuple[bool, bool]:
    spatial = manifest.get("spatial_alignment", {})
    return (
        bool(spatial.get("prediction_latitude_flip_applied", False)),
        bool(spatial.get("prediction_longitude_flip_applied", False)),
    )


def align_prediction(map_values: np.ndarray, *, latitude_flip: bool, longitude_flip: bool) -> np.ndarray:
    aligned = np.asarray(map_values)
    if latitude_flip:
        aligned = np.flip(aligned, axis=-2)
    if longitude_flip:
        aligned = np.flip(aligned, axis=-1)
    return aligned.copy()


def convert_display_values(variable: str, values: np.ndarray) -> tuple[np.ndarray, str]:
    """Conversioni minime per leggere le variabili chiave."""
    values = values.astype(np.float32)
    if variable in {"t2m", "d2m"}:
        return values - 273.15, "degC"
    if variable == "tp":
        return values * 1000.0, "mm"
    return values, "native"


def finite_metric_values(predicted: np.ndarray, observed: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(predicted) & np.isfinite(observed)
    return predicted[mask].astype(np.float64), observed[mask].astype(np.float64)


def compute_metrics(predicted: np.ndarray, observed: np.ndarray) -> dict[str, Any]:
    pred, obs = finite_metric_values(predicted, observed)
    if pred.size == 0:
        return {
            "cell_count": 0,
            "predicted_mean": math.nan,
            "observed_mean": math.nan,
            "mae": math.nan,
            "rmse": math.nan,
            "bias": math.nan,
            "correlation": math.nan,
            "predicted_min": math.nan,
            "predicted_max": math.nan,
            "observed_min": math.nan,
            "observed_max": math.nan,
            "relative_mae_pct": math.nan,
        }
    diff = pred - obs
    corr = math.nan
    if pred.size > 1 and float(np.std(pred)) > 0.0 and float(np.std(obs)) > 0.0:
        corr = float(np.corrcoef(pred, obs)[0, 1])
    observed_abs_mean = float(abs(np.mean(obs)))
    mae = float(np.mean(np.abs(diff)))
    return {
        "cell_count": int(pred.size),
        "predicted_mean": float(np.mean(pred)),
        "observed_mean": float(np.mean(obs)),
        "mae": mae,
        "rmse": float(np.sqrt(np.mean(np.square(diff)))),
        "bias": float(np.mean(diff)),
        "correlation": corr,
        "predicted_min": float(np.min(pred)),
        "predicted_max": float(np.max(pred)),
        "observed_min": float(np.min(obs)),
        "observed_max": float(np.max(obs)),
        "relative_mae_pct": math.nan if observed_abs_mean < 1e-12 else float(mae / observed_abs_mean * 100.0),
    }


def reliability_label(group: str, variable: str, metrics: dict[str, Any]) -> str:
    mae = metrics.get("mae", math.nan)
    corr = metrics.get("correlation", math.nan)
    rel = metrics.get("relative_mae_pct", math.nan)
    if group == "climate" and variable == "t2m":
        if mae <= 2.0 and corr >= 0.9:
            return "alta"
        if mae <= 3.0 and corr >= 0.75:
            return "buona"
        if mae <= 5.0 and corr >= 0.5:
            return "media"
        return "bassa"
    if group == "climate" and variable == "tp":
        if corr >= 0.7 and rel <= 50:
            return "media-alta"
        if corr >= 0.4 and rel <= 100:
            return "media"
        return "bassa"
    if group == "species_proxy":
        if corr >= 0.7 and rel <= 50:
            return "promettente"
        if corr >= 0.4:
            return "da verificare"
        return "debole"
    if corr >= 0.8 and rel <= 25:
        return "buona"
    if corr >= 0.5:
        return "media"
    return "bassa/diagnostica"


def get_group(batch, group_name: str) -> dict[str, torch.Tensor]:
    return getattr(batch, GROUP_FIELDS[group_name])


def pressure_level_label(batch, level_index: int | None) -> str | None:
    if level_index is None:
        return None
    levels = getattr(batch.batch_metadata, "pressure_levels", [])
    if hasattr(levels, "detach"):
        levels = levels.detach().cpu().numpy().tolist()
    try:
        return str(levels[level_index])
    except Exception:
        return str(level_index)


def read_runs(base_dir: Path, include_large: bool, forecast_year: int | None = None) -> list[Path]:
    runs_by_month: dict[str, Path] = {}
    for manifest_path in sorted(base_dir.glob("*/forecast_native_manifest.json")):
        run_dir = manifest_path.parent
        manifest = load_json(manifest_path)
        if manifest.get("checkpoint_kind") != "small" and not include_large:
            continue
        if forecast_year is not None:
            forecast_month = manifest.get("forecast_month")
            if not forecast_month:
                continue
            if pd.Timestamp(forecast_month).year != forecast_year:
                continue
        if not (run_dir / "native_prediction_original.pt").exists():
            continue
        if not (run_dir / "native_target_original.pt").exists():
            continue
        forecast_month = manifest.get("forecast_month", "")
        existing = runs_by_month.get(forecast_month)
        if existing is None:
            runs_by_month[forecast_month] = run_dir
            continue
        if existing.name.endswith(" 4") and not run_dir.name.endswith(" 4"):
            runs_by_month[forecast_month] = run_dir
    return sorted(runs_by_month.values(), key=lambda path: load_json(path / "forecast_native_manifest.json").get("forecast_month", ""))


def describe_run_selection(runs: list[Path]) -> str:
    months = [pd.Timestamp(load_json(run / "forecast_native_manifest.json").get("forecast_month")) for run in runs]
    if not months:
        return "nessun run"
    years = sorted({month.year for month in months})
    month_labels = ", ".join(month.strftime("%Y-%m") for month in sorted(months))
    year_label = ", ".join(str(year) for year in years)
    return f"{len(runs)} run selezionati, anno/i {year_label}: {month_labels}"


def build_grid_frame(batch) -> pd.DataFrame:
    latitudes = as_1d(batch.batch_metadata.latitudes)
    longitudes = as_1d(batch.batch_metadata.longitudes)
    rows = []
    for lat_index, lat in enumerate(latitudes):
        for lon_index, lon in enumerate(longitudes):
            rows.append({"lat_index": lat_index, "lon_index": lon_index, "lat": float(lat), "lon": float(lon)})
    return pd.DataFrame.from_records(rows)


def build_group_frame(batch, group_name: str, *, latitude_flip: bool = False, longitude_flip: bool = False) -> pd.DataFrame:
    frame = build_grid_frame(batch)
    group = get_group(batch, group_name)
    for variable, tensor in sorted(group.items()):
        for level_index, native_map in selected_maps(tensor):
            if latitude_flip or longitude_flip:
                native_map = align_prediction(native_map, latitude_flip=latitude_flip, longitude_flip=longitude_flip)
            suffix = "native" if level_index is None else f"level_{pressure_level_label(batch, level_index)}_native"
            frame[f"{variable}_{suffix}"] = native_map.reshape(-1)
    return frame


def write_excel_it_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, sep=";", decimal=",", encoding="utf-8-sig")


def create_readable_group_exports(run_dir: Path, prediction_batch, observed_batch, manifest: dict[str, Any]) -> list[Path]:
    lat_flip, lon_flip = prediction_alignment_flags(manifest)
    export_root = run_dir / "exports"
    readable_pred_dir = export_root / "bioanalyst_native_full_output_group_csv_excel_it_aligned" / "prediction"
    readable_obs_dir = export_root / "bioanalyst_native_full_output_group_csv_excel_it_aligned" / "observed"
    written: list[Path] = []
    for group_name in GROUP_FIELDS:
        pred_frame = build_group_frame(prediction_batch, group_name, latitude_flip=lat_flip, longitude_flip=lon_flip)
        obs_frame = build_group_frame(observed_batch, group_name, latitude_flip=False, longitude_flip=False)
        pred_path = readable_pred_dir / f"{group_name}_variables_grid_excel_it.csv"
        obs_path = readable_obs_dir / f"{group_name}_variables_grid_excel_it.csv"
        write_excel_it_csv(pred_frame, pred_path)
        write_excel_it_csv(obs_frame, obs_path)
        written.extend([pred_path, obs_path])

    readme = export_root / "bioanalyst_native_full_output_group_csv_excel_it_aligned" / "README_LEGGIMI.md"
    readme.write_text(
        "# CSV leggibili in Excel italiano\n\n"
        "Questa cartella contiene copie derivate dei CSV nativi con separatore `;` e decimale `,`.\n\n"
        "- `prediction/`: valori predetti, con riallineamento nord-sud applicato se dichiarato nel manifest.\n"
        "- `observed/`: valori osservati/target, senza flip.\n\n"
        "I file `.pt` originali non sono stati modificati.\n",
        encoding="utf-8",
    )
    written.append(readme)
    return written


def variable_metrics_for_run(run_dir: Path, prediction_batch, observed_batch, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    lat_flip, lon_flip = prediction_alignment_flags(manifest)
    forecast_month = manifest.get("forecast_month")
    checkpoint = manifest.get("checkpoint_kind")
    input_mode = manifest.get("input_mode")
    group_status = manifest.get("group_source_status", {})
    rows: list[dict[str, Any]] = []
    for group_name in GROUP_FIELDS:
        pred_group = get_group(prediction_batch, group_name)
        obs_group = get_group(observed_batch, group_name)
        for variable, pred_tensor in sorted(pred_group.items()):
            if variable not in obs_group:
                continue
            pred_maps = selected_maps(pred_tensor)
            obs_maps = selected_maps(obs_group[variable])
            for (level_index, pred_map), (_, obs_map) in zip(pred_maps, obs_maps):
                pred_map = align_prediction(pred_map, latitude_flip=lat_flip, longitude_flip=lon_flip)
                pred_display, unit = convert_display_values(variable, pred_map)
                obs_display, _ = convert_display_values(variable, obs_map)
                metrics = compute_metrics(pred_display, obs_display)
                rows.append(
                    {
                        "run_dir": str(run_dir),
                        "forecast_month": forecast_month,
                        "checkpoint": checkpoint,
                        "input_mode": input_mode,
                        "group": group_name,
                        "variable": variable,
                        "level_index": level_index,
                        "pressure_level": pressure_level_label(prediction_batch, level_index),
                        "unit": unit,
                        "source_status": group_status.get(group_name),
                        "reliability": reliability_label(group_name, variable, metrics),
                        **metrics,
                    }
                )
    rows.extend(species_proxy_metrics(run_dir, prediction_batch, observed_batch, manifest))
    return rows


def species_stack(batch) -> np.ndarray:
    maps = []
    for _, tensor in sorted(get_group(batch, "species").items()):
        maps.append(selected_maps(tensor)[0][1])
    return np.stack(maps, axis=0).astype(np.float32)


def species_proxy_metrics(run_dir: Path, prediction_batch, observed_batch, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    lat_flip, lon_flip = prediction_alignment_flags(manifest)
    pred_stack = species_stack(prediction_batch)
    obs_stack = species_stack(observed_batch)
    pred_stack = np.stack(
        [align_prediction(item, latitude_flip=lat_flip, longitude_flip=lon_flip) for item in pred_stack],
        axis=0,
    )
    pred_sum = np.sum(pred_stack, axis=0)
    obs_sum = np.sum(obs_stack, axis=0)
    pred_count_05 = np.sum(pred_stack >= 0.5, axis=0)
    obs_count_05 = np.sum(obs_stack >= 0.5, axis=0)
    pred_count_01 = np.sum(pred_stack >= 0.1, axis=0)
    obs_count_01 = np.sum(obs_stack >= 0.1, axis=0)
    rows = []
    for variable, pred_map, obs_map, unit in [
        ("species_sum_proxy", pred_sum, obs_sum, "species_native_sum"),
        ("species_count_threshold_0_5", pred_count_05, obs_count_05, "species_count"),
        ("species_count_threshold_0_1", pred_count_01, obs_count_01, "species_count"),
    ]:
        metrics = compute_metrics(pred_map, obs_map)
        rows.append(
            {
                "run_dir": str(run_dir),
                "forecast_month": manifest.get("forecast_month"),
                "checkpoint": manifest.get("checkpoint_kind"),
                "input_mode": manifest.get("input_mode"),
                "group": "species_proxy",
                "variable": variable,
                "level_index": None,
                "pressure_level": None,
                "unit": unit,
                "source_status": manifest.get("group_source_status", {}).get("species"),
                "reliability": reliability_label("species_proxy", variable, metrics),
                **metrics,
            }
        )
    return rows


def month_label(value: str) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def chart_line(
    frame: pd.DataFrame,
    *,
    output_path: Path,
    title: str,
    y_columns: list[str],
    ylabel: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chart_frame = frame.sort_values("forecast_month").copy()
    x = [month_label(item) for item in chart_frame["forecast_month"]]
    plt.figure(figsize=(10, 5))
    for column in y_columns:
        plt.plot(x, chart_frame[column], marker="o", linewidth=2, label=column)
    plt.title(title)
    plt.xlabel("Forecast month")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def chart_bar(
    frame: pd.DataFrame,
    *,
    output_path: Path,
    title: str,
    value_column: str,
    ylabel: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chart_frame = frame.sort_values("forecast_month").copy()
    labels = [month_label(item) for item in chart_frame["forecast_month"]]
    plt.figure(figsize=(10, 5))
    plt.bar(labels, chart_frame[value_column], color="#476A6F")
    plt.title(title)
    plt.xlabel("Forecast month")
    plt.ylabel(ylabel)
    plt.grid(True, axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def chart_metric_by_variable(
    frame: pd.DataFrame,
    *,
    output_path: Path,
    title: str,
    value_column: str,
    ylabel: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    chart_frame = frame.sort_values("forecast_month").copy()
    chart_frame["series_label"] = chart_frame["group"] + "." + chart_frame["variable"]
    x_values = sorted(chart_frame["forecast_month"].dropna().unique())
    x_labels = [month_label(item) for item in x_values]
    plt.figure(figsize=(11, 5.5))
    for label, subframe in chart_frame.groupby("series_label"):
        subframe = subframe.set_index("forecast_month").reindex(x_values)
        plt.plot(x_labels, subframe[value_column], marker="o", linewidth=2, label=label)
    plt.title(title)
    plt.xlabel("Forecast month")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.25)
    plt.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def write_analysis_workbook(output_path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path) as writer:
        for sheet_name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)


def create_report(
    *,
    output_dir: Path,
    runs: list[Path],
    all_metrics: pd.DataFrame,
    core_metrics: pd.DataFrame,
    readable_paths: list[Path],
    chart_paths: dict[str, Path],
) -> Path:
    def markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
        if frame.empty:
            return "_Nessun dato disponibile._"
        display = frame[columns].head(max_rows).copy()
        for column in display.select_dtypes(include=[float]).columns:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
        return display.to_markdown(index=False)

    t2m = core_metrics[(core_metrics["group"] == "climate") & (core_metrics["variable"] == "t2m")]
    tp = core_metrics[(core_metrics["group"] == "climate") & (core_metrics["variable"] == "tp")]
    species = core_metrics[(core_metrics["group"] == "species_proxy")]
    other_core = core_metrics[
        ~((core_metrics["group"] == "climate") & (core_metrics["variable"].isin(["t2m", "tp"])))
        & ~core_metrics["group"].eq("species_proxy")
    ]
    run_selection = describe_run_selection(runs)
    years = sorted({pd.Timestamp(item).year for item in core_metrics["forecast_month"].dropna().unique()})
    year_label = "_".join(str(year) for year in years) if years else "mixed"
    lines: list[str] = []
    lines.append(f"# Report analisi BioAnalyst native {year_label}")
    lines.append("")
    lines.append(f"Questo report analizza i run `small aligned` selezionati: {run_selection}.")
    lines.append(f"Sono state prodotte metriche per `{len(all_metrics)}` combinazioni gruppo/variabile/livello.")
    if len(runs) < 4:
        lines.append("")
        lines.append("> Nota: sono stati analizzati solo i run coerenti con il filtro richiesto. Se manca una stagione, significa che non e' stato trovato un manifest con quell'anno nel `forecast_month`.")
    lines.append("")
    lines.append("## Run analizzati")
    for run in runs:
        manifest = load_json(run / "forecast_native_manifest.json")
        lines.append(f"- `{run.name}` -> forecast `{manifest.get('forecast_month')}`, checkpoint `{manifest.get('checkpoint_kind')}`")
    lines.append("")
    lines.append("## CSV resi leggibili in Excel")
    lines.append("")
    lines.append("Sono state create copie derivate dei CSV con separatore `;` e decimale `,` dentro ogni run:")
    lines.append("")
    lines.append("```text")
    lines.append("exports/bioanalyst_native_full_output_group_csv_excel_it_aligned/prediction/")
    lines.append("exports/bioanalyst_native_full_output_group_csv_excel_it_aligned/observed/")
    lines.append("```")
    lines.append("")
    lines.append(f"Totale file generati/aggiornati: `{len(readable_paths)}`.")
    lines.append("")
    lines.append("## Sintesi affidabilita")
    lines.append("")
    lines.append("### Temperatura `climate.t2m`")
    lines.append(markdown_table(t2m, ["forecast_month", "predicted_mean", "observed_mean", "mae", "rmse", "bias", "correlation", "reliability"]))
    lines.append("")
    lines.append("Interpretazione: la temperatura e' la variabile piu' promettente se il flip nord-sud e' applicato. Va comunque validata contro fonti esterne locali, non solo contro il target BioCube.")
    lines.append("")
    lines.append("### Precipitazione `climate.tp`")
    lines.append(markdown_table(tp, ["forecast_month", "predicted_mean", "observed_mean", "mae", "rmse", "bias", "correlation", "relative_mae_pct", "reliability"]))
    lines.append("")
    lines.append("Interpretazione: la precipitazione e' normalmente piu' difficile della temperatura. Se correlazione e relative MAE sono deboli, va trattata come variabile diagnostica e non ancora come risultato robusto.")
    lines.append("")
    lines.append("### Altre variabili principali")
    lines.append(
        markdown_table(
            other_core,
            ["forecast_month", "group", "variable", "predicted_mean", "observed_mean", "mae", "rmse", "bias", "correlation", "reliability"],
            max_rows=40,
        )
    )
    lines.append("")
    lines.append("Interpretazione: `d2m` e' utile come controllo climatico aggiuntivo; `NDVI`, `Forest` e `Agriculture` sono per ora diagnostici/proxy, perche' dipendono dal mapping dei dataset statici o quasi-statici dentro i canali nativi.")
    lines.append("")
    lines.append("### Specie / biodiversity proxy")
    lines.append(markdown_table(species, ["forecast_month", "variable", "predicted_mean", "observed_mean", "mae", "rmse", "correlation", "relative_mae_pct", "reliability"], max_rows=30))
    lines.append("")
    lines.append("Interpretazione: le specie sono state analizzate come proxy nativo aggregato, non come species richness finale BIOMAP. La metrica `species_sum_proxy` somma i 28 canali specie nativi; le soglie 0.1 e 0.5 sono diagnostiche.")
    lines.append("")
    lines.append("## Grafici")
    lines.append("")
    for title, path in chart_paths.items():
        rel = path.relative_to(output_dir)
        lines.append(f"### {title}")
        lines.append("")
        lines.append(f"![{title}]({rel.as_posix()})")
        lines.append("")
    lines.append("## Tabelle complete")
    lines.append("")
    lines.append("- `analysis_metrics_all_variables.csv`: metriche per tutte le variabili/gruppi/livelli.")
    lines.append("- `analysis_metrics_core_variables.csv`: subset delle variabili principali.")
    lines.append("- `analysis_summary_workbook.xlsx`: workbook con summary e metriche.")
    lines.append("")
    lines.append("## Conclusione operativa")
    lines.append("")
    lines.append("1. La temperatura `t2m` e' il primo indicatore da portare avanti, perche' dopo l'allineamento nord-sud e' la variabile piu' interpretabile.")
    lines.append("2. La precipitazione va analizzata con cautela: va validata su pattern regionali e non solo sulla media europea.")
    lines.append("3. Le specie vanno considerate output nativo/proxy, non ancora indicatore BIOMAP definitivo.")
    lines.append("4. Prima di dichiarare affidabilita' scientifica definitiva, serve confronto esterno con dati reali per aree campione.")
    report_path = output_dir / f"BIOANALYST_NATIVE_{year_label}_SEASONAL_ANALYSIS_REPORT.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    args = build_parser().parse_args()
    base_dir = args.base_dir
    output_suffix = str(args.forecast_year) if args.forecast_year is not None else "all"
    output_dir = args.output_dir or (base_dir / f"analysis_report_{output_suffix}")
    output_dir.mkdir(parents=True, exist_ok=True)

    runs = read_runs(base_dir, args.include_large, args.forecast_year)
    if not runs:
        raise SystemExit(f"Nessun run trovato in {base_dir}")

    all_rows: list[dict[str, Any]] = []
    readable_paths: list[Path] = []
    for run_dir in runs:
        manifest = load_json(run_dir / "forecast_native_manifest.json")
        prediction_batch = load_batch(run_dir / "native_prediction_original.pt")
        observed_batch = load_batch(run_dir / "native_target_original.pt")
        readable_paths.extend(create_readable_group_exports(run_dir, prediction_batch, observed_batch, manifest))
        all_rows.extend(variable_metrics_for_run(run_dir, prediction_batch, observed_batch, manifest))

    all_metrics = pd.DataFrame.from_records(all_rows)
    all_metrics = all_metrics.sort_values(["forecast_month", "group", "variable", "level_index"], na_position="first")
    core_filter = pd.Series(False, index=all_metrics.index)
    for group, variable in CORE_VARIABLES:
        core_filter |= (all_metrics["group"] == group) & (all_metrics["variable"].str.lower() == variable)
    core_filter |= all_metrics["group"].eq("species_proxy")
    core_metrics = all_metrics[core_filter].copy()

    metrics_csv = output_dir / "analysis_metrics_all_variables.csv"
    core_csv = output_dir / "analysis_metrics_core_variables.csv"
    all_metrics.to_csv(metrics_csv, index=False, encoding="utf-8-sig")
    core_metrics.to_csv(core_csv, index=False, encoding="utf-8-sig")
    all_metrics.to_csv(output_dir / "analysis_metrics_all_variables_excel_it.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")
    core_metrics.to_csv(output_dir / "analysis_metrics_core_variables_excel_it.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")

    chart_dir = output_dir / "charts"
    chart_paths: dict[str, Path] = {}
    t2m = core_metrics[(core_metrics["group"] == "climate") & (core_metrics["variable"] == "t2m")]
    tp = core_metrics[(core_metrics["group"] == "climate") & (core_metrics["variable"] == "tp")]
    species_sum = core_metrics[(core_metrics["group"] == "species_proxy") & (core_metrics["variable"] == "species_sum_proxy")]
    if not t2m.empty:
        chart_paths["Temperatura t2m - MAE/RMSE"] = chart_dir / "t2m_mae_rmse.png"
        chart_line(t2m, output_path=chart_paths["Temperatura t2m - MAE/RMSE"], title="Temperatura t2m: MAE e RMSE", y_columns=["mae", "rmse"], ylabel="Errore (degC)")
        chart_paths["Temperatura t2m - media predicted vs observed"] = chart_dir / "t2m_predicted_observed_mean.png"
        chart_line(t2m, output_path=chart_paths["Temperatura t2m - media predicted vs observed"], title="Temperatura t2m: media predicted vs observed", y_columns=["predicted_mean", "observed_mean"], ylabel="Temperatura media (degC)")
    if not tp.empty:
        chart_paths["Precipitazione tp - MAE/RMSE"] = chart_dir / "tp_mae_rmse.png"
        chart_line(tp, output_path=chart_paths["Precipitazione tp - MAE/RMSE"], title="Precipitazione tp: MAE e RMSE", y_columns=["mae", "rmse"], ylabel="Errore (mm)")
        chart_paths["Precipitazione tp - correlazione"] = chart_dir / "tp_correlation.png"
        chart_bar(tp, output_path=chart_paths["Precipitazione tp - correlazione"], title="Precipitazione tp: correlazione predicted/observed", value_column="correlation", ylabel="Correlazione")
    if not species_sum.empty:
        chart_paths["Species sum proxy - MAE/RMSE"] = chart_dir / "species_sum_proxy_mae_rmse.png"
        chart_line(species_sum, output_path=chart_paths["Species sum proxy - MAE/RMSE"], title="Species sum proxy: MAE e RMSE", y_columns=["mae", "rmse"], ylabel="Errore proxy")
        chart_paths["Species sum proxy - correlazione"] = chart_dir / "species_sum_proxy_correlation.png"
        chart_bar(species_sum, output_path=chart_paths["Species sum proxy - correlazione"], title="Species sum proxy: correlazione predicted/observed", value_column="correlation", ylabel="Correlazione")
    other_core = core_metrics[
        ~((core_metrics["group"] == "climate") & (core_metrics["variable"].isin(["t2m", "tp"])))
        & ~core_metrics["group"].eq("species_proxy")
    ]
    if not other_core.empty:
        chart_paths["Altre variabili principali - correlazione"] = chart_dir / "other_core_correlation.png"
        chart_metric_by_variable(
            other_core,
            output_path=chart_paths["Altre variabili principali - correlazione"],
            title="Altre variabili principali: correlazione predicted/observed",
            value_column="correlation",
            ylabel="Correlazione",
        )

    workbook_path = output_dir / "analysis_summary_workbook.xlsx"
    write_analysis_workbook(
        workbook_path,
        {
            "core_metrics": core_metrics,
            "all_metrics": all_metrics,
            "readable_csv_paths": pd.DataFrame({"path": [str(path) for path in readable_paths]}),
        },
    )
    report_path = create_report(
        output_dir=output_dir,
        runs=runs,
        all_metrics=all_metrics,
        core_metrics=core_metrics,
        readable_paths=readable_paths,
        chart_paths=chart_paths,
    )

    print(json.dumps({
        "runs_analyzed": [str(run) for run in runs],
        "output_dir": str(output_dir),
        "report": str(report_path),
        "workbook": str(workbook_path),
        "all_metrics_csv": str(metrics_csv),
        "core_metrics_csv": str(core_csv),
        "readable_csv_files": len(readable_paths),
        "charts": {name: str(path) for name, path in chart_paths.items()},
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
