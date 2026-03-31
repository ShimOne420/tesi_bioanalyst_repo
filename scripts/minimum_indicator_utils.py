"""Funzioni di supporto condivise per gli script degli indicatori minimi.

Questo file non va lanciato da solo. Serve come modulo comune per:

- ritagliare correttamente l'Europa dal dataset climatico
- filtrare i dati per periodo
- costruire bounding box da punti o città
- applicare la maschera terra
- esportare output tabellari leggibili anche in Excel
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


# Definiamo il bounding box europeo usato come perimetro coerente del progetto.
EUROPE_BOUNDS = {
    "min_lat": 30.0,
    "max_lat": 75.0,
    "min_lon": -25.0,
    "max_lon": 45.0,
}


# Normalizziamo le longitudini nel range [-180, 180] per lavorare sempre con coordinate coerenti.
def normalize_longitude(ds: xr.Dataset) -> xr.Dataset:
    longitude = (((ds.longitude + 180) % 360) - 180)
    return ds.assign_coords(longitude=longitude).sortby("longitude")


# Ritagliamo il dataset climatico sul bounding box europeo di riferimento.
def subset_europe(ds: xr.Dataset, bounds: dict[str, float] | None = None) -> xr.Dataset:
    bounds = bounds or EUROPE_BOUNDS
    ds = normalize_longitude(ds)
    return ds.sel(
        latitude=slice(bounds["max_lat"], bounds["min_lat"]),
        longitude=slice(bounds["min_lon"], bounds["max_lon"]),
    )


# Costruiamo una maschera terra/mare usando il layer `lsm` di ERA5.
def build_land_mask(ds_temp: xr.Dataset) -> xr.DataArray:
    return ds_temp["lsm"].isel(valid_time=0) > 0.5


# Uniformiamo tutte le date al primo giorno del mese per evitare disallineamenti temporali.
def to_month_start(value: str | pd.Timestamp | None) -> pd.Timestamp | None:
    if value is None:
        return None
    return pd.Timestamp(value).to_period("M").to_timestamp()


# Filtriamo un DataFrame tabellare per intervallo temporale mensile.
def filter_dataframe_month_range(
    df: pd.DataFrame,
    month_column: str,
    start: str | None = None,
    end: str | None = None,
    max_steps: int | None = None,
) -> pd.DataFrame:
    start_ts = to_month_start(start)
    end_ts = to_month_start(end)

    filtered = df.copy()
    if start_ts is not None:
        filtered = filtered[filtered[month_column] >= start_ts]
    if end_ts is not None:
        filtered = filtered[filtered[month_column] <= end_ts]
    if max_steps is not None:
        months = (
            filtered[month_column]
            .drop_duplicates()
            .sort_values()
            .iloc[:max_steps]
            .tolist()
        )
        filtered = filtered[filtered[month_column].isin(months)]
    return filtered


# Filtriamo un dataset xarray sullo stesso intervallo temporale mensile.
def filter_dataset_month_range(
    ds: xr.Dataset,
    start: str | None = None,
    end: str | None = None,
    max_steps: int | None = None,
) -> xr.Dataset:
    time_index = pd.to_datetime(ds["valid_time"].values).to_period("M").to_timestamp()
    mask = np.ones(len(time_index), dtype=bool)

    start_ts = to_month_start(start)
    end_ts = to_month_start(end)
    if start_ts is not None:
        mask &= time_index >= start_ts
    if end_ts is not None:
        mask &= time_index <= end_ts

    selected = np.where(mask)[0]
    if max_steps is not None:
        selected = selected[:max_steps]

    return ds.isel(valid_time=selected)


# Costruiamo automaticamente un piccolo rettangolo spaziale attorno a un punto.
def build_bbox_from_point(lat: float, lon: float, half_window_deg: float = 0.125) -> dict[str, float]:
    return {
        "min_lat": lat - half_window_deg,
        "max_lat": lat + half_window_deg,
        "min_lon": lon - half_window_deg,
        "max_lon": lon + half_window_deg,
    }


# Ritagliamo un dataset xarray su un bounding box arbitrario.
def subset_bbox(ds: xr.Dataset, bounds: dict[str, float]) -> xr.Dataset:
    return ds.sel(
        latitude=slice(bounds["max_lat"], bounds["min_lat"]),
        longitude=slice(bounds["min_lon"], bounds["max_lon"]),
    )


# Calcoliamo una serie temporale media su sole celle di terra usando pesi di latitudine.
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


# Risolviamo una cartella di output scrivibile, con fallback locale se il disco esterno non è accessibile.
def resolve_output_base_dir(output_dir: Path, project_root: Path) -> tuple[Path, bool]:
    def ensure_writable(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
        return path

    try:
        return ensure_writable(output_dir), False
    except PermissionError:
        fallback = project_root / "outputs" / "local_preview"
        return ensure_writable(fallback), True


# Esportiamo una tabella in più formati per facilitare sia analisi Python sia apertura in Excel.
def write_tabular_outputs(
    summary: dict,
    table_df: pd.DataFrame,
    stem: str,
    output_dir: Path,
    project_root: Path,
) -> tuple[dict[str, Path], bool]:
    base_dir, used_fallback = resolve_output_base_dir(output_dir, project_root)
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
    return paths, used_fallback
