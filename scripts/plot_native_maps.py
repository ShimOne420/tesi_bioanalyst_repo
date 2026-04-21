#!/usr/bin/env python3
"""Salva mappe PNG leggibili a partire dagli output nativi di BioAnalyst."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

from bioanalyst_native_utils import (
    NATIVE_GROUP_FIELDS,
    convert_display_values,
    extract_native_map,
    get_native_group,
    load_native_batch_artifact,
    load_native_manifest,
    resolve_native_batch_path,
)
from spatial_alignment import (
    align_prediction_map,
    plot_origin_for_latitudes,
    prediction_latitude_flip_enabled,
    prediction_longitude_flip_enabled,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Crea mappe PNG da prediction, observed o rollout nativi di BioAnalyst.",
    )
    parser.add_argument("--run-dir", type=Path, required=True, help="Cartella del run con `forecast_native_manifest.json`.")
    parser.add_argument(
        "--batch-kind",
        choices=["prediction", "observed", "rollout"],
        default="prediction",
        help="Quale batch visualizzare.",
    )
    parser.add_argument(
        "--rollout-step",
        type=int,
        default=None,
        help="Step del rollout da usare quando `--batch-kind rollout`.",
    )
    parser.add_argument(
        "--group",
        choices=sorted(NATIVE_GROUP_FIELDS),
        default="climate",
        help="Gruppo da visualizzare.",
    )
    parser.add_argument(
        "--variable",
        default="t2m",
        help="Variabile del gruppo da plottare.",
    )
    parser.add_argument(
        "--difference",
        action="store_true",
        help="Plotta `prediction - observed` per la variabile scelta. Funziona solo sui run one-step con target osservato.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path finale del PNG. Se omesso, salva in `run_dir/plots`.",
    )
    parser.add_argument(
        "--align-prediction-latitude",
        dest="align_prediction_latitude",
        action="store_true",
        default=None,
        help="Forza il flip nord-sud della prediction anche se il manifest non lo dichiara.",
    )
    parser.add_argument(
        "--no-align-prediction-latitude",
        dest="align_prediction_latitude",
        action="store_false",
        help="Non applica il flip nord-sud dichiarato nel manifest alla prediction.",
    )
    return parser


def get_batch_variable_map(batch, *, group_name: str, variable_name: str) -> tuple[np.ndarray, str]:
    group = get_native_group(batch, group_name)
    if variable_name not in group:
        raise SystemExit(f"Variabile `{variable_name}` non trovata nel gruppo `{group_name}`.")
    raw_map = extract_native_map(group[variable_name])
    return convert_display_values(variable_name, raw_map)


def get_grid_coordinates(batch) -> tuple[np.ndarray, np.ndarray]:
    latitudes = np.asarray(batch.batch_metadata.latitudes, dtype=np.float32)
    longitudes = np.asarray(batch.batch_metadata.longitudes, dtype=np.float32)
    if latitudes.ndim > 1:
        latitudes = latitudes[0]
    if longitudes.ndim > 1:
        longitudes = longitudes[0]
    return latitudes, longitudes


def build_output_path(run_dir: Path, *, batch_kind: str, variable_name: str, difference: bool, rollout_step: int | None) -> Path:
    plots_dir = run_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)
    if difference:
        stem = f"{variable_name}_difference"
    elif batch_kind == "rollout":
        step_label = rollout_step if rollout_step is not None else "last"
        stem = f"{variable_name}_rollout_step_{step_label}"
    else:
        stem = f"{variable_name}_{batch_kind}"
    return plots_dir / f"{stem}.png"


def add_selection_box(ax, bounds: dict[str, float] | None) -> None:
    if not bounds:
        return
    rect = patches.Rectangle(
        (bounds["min_lon"], bounds["min_lat"]),
        bounds["max_lon"] - bounds["min_lon"],
        bounds["max_lat"] - bounds["min_lat"],
        linewidth=1.5,
        edgecolor="black",
        facecolor="none",
        linestyle="--",
    )
    ax.add_patch(rect)


def main() -> None:
    args = build_parser().parse_args()
    run_dir = args.run_dir.resolve()
    manifest = load_native_manifest(run_dir)
    align_prediction_latitude = (
        bool(args.align_prediction_latitude)
        if args.align_prediction_latitude is not None
        else bool(prediction_latitude_flip_enabled(manifest))
    )
    align_prediction_longitude = bool(prediction_longitude_flip_enabled(manifest))

    if args.difference:
        if not manifest.get("native_prediction_original") or not manifest.get("native_target_original"):
            raise SystemExit("Per `--difference` servono sia prediction sia observed nello stesso run.")
        prediction_batch = load_native_batch_artifact(Path(manifest["native_prediction_original"]))
        observed_batch = load_native_batch_artifact(Path(manifest["native_target_original"]))
        prediction_map, unit = get_batch_variable_map(
            prediction_batch,
            group_name=args.group,
            variable_name=args.variable,
        )
        prediction_map = align_prediction_map(
            prediction_map,
            latitude_flip=align_prediction_latitude,
            longitude_flip=align_prediction_longitude,
        )
        observed_map, _ = get_batch_variable_map(
            observed_batch,
            group_name=args.group,
            variable_name=args.variable,
        )
        map_values = prediction_map - observed_map
        title = f"{args.group}.{args.variable} prediction - observed"
        cmap = "coolwarm"
        latitudes, longitudes = get_grid_coordinates(prediction_batch)
    else:
        batch_path = resolve_native_batch_path(
            manifest,
            batch_kind=args.batch_kind,
            rollout_step=args.rollout_step,
        )
        batch = load_native_batch_artifact(batch_path)
        map_values, unit = get_batch_variable_map(
            batch,
            group_name=args.group,
            variable_name=args.variable,
        )
        if args.batch_kind in ("prediction", "rollout"):
            map_values = align_prediction_map(
                map_values,
                latitude_flip=align_prediction_latitude,
                longitude_flip=align_prediction_longitude,
            )
        title = f"{args.group}.{args.variable} ({args.batch_kind})"
        cmap = "coolwarm" if args.variable == "t2m" else "viridis"
        latitudes, longitudes = get_grid_coordinates(batch)

    output_path = args.output.resolve() if args.output else build_output_path(
        run_dir,
        batch_kind=args.batch_kind,
        variable_name=args.variable,
        difference=args.difference,
        rollout_step=args.rollout_step,
    )

    fig, ax = plt.subplots(figsize=(11, 6))
    image = ax.imshow(
        map_values,
        origin=plot_origin_for_latitudes(latitudes),
        extent=[float(longitudes.min()), float(longitudes.max()), float(latitudes.min()), float(latitudes.max())],
        aspect="auto",
        cmap=cmap,
    )
    add_selection_box(ax, manifest.get("bounds"))
    ax.set_title(title)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label(unit)
    fig.tight_layout()
    fig.savefig(output_path, dpi=200)
    plt.close(fig)

    print(f"Mappa salvata in: {output_path}")


if __name__ == "__main__":
    main()
