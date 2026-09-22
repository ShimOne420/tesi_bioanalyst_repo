#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from _bootstrap import ROOT  # noqa: F401
from tessera_indicators.contracts import write_json
from tessera_indicators.metrics import bootstrap_mae_interval, regression_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    frame = pd.read_csv(args.input)
    if not {"target_value", "prediction", "split", "macro_region"}.issubset(frame):
        raise ValueError("Prediction file lacks target_value, prediction, split, or macro_region.")
    test = frame.loc[frame.split == "test"]
    if test.empty:
        raise ValueError("Final metrics must use the held-out test split.")
    low, high = bootstrap_mae_interval(test.target_value, test.prediction)
    payload = {"test": regression_metrics(test.target_value, test.prediction), "test_mae_95ci": [low, high], "by_macro_region": {}}
    for region, subset in test.groupby("macro_region"):
        payload["by_macro_region"][region] = regression_metrics(subset.target_value, subset.prediction)
    write_json(args.output, payload)
    print(args.output)


if __name__ == "__main__":
    main()
