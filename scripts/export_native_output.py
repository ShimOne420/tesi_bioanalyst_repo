#!/usr/bin/env python3
"""Esporta un batch .pt nativo BioAnalyst in tabelle leggibili."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

from bioanalyst_native_utils import (
    NATIVE_GROUP_FIELDS,
    convert_display_values,
    flatten_batch_timestamps,
    get_native_group,
    list_native_group_counts,
    list_native_group_variables,
    load_native_batch_artifact,
    load_native_manifest,
    resolve_native_batch_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Legge l'output nativo BioAnalyst (.pt) e crea un Excel con metadati, "
            "coordinate, variabili e valori cella-per-cella."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run-dir", type=Path, help="Cartella del run con forecast_native_manifest.json.")
    source.add_argument("--pt-file", type=Path, help="File .pt da leggere direttamente.")
    parser.add_argument(
        "--batch-kind",
        choices=["prediction", "observed", "rollout"],
        default="prediction",
        help="Batch da leggere quando si usa --run-dir.",
    )
    parser.add_argument("--rollout-step", type=int, default=None, help="Step rollout da leggere, se batch-kind=rollout.")
    parser.add_argument("--group", default="climate", choices=sorted(NATIVE_GROUP_FIELDS), help="Gruppo da esportare in dettaglio.")
    parser.add_argument("--variable", default="t2m", help="Variabile da esportare in dettaglio.")
    parser.add_argument("--time-index", type=int, default=-1, help="Indice temporale da esportare. Default: ultimo timestep.")
    parser.add_argument("--level-index", type=int, default=0, help="Indice livello per gruppi 3D come atmospheric.")
    parser.add_argument("--output", type=Path, default=None, help="Path Excel finale. Default: run_dir/exports/native_output_*.xlsx.")
    parser.add_argument(
        "--export-group-csvs",
        action="store_true",
        help="Esporta anche un CSV per ogni gruppo, con tutte le variabili sull'ultimo timestep.",
    )
    parser.add_argument(
        "--no-coordinates-sheet",
        action="store_true",
        help="Non inserisce la griglia completa delle coordinate nell'Excel.",
    )
    return parser


def as_1d_float_array(value: Any) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32)
    if array.ndim > 1:
        array = array[0]
    return array


def selected_area_mask(latitudes: np.ndarray, longitudes: np.ndarray, bounds: dict[str, float] | None) -> np.ndarray:
    if not bounds:
        return np.ones((latitudes.size, longitudes.size), dtype=bool)
    lat_mask = (latitudes >= bounds["min_lat"]) & (latitudes <= bounds["max_lat"])
    lon_mask = (longitudes >= bounds["min_lon"]) & (longitudes <= bounds["max_lon"])
    return lat_mask[:, None] & lon_mask[None, :]


def tensor_to_numpy(tensor: torch.Tensor) -> np.ndarray:
    return tensor.detach().cpu().numpy()


def infer_tensor_dimensions(array: np.ndarray) -> dict[str, int | None]:
    dims: dict[str, int | None] = {
        "batch_count": None,
        "time_count": None,
        "level_count": None,
        "height": None,
        "width": None,
    }
    if array.ndim == 2:
        dims.update({"height": array.shape[0], "width": array.shape[1]})
    elif array.ndim == 3:
        dims.update({"time_count": array.shape[0], "height": array.shape[1], "width": array.shape[2]})
    elif array.ndim == 4:
        dims.update({"batch_count": array.shape[0], "time_count": array.shape[1], "height": array.shape[2], "width": array.shape[3]})
    elif array.ndim == 5:
        dims.update(
            {
                "batch_count": array.shape[0],
                "time_count": array.shape[1],
                "level_count": array.shape[2],
                "height": array.shape[3],
                "width": array.shape[4],
            }
        )
    return dims


def select_2d_map(tensor: torch.Tensor, *, time_index: int, level_index: int) -> np.ndarray:
    array = tensor_to_numpy(tensor)
    if array.ndim == 2:
        return array.astype(np.float32)
    if array.ndim == 3:
        return array[time_index].astype(np.float32)
    if array.ndim == 4:
        return array[0, time_index].astype(np.float32)
    if array.ndim == 5:
        return array[0, time_index, level_index].astype(np.float32)
    raise SystemExit(f"Shape non supportata: {array.shape}")


def finite_stats(values: np.ndarray) -> dict[str, float | int]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {
            "finite_count": 0,
            "nan_count": int(np.isnan(values).sum()),
            "zero_count": int((values == 0).sum()),
            "min": np.nan,
            "max": np.nan,
            "mean": np.nan,
            "std": np.nan,
        }
    return {
        "finite_count": int(finite.size),
        "nan_count": int(np.isnan(values).sum()),
        "zero_count": int((values == 0).sum()),
        "min": float(np.nanmin(values)),
        "max": float(np.nanmax(values)),
        "mean": float(np.nanmean(values)),
        "std": float(np.nanstd(values)),
    }


def build_variable_inventory(batch, *, time_index: int, level_index: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_name in NATIVE_GROUP_FIELDS:
        group = get_native_group(batch, group_name)
        for variable_name, tensor in sorted(group.items()):
            native_map = select_2d_map(tensor, time_index=time_index, level_index=level_index)
            display_map, unit = convert_display_values(variable_name, native_map)
            native_stats = finite_stats(native_map)
            display_stats = finite_stats(display_map)
            dims = infer_tensor_dimensions(tensor_to_numpy(tensor))
            rows.append(
                {
                    "group": group_name,
                    "variable": variable_name,
                    "tensor_shape": str(tuple(tensor.shape)),
                    "dtype": str(tensor.dtype),
                    **dims,
                    "selected_time_index": time_index,
                    "selected_level_index": level_index if tensor_to_numpy(tensor).ndim == 5 else None,
                    "display_unit": unit,
                    "native_min": native_stats["min"],
                    "native_max": native_stats["max"],
                    "native_mean": native_stats["mean"],
                    "native_std": native_stats["std"],
                    "display_min": display_stats["min"],
                    "display_max": display_stats["max"],
                    "display_mean": display_stats["mean"],
                    "display_std": display_stats["std"],
                    "finite_count": native_stats["finite_count"],
                    "nan_count": native_stats["nan_count"],
                    "zero_count": native_stats["zero_count"],
                }
            )
    return pd.DataFrame.from_records(rows)


def build_grid_frame(latitudes: np.ndarray, longitudes: np.ndarray, bounds: dict[str, float] | None) -> pd.DataFrame:
    area_mask = selected_area_mask(latitudes, longitudes, bounds)
    rows = []
    for lat_index, lat in enumerate(latitudes):
        for lon_index, lon in enumerate(longitudes):
            rows.append(
                {
                    "lat_index": lat_index,
                    "lon_index": lon_index,
                    "lat": float(lat),
                    "lon": float(lon),
                    "inside_selected_area": bool(area_mask[lat_index, lon_index]),
                }
            )
    return pd.DataFrame.from_records(rows)


def build_selected_variable_frame(
    batch,
    *,
    group_name: str,
    variable_name: str,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    bounds: dict[str, float] | None,
    time_index: int,
    level_index: int,
    observed_batch=None,
) -> pd.DataFrame:
    group = get_native_group(batch, group_name)
    if variable_name not in group:
        available = ", ".join(sorted(group.keys())[:20])
        raise SystemExit(f"Variabile {group_name}.{variable_name} non trovata. Disponibili: {available}")

    native_map = select_2d_map(group[variable_name], time_index=time_index, level_index=level_index)
    display_map, unit = convert_display_values(variable_name, native_map)
    area_mask = selected_area_mask(latitudes, longitudes, bounds)

    observed_native = None
    observed_display = None
    if observed_batch is not None:
        observed_group = get_native_group(observed_batch, group_name)
        if variable_name in observed_group:
            observed_native = select_2d_map(observed_group[variable_name], time_index=time_index, level_index=level_index)
            observed_display, _ = convert_display_values(variable_name, observed_native)

    rows = []
    for lat_index, lat in enumerate(latitudes):
        for lon_index, lon in enumerate(longitudes):
            native_value = float(native_map[lat_index, lon_index])
            display_value = float(display_map[lat_index, lon_index])
            observed_native_value = None if observed_native is None else float(observed_native[lat_index, lon_index])
            observed_display_value = None if observed_display is None else float(observed_display[lat_index, lon_index])
            rows.append(
                {
                    "lat_index": lat_index,
                    "lon_index": lon_index,
                    "lat": float(lat),
                    "lon": float(lon),
                    "group": group_name,
                    "variable": variable_name,
                    "unit": unit,
                    "native_value": native_value,
                    "display_value": display_value,
                    "observed_native_value": observed_native_value,
                    "observed_display_value": observed_display_value,
                    "native_difference": None if observed_native_value is None else native_value - observed_native_value,
                    "display_difference": None if observed_display_value is None else display_value - observed_display_value,
                    "inside_selected_area": bool(area_mask[lat_index, lon_index]),
                }
            )
    return pd.DataFrame.from_records(rows)


def build_group_wide_frame(
    batch,
    *,
    group_name: str,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
    bounds: dict[str, float] | None,
    time_index: int,
    level_index: int,
) -> pd.DataFrame:
    frame = build_grid_frame(latitudes, longitudes, bounds)
    group = get_native_group(batch, group_name)
    pressure_levels = getattr(batch.batch_metadata, "pressure_levels", None)
    if pressure_levels is None:
        pressure_levels = []
    if hasattr(pressure_levels, "detach"):
        pressure_levels = pressure_levels.detach().cpu().numpy().tolist()

    for variable_name, tensor in sorted(group.items()):
        array = tensor_to_numpy(tensor)
        if array.ndim == 5:
            level_count = array.shape[2]
            for current_level in range(level_count):
                native_map = select_2d_map(tensor, time_index=time_index, level_index=current_level)
                level_label = pressure_levels[current_level] if current_level < len(pressure_levels) else current_level
                column_name = f"{variable_name}_level_{level_label}_native"
                frame[column_name] = native_map.reshape(-1)
        else:
            native_map = select_2d_map(tensor, time_index=time_index, level_index=level_index)
            column_name = f"{variable_name}_native"
            frame[column_name] = native_map.reshape(-1)
    return frame


def rows_from_mapping(mapping: dict[str, Any], prefix: str = "") -> list[dict[str, Any]]:
    rows = []
    for key, value in mapping.items():
        row_key = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            rows.extend(rows_from_mapping(value, row_key))
        else:
            rows.append({"key": row_key, "value": json.dumps(value, ensure_ascii=False) if isinstance(value, (list, tuple)) else value})
    return rows


def resolve_inputs(args) -> tuple[dict[str, Any], Path, Any, Path | None]:
    if args.run_dir:
        run_dir = args.run_dir.resolve()
        manifest = load_native_manifest(run_dir)
        batch_path = resolve_native_batch_path(manifest, batch_kind=args.batch_kind, rollout_step=args.rollout_step)
        observed_path = manifest.get("native_target_original") if args.batch_kind == "prediction" else None
        return manifest, batch_path, load_native_batch_artifact(batch_path), Path(observed_path) if observed_path else None

    pt_file = args.pt_file.resolve()
    manifest = {
        "mode": "direct_pt_file",
        "label": pt_file.stem,
        "bounds": None,
        "source_pt_file": str(pt_file),
    }
    return manifest, pt_file, load_native_batch_artifact(pt_file), None


def default_output_path(args, run_dir: Path | None, batch_path: Path) -> Path:
    if args.output:
        return args.output.resolve()
    base_dir = (run_dir / "exports") if run_dir else (batch_path.parent / "exports")
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"native_output_{args.batch_kind}_{args.group}_{args.variable}.xlsx"


def write_excel_with_fallback(path: Path, sheets: dict[str, pd.DataFrame]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path
    try:
        with pd.ExcelWriter(target) as writer:
            for sheet_name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        return target
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}")
        with pd.ExcelWriter(fallback) as writer:
            for sheet_name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=sheet_name[:31], index=False)
        return fallback


def main() -> None:
    args = build_parser().parse_args()
    manifest, batch_path, batch, observed_path = resolve_inputs(args)
    run_dir = args.run_dir.resolve() if args.run_dir else None
    observed_batch = load_native_batch_artifact(observed_path) if observed_path and observed_path.exists() else None

    latitudes = as_1d_float_array(batch.batch_metadata.latitudes)
    longitudes = as_1d_float_array(batch.batch_metadata.longitudes)
    bounds = manifest.get("bounds")
    variable_inventory = build_variable_inventory(batch, time_index=args.time_index, level_index=args.level_index)
    selected_variable = build_selected_variable_frame(
        batch,
        group_name=args.group,
        variable_name=args.variable,
        latitudes=latitudes,
        longitudes=longitudes,
        bounds=bounds,
        time_index=args.time_index,
        level_index=args.level_index,
        observed_batch=observed_batch,
    )

    group_counts = list_native_group_counts(batch)
    group_variables = list_native_group_variables(batch)
    group_rows = [
        {
            "group": group_name,
            "variable_count": group_counts.get(group_name, 0),
            "variables": ", ".join(group_variables.get(group_name, [])),
        }
        for group_name in NATIVE_GROUP_FIELDS
    ]

    run_info = {
        "batch_path": str(batch_path),
        "batch_kind": args.batch_kind,
        "label": manifest.get("label"),
        "mode": manifest.get("mode"),
        "checkpoint_kind": manifest.get("checkpoint_kind"),
        "input_mode": manifest.get("input_mode"),
        "device": manifest.get("device"),
        "timestamps": flatten_batch_timestamps(batch),
        "grid_lat_count": int(latitudes.size),
        "grid_lon_count": int(longitudes.size),
        "grid_cell_count": int(latitudes.size * longitudes.size),
        "latitude_min": float(latitudes.min()),
        "latitude_max": float(latitudes.max()),
        "longitude_min": float(longitudes.min()),
        "longitude_max": float(longitudes.max()),
        "selected_group": args.group,
        "selected_variable": args.variable,
        "selected_time_index": args.time_index,
        "selected_level_index": args.level_index,
    }

    sheets = {
        "run_info": pd.DataFrame(rows_from_mapping(run_info)),
        "groups": pd.DataFrame.from_records(group_rows),
        "variables": variable_inventory,
        "selected_variable": selected_variable,
        "manifest": pd.DataFrame(rows_from_mapping(manifest)),
    }
    if not args.no_coordinates_sheet:
        sheets["coordinates"] = build_grid_frame(latitudes, longitudes, bounds)

    output_path = default_output_path(args, run_dir, batch_path)
    written_xlsx = write_excel_with_fallback(output_path, sheets)

    csv_paths: list[Path] = []
    if args.export_group_csvs:
        csv_dir = written_xlsx.parent / f"{written_xlsx.stem}_group_csv"
        csv_dir.mkdir(parents=True, exist_ok=True)
        for group_name in NATIVE_GROUP_FIELDS:
            group_frame = build_group_wide_frame(
                batch,
                group_name=group_name,
                latitudes=latitudes,
                longitudes=longitudes,
                bounds=bounds,
                time_index=args.time_index,
                level_index=args.level_index,
            )
            csv_path = csv_dir / f"{group_name}_variables_grid.csv"
            group_frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
            csv_paths.append(csv_path)

    print("\nBioAnalyst native output")
    print(f"- batch: {batch_path}")
    print(f"- timestamps: {', '.join(flatten_batch_timestamps(batch))}")
    print(f"- grid: {latitudes.size} lat x {longitudes.size} lon = {latitudes.size * longitudes.size} celle")
    print(f"- gruppi: {json.dumps(group_counts, ensure_ascii=False)}")
    print(f"- variabili totali: {int(variable_inventory.shape[0])}")
    print(f"- Excel: {written_xlsx}")
    if csv_paths:
        print(f"- CSV gruppi: {csv_paths[0].parent}")


if __name__ == "__main__":
    main()
