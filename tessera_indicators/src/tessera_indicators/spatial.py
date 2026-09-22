"""Deterministic European macro-region and spatial-block splits."""

from __future__ import annotations

import hashlib

import pandas as pd


def macro_region(longitude: float, latitude: float) -> str:
    if latitude >= 60:
        return "fennoscandia"
    if longitude <= -1 and latitude < 45:
        return "iberia"
    if longitude >= 7 and longitude <= 19 and latitude < 48:
        return "mediterranean_italy"
    return "central_europe"


def spatial_block(longitude: float, latitude: float, degrees: float = 0.5) -> str:
    return f"{int((longitude + 30) // degrees):03d}_{int((latitude - 25) // degrees):03d}"


def split_for_block(block_id: str) -> str:
    bucket = int(hashlib.sha256(block_id.encode("utf-8")).hexdigest()[:8], 16) % 10
    return "test" if bucket == 0 else "validation" if bucket == 1 else "train"


def add_spatial_split(frame: pd.DataFrame, degrees: float = 0.5) -> pd.DataFrame:
    result = frame.copy()
    result["macro_region"] = [macro_region(lon, lat) for lon, lat in zip(result.longitude, result.latitude)]
    result["spatial_block"] = [spatial_block(lon, lat, degrees) for lon, lat in zip(result.longitude, result.latitude)]
    result["split"] = [split_for_block(value) for value in result.spatial_block]
    return result
