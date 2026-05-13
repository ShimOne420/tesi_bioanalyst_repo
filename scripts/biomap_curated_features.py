"""Shared curated BIOMAP feature definitions for exports and charts."""

from __future__ import annotations

from typing import Any


CURATED_BIOMAP_FEATURES: list[dict[str, Any]] = [
    {
        "group": "climate",
        "variable": "t2m",
        "file_prefix": "t2m",
        "folder": "temperature",
        "chart_folder": "t2m",
        "sheet_name": "Temperature_t2m",
        "cmap": "coolwarm",
    },
    {
        "group": "climate",
        "variable": "tp",
        "file_prefix": "tp",
        "folder": "precipitation",
        "chart_folder": "tp",
        "sheet_name": "Precipitation_tp",
        "cmap": "PuBu",
    },
    {
        "group": "vegetation",
        "variable": "NDVI",
        "file_prefix": "ndvi",
        "folder": "ndvi",
        "chart_folder": "NDVI",
        "sheet_name": "Vegetation_NDVI",
        "cmap": "YlGn",
    },
    {
        "group": "edaphic",
        "variable": "swvl1",
        "file_prefix": "swvl1",
        "folder": "swvl1",
        "chart_folder": "swvl1",
        "sheet_name": "Edaphic_swvl1",
        "cmap": "Blues",
    },
    {
        "group": "edaphic",
        "variable": "swvl2",
        "file_prefix": "swvl2",
        "folder": "swvl2",
        "chart_folder": "swvl2",
        "sheet_name": "Edaphic_swvl2",
        "cmap": "Blues",
    },
    {
        "group": "atmospheric",
        "variable": "q",
        "file_prefix": "q",
        "folder": "q",
        "chart_folder": "q",
        "sheet_name": "Atmospheric_q",
        "cmap": "PuBuGn",
        "level_index": 0,
    },
    {
        "group": "forest",
        "variable": "Forest",
        "file_prefix": "forest",
        "folder": "forest",
        "chart_folder": "Forest",
        "sheet_name": "Forest",
        "cmap": "Greens",
    },
    {
        "group": "agriculture",
        "variable": "Arable",
        "file_prefix": "arable",
        "folder": "arable",
        "chart_folder": "Arable",
        "sheet_name": "Agriculture_Arable",
        "cmap": "YlOrBr",
    },
    {
        "group": "agriculture",
        "variable": "Cropland",
        "file_prefix": "cropland",
        "folder": "cropland",
        "chart_folder": "Cropland",
        "sheet_name": "Agriculture_Cropland",
        "cmap": "YlOrBr",
    },
    {
        "group": "climate",
        "variable": "avg_snlwrf",
        "file_prefix": "avg_snlwrf",
        "folder": "avg_snlwrf",
        "chart_folder": "avg_snlwrf",
        "sheet_name": "Climate_avg_snlwrf",
        "cmap": "magma",
    },
    {
        "group": "edaphic",
        "variable": "stl1",
        "file_prefix": "stl1",
        "folder": "stl1",
        "chart_folder": "stl1",
        "sheet_name": "Edaphic_stl1",
        "cmap": "coolwarm",
    },
    {
        "group": "edaphic",
        "variable": "stl2",
        "file_prefix": "stl2",
        "folder": "stl2",
        "chart_folder": "stl2",
        "sheet_name": "Edaphic_stl2",
        "cmap": "coolwarm",
    },
]


CURATED_BIOMAP_FEATURE_LOOKUP = {
    (str(feature["group"]), str(feature["variable"]), int(feature.get("level_index", 0))): feature
    for feature in CURATED_BIOMAP_FEATURES
}
