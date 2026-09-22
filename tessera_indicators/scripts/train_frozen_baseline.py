#!/usr/bin/env python3
"""Train a dependency-light Ridge baseline on frozen TESSERA embeddings."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from _bootstrap import ROOT  # noqa: F401
from tessera_indicators.contracts import feature_columns, validate_samples, write_json


def read_table(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def fit_ridge(x: np.ndarray, y: np.ndarray, penalty: float) -> tuple[np.ndarray, np.ndarray, float]:
    mean, scale = x.mean(axis=0), x.std(axis=0)
    scale[scale == 0] = 1.0
    normalized = (x - mean) / scale
    augmented = np.c_[np.ones(len(normalized)), normalized]
    regularizer = np.eye(augmented.shape[1]) * penalty
    regularizer[0, 0] = 0.0
    weights = np.linalg.solve(augmented.T @ augmented + regularizer, augmented.T @ y)
    return weights, mean, scale


def predict(x: np.ndarray, weights: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return np.c_[np.ones(len(x)), (x - mean) / scale] @ weights


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--task", required=True, choices=("bii", "msa_globio4"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--penalties", default="0.01,0.1,1,10,100")
    args = parser.parse_args()
    frame = read_table(Path(args.input))
    features = validate_samples(frame, require_split=True)
    train, validation = frame.query("split == 'train'"), frame.query("split == 'validation'")
    if train.empty or validation.empty:
        raise ValueError("Both train and validation partitions are required before baseline training.")
    x_train, y_train = train[features].to_numpy(float), train.target_value.to_numpy(float)
    x_validation, y_validation = validation[features].to_numpy(float), validation.target_value.to_numpy(float)
    candidates = []
    for value in map(float, args.penalties.split(",")):
        weights, mean, scale = fit_ridge(x_train, y_train, value)
        candidates.append((float(np.mean((predict(x_validation, weights, mean, scale) - y_validation) ** 2)), value, weights, mean, scale))
    _, penalty, weights, mean, scale = min(candidates, key=lambda item: item[0])
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=True)
    np.savez(destination / "ridge_model.npz", weights=weights, mean=mean, scale=scale, features=np.array(features), penalty=penalty)
    output = frame[["sample_id", "longitude", "latitude", "macro_region", "spatial_block", "split", "target_value"]].copy()
    output["prediction"] = np.clip(predict(frame[features].to_numpy(float), weights, mean, scale), 0.0, 1.0)
    output.to_csv(destination / "predictions.csv", index=False)
    write_json(destination / "run_manifest.json", {"task": args.task, "model": "frozen_embedding_ridge", "penalty": penalty, "feature_count": len(features), "input": str(Path(args.input).resolve())})
    print(destination / "predictions.csv")


if __name__ == "__main__":
    main()
