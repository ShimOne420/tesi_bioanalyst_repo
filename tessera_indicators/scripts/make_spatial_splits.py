#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from _bootstrap import ROOT  # noqa: F401
from tessera_indicators.contracts import validate_samples
from tessera_indicators.spatial import add_spatial_split


def read_table(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--block-degrees", type=float, default=0.5)
    args = parser.parse_args()
    samples = read_table(Path(args.input))
    validate_samples(samples)
    result = add_spatial_split(samples, args.block_degrees)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    (result.to_parquet(destination, index=False) if destination.suffix == ".parquet" else result.to_csv(destination, index=False))
    print(result.groupby(["macro_region", "split"]).size())


if __name__ == "__main__":
    main()
