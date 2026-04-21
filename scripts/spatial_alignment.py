#!/usr/bin/env python3
"""Utility per riallineare gli output grigliati BioAnalyst alle coordinate geografiche."""

from __future__ import annotations

from typing import Any

import math
import numpy as np
import pandas as pd


DEFAULT_PREDICTION_LATITUDE_FLIP = True
DEFAULT_PREDICTION_LONGITUDE_FLIP = False


def build_spatial_alignment_metadata() -> dict[str, Any]:
    """Metadati espliciti da salvare nel manifest del run."""
    return {
        "prediction_latitude_flip_applied": DEFAULT_PREDICTION_LATITUDE_FLIP,
        "prediction_longitude_flip_applied": DEFAULT_PREDICTION_LONGITUDE_FLIP,
        "applies_to": "human-readable exports, plots and validation metrics",
        "native_pt_preserved": True,
        "reason": (
            "Diagnostic on t2m small showed a north-south inversion of the predicted map "
            "against the observed target; east-west flip was worse and is not applied."
        ),
    }


def prediction_latitude_flip_enabled(manifest: dict[str, Any] | None) -> bool:
    """Legge dal manifest se le prediction devono essere ribaltate sull'asse latitudinale."""
    if not manifest:
        return False
    spatial_alignment = manifest.get("spatial_alignment", {})
    return bool(spatial_alignment.get("prediction_latitude_flip_applied", False))


def prediction_longitude_flip_enabled(manifest: dict[str, Any] | None) -> bool:
    """Legge dal manifest se le prediction devono essere ribaltate sull'asse longitudinale."""
    if not manifest:
        return False
    spatial_alignment = manifest.get("spatial_alignment", {})
    return bool(spatial_alignment.get("prediction_longitude_flip_applied", False))


def align_prediction_map(
    map_values: np.ndarray,
    *,
    latitude_flip: bool = DEFAULT_PREDICTION_LATITUDE_FLIP,
    longitude_flip: bool = DEFAULT_PREDICTION_LONGITUDE_FLIP,
) -> np.ndarray:
    """Allinea una mappa 2D predetta alle coordinate lat/lon usate per observed/export.

    Il flip e' applicato solo alla prediction, mai all'observed. Per una mappa 2D
    l'asse latitudinale e' `-2` e l'asse longitudinale e' `-1`.
    """
    aligned = np.asarray(map_values)
    if latitude_flip:
        aligned = np.flip(aligned, axis=-2)
    if longitude_flip:
        aligned = np.flip(aligned, axis=-1)
    return aligned.copy()


def plot_origin_for_latitudes(latitudes: np.ndarray) -> str:
    """Sceglie l'origine imshow coerente con l'ordine della latitudine."""
    latitudes = np.asarray(latitudes)
    if latitudes.size >= 2 and float(latitudes[0]) > float(latitudes[-1]):
        return "upper"
    return "lower"


def _metric_row(name: str, predicted: np.ndarray, observed: np.ndarray) -> dict[str, float | int | str]:
    mask = np.isfinite(predicted) & np.isfinite(observed)
    if not mask.any():
        return {
            "scenario": name,
            "cell_count": 0,
            "correlation": math.nan,
            "mae": math.nan,
            "rmse": math.nan,
            "bias": math.nan,
            "predicted_mean": math.nan,
            "observed_mean": math.nan,
        }

    pred = predicted[mask].astype(np.float64)
    obs = observed[mask].astype(np.float64)
    diff = pred - obs
    if pred.size > 1 and float(np.std(pred)) > 0.0 and float(np.std(obs)) > 0.0:
        correlation = float(np.corrcoef(pred, obs)[0, 1])
    else:
        correlation = math.nan

    return {
        "scenario": name,
        "cell_count": int(pred.size),
        "correlation": correlation,
        "mae": float(np.mean(np.abs(diff))),
        "rmse": float(np.sqrt(np.mean(np.square(diff)))),
        "bias": float(np.mean(diff)),
        "predicted_mean": float(np.mean(pred)),
        "observed_mean": float(np.mean(obs)),
    }


def build_alignment_diagnostic_frame(predicted_map_raw: np.ndarray, observed_map: np.ndarray) -> pd.DataFrame:
    """Confronta orientamento originale e possibili flip della prediction."""
    predicted_map_raw = np.asarray(predicted_map_raw)
    observed_map = np.asarray(observed_map)
    rows = [
        _metric_row("original", predicted_map_raw, observed_map),
        _metric_row("flip_north_south", np.flip(predicted_map_raw, axis=-2), observed_map),
        _metric_row("flip_east_west", np.flip(predicted_map_raw, axis=-1), observed_map),
        _metric_row("flip_north_south_east_west", np.flip(np.flip(predicted_map_raw, axis=-2), axis=-1), observed_map),
    ]
    return pd.DataFrame.from_records(rows)

