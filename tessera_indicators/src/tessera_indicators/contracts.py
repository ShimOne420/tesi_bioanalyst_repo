"""Data contracts that prevent unsupported BII/MSA claims."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_SAMPLE_COLUMNS = {"sample_id", "longitude", "latitude", "target_value", "coverage_fraction"}


def load_task_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        config = json.load(handle)
    if set(config.get("tasks", {})) != {"bii", "msa_globio4"}:
        raise ValueError("Config must declare exactly 'bii' and 'msa_globio4'.")
    return config


def unresolved_fields(task: dict[str, Any]) -> list[str]:
    required = ("target_path", "target_year", "target_version", "license", "source_url")
    return [field for field in required if str(task.get(field, "")).startswith("REQUIRED") or not task.get(field)]


def feature_columns(frame: pd.DataFrame) -> list[str]:
    features = sorted(column for column in frame.columns if column.startswith("emb_"))
    if not features:
        raise ValueError("No embedding features found. Expected columns named emb_000, emb_001, ...")
    return features


def validate_samples(frame: pd.DataFrame, *, require_split: bool = False) -> list[str]:
    missing = sorted(REQUIRED_SAMPLE_COLUMNS - set(frame.columns))
    if require_split and "split" not in frame.columns:
        missing.append("split")
    if missing:
        raise ValueError(f"Prepared samples missing required columns: {', '.join(missing)}")
    if frame["sample_id"].duplicated().any():
        raise ValueError("sample_id must be unique at target support; duplicate labels create pseudo-replication.")
    for column, lower, upper in (("longitude", -25, 45), ("latitude", 30, 75), ("coverage_fraction", 0, 1), ("target_value", 0, 1)):
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or ((values < lower) | (values > upper)).any():
            raise ValueError(f"{column} contains missing or out-of-range values for the European task contract.")
    return feature_columns(frame)


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
