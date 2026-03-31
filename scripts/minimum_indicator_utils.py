from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


EUROPE_BOUNDS = {
    "min_lat": 30.0,
    "max_lat": 75.0,
    "min_lon": -25.0,
    "max_lon": 45.0,
}


def normalize_longitude(ds: xr.Dataset) -> xr.Dataset:
    longitude = (((ds.longitude + 180) % 360) - 180)
    return ds.assign_coords(longitude=longitude).sortby("longitude")


def subset_europe(ds: xr.Dataset, bounds: dict[str, float] | None = None) -> xr.Dataset:
    bounds = bounds or EUROPE_BOUNDS
    ds = normalize_longitude(ds)
    return ds.sel(
        latitude=slice(bounds["max_lat"], bounds["min_lat"]),
        longitude=slice(bounds["min_lon"], bounds["max_lon"]),
    )


def build_land_mask(ds_temp: xr.Dataset) -> xr.DataArray:
    return ds_temp["lsm"].isel(valid_time=0) > 0.5


def compute_weighted_land_mean_series(
    ds: xr.Dataset,
    var_name: str,
    output_column: str,
    land_mask: xr.DataArray,
    transform=lambda x: x,
    max_steps: int | None = None,
) -> pd.DataFrame:
    data = ds[var_name]
    if max_steps is not None:
        data = data.isel(valid_time=slice(0, max_steps))

    weights = np.cos(np.deg2rad(data.latitude))
    series = data.where(land_mask).weighted(weights).mean(dim=("latitude", "longitude"))

    records = []
    for valid_time, value in zip(data["valid_time"].values, series.values):
        records.append(
            {
                "month": str(pd.to_datetime(valid_time).date()),
                output_column: float(transform(value)),
            }
        )

    return pd.DataFrame.from_records(records)


def write_tabular_outputs(
    summary: dict,
    table_df: pd.DataFrame,
    stem: str,
    output_dir: Path,
    project_root: Path,
) -> tuple[dict[str, Path], bool]:
    preferred_output_dir = output_dir
    fallback_output_dir = project_root / "outputs" / "local_preview"

    def export(base_dir: Path) -> dict[str, Path]:
        base_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "summary": base_dir / f"{stem}_summary.json",
            "csv": base_dir / f"{stem}.csv",
            "excel_csv": base_dir / f"{stem}_excel.csv",
            "xlsx": base_dir / f"{stem}.xlsx",
        }
        paths["summary"].write_text(pd.Series(summary).to_json(force_ascii=False, indent=2))
        table_df.to_csv(paths["csv"], index=False)
        table_df.to_csv(paths["excel_csv"], index=False, sep=";", encoding="utf-8-sig")
        table_df.to_excel(paths["xlsx"], index=False)
        return paths

    try:
        return export(preferred_output_dir), False
    except PermissionError:
        return export(fallback_output_dir), True
