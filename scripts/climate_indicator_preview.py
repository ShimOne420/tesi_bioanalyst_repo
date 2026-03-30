#!/usr/bin/env python3
"""Preview degli indicatori climatici minimi: temperatura e precipitazione."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pandas as pd
import xarray as xr
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def require_path(env_name: str) -> Path:
    value = os.getenv(env_name)
    if not value:
        raise RuntimeError(f"Variabile d'ambiente mancante: {env_name}")
    path = Path(value).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Percorso non trovato per {env_name}: {path}")
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crea un preview leggero di temperatura media e precipitazione media."
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help="Numero massimo di time step da processare per un test veloce.",
    )
    return parser


def compute_spatial_mean_series(
    ds: xr.Dataset, var_name: str, max_steps: int | None = None
) -> pd.DataFrame:
    records: list[dict[str, float | str]] = []
    data = ds[var_name]
    total_steps = data.sizes["valid_time"]
    if max_steps is not None:
        total_steps = min(total_steps, max_steps)

    for idx in range(total_steps):
        slice_da = data.isel(valid_time=idx)
        mean_value = float(slice_da.mean(skipna=True).load().item())
        records.append(
            {
                "valid_time": str(pd.to_datetime(ds["valid_time"].values[idx]).date()),
                var_name: mean_value,
            }
        )

    return pd.DataFrame.from_records(records)


def write_outputs(summary: dict, preview_df: pd.DataFrame, stem: str, output_dir: Path) -> tuple[Path, Path, bool]:
    preferred_output_dir = output_dir
    fallback_output_dir = PROJECT_ROOT / "outputs" / "local_preview"
    summary_path = preferred_output_dir / f"{stem}_summary.json"
    preview_path = preferred_output_dir / f"{stem}_preview.csv"

    try:
        preferred_output_dir.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        preview_df.to_csv(preview_path, index=False)
        return summary_path, preview_path, False
    except PermissionError:
        fallback_output_dir.mkdir(parents=True, exist_ok=True)
        summary_path = fallback_output_dir / f"{stem}_summary.json"
        preview_path = fallback_output_dir / f"{stem}_preview.csv"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        preview_df.to_csv(preview_path, index=False)
        return summary_path, preview_path, True


def main() -> None:
    args = build_parser().parse_args()
    load_dotenv()

    biocube_dir = require_path("BIOCUBE_DIR")
    output_dir = require_path("PROJECT_OUTPUT_DIR")

    temperature_path = (
        biocube_dir
        / "Copernicus"
        / "ERA5-monthly"
        / "era5-single"
        / "era5_single.nc"
    )
    precipitation_path = (
        biocube_dir
        / "Copernicus"
        / "ERA5-monthly"
        / "era5-climate-energy-moisture"
        / "era5-climate-energy-moisture-0.nc"
    )

    if not temperature_path.exists():
        raise FileNotFoundError(f"File temperatura non trovato: {temperature_path}")
    if not precipitation_path.exists():
        raise FileNotFoundError(f"File precipitazione non trovato: {precipitation_path}")

    ds_temp = xr.open_dataset(temperature_path)
    ds_prec = xr.open_dataset(precipitation_path)

    temp_df = compute_spatial_mean_series(ds_temp, "t2m", max_steps=args.max_steps)
    temp_df["temperature_mean_c"] = temp_df["t2m"] - 273.15
    temp_df = temp_df.drop(columns=["t2m"])

    prec_df = compute_spatial_mean_series(ds_prec, "tp", max_steps=args.max_steps)
    prec_df["precipitation_mean_mm"] = prec_df["tp"] * 1000.0
    prec_df = prec_df.drop(columns=["tp"])

    ds_temp.close()
    ds_prec.close()

    merged = temp_df.merge(prec_df, on="valid_time", how="inner")

    summary = {
        "temperature_source": str(temperature_path),
        "precipitation_source": str(precipitation_path),
        "rows_preview": int(len(merged)),
        "time_start": str(merged["valid_time"].min()),
        "time_end": str(merged["valid_time"].max()),
        "temperature_mean_c_global_mean": float(merged["temperature_mean_c"].mean()),
        "temperature_mean_c_min": float(merged["temperature_mean_c"].min()),
        "temperature_mean_c_max": float(merged["temperature_mean_c"].max()),
        "precipitation_mean_mm_global_mean": float(merged["precipitation_mean_mm"].mean()),
        "precipitation_mean_mm_min": float(merged["precipitation_mean_mm"].min()),
        "precipitation_mean_mm_max": float(merged["precipitation_mean_mm"].max()),
    }

    summary_path, preview_path, used_fallback = write_outputs(
        summary=summary,
        preview_df=merged,
        stem="climate_indicators",
        output_dir=output_dir,
    )

    print("Climate indicator preview creato con successo.")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nSummary: {summary_path}")
    print(f"Preview CSV: {preview_path}")
    if used_fallback:
        print(
            "\nNota: ho usato la cartella locale del repo perché il path esterno non era "
            "scrivibile in questo ambiente."
        )


if __name__ == "__main__":
    main()
