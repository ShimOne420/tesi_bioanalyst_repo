#!/usr/bin/env python3
"""Corregge in-place la scala di climate_a per i mesi futuri gia scaricati.

Contesto:
- il file storico BioCube `era5-climate-energy-moisture-0.nc` contiene per `tp`,
  `csfr` e `smlt` valori compatibili con monthly means of daily means;
- le prime estensioni future da hourly sono state aggregate come totale mensile,
  producendo valori ~30x piu alti del previsto.

Questo script NON riscarica nulla. Divide solo i mesi indicati per il numero di
giorni del mese, riallineando i valori futuri alla scala storica del BioCube.

Uso tipico:
    python scripts/repair_future_climate_a_scale.py --years 2021 2022 2023
    python scripts/repair_future_climate_a_scale.py --years 2024 2025 --dry-run
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import pandas as pd
import xarray as xr
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TARGET_RELATIVE_PATH = (
    Path("Copernicus")
    / "ERA5-monthly"
    / "era5-climate-energy-moisture"
    / "era5-climate-energy-moisture-0.nc"
)
ACCUMULATION_VARS = ("tp", "csfr", "smlt")


def resolve_biocube_dir(cli_path: Path | None) -> Path:
    if cli_path is not None:
        return cli_path.expanduser().resolve()
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    value = os.getenv("BIOCUBE_DIR")
    if not value:
        raise SystemExit("BIOCUBE_DIR non impostata in .env e nessun --biocube-dir fornito.")
    return Path(value).expanduser().resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Corregge la scala di climate_a per mesi futuri gia aggregati come totale mensile.",
    )
    parser.add_argument("--years", type=int, nargs="+", required=True, help="Anni futuri da correggere.")
    parser.add_argument("--biocube-dir", type=Path, default=None, help="Override di BIOCUBE_DIR.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra i mesi coinvolti senza scrivere.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Forza la correzione anche se il range risulta gia registrato nei metadata.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    years = sorted(set(args.years))
    biocube_dir = resolve_biocube_dir(args.biocube_dir)
    dataset_path = biocube_dir / TARGET_RELATIVE_PATH

    if not dataset_path.exists():
        raise SystemExit(f"File climate_a non trovato: {dataset_path}")

    repair_tag = f"{years[0]}-{years[-1]}"
    print(f"Dataset: {dataset_path}")
    print(f"Anni richiesti: {', '.join(str(year) for year in years)}")

    with xr.open_dataset(dataset_path, engine="netcdf4") as ds:
        ds = ds.load()

    valid_times = pd.to_datetime(ds["valid_time"].values)
    selected_positions = [idx for idx, ts in enumerate(valid_times) if int(ts.year) in years]
    if not selected_positions:
        raise SystemExit("Nessun mese del file corrisponde agli anni richiesti.")

    repaired_ranges = ds.attrs.get("future_climate_a_scale_repaired_ranges", "")
    repaired_tokens = {token.strip() for token in repaired_ranges.split(",") if token.strip()}
    if repair_tag in repaired_tokens and not args.force:
        raise SystemExit(
            f"Il range {repair_tag} risulta gia corretto nei metadata. "
            "Usa --force solo se sei certo di doverlo riapplicare."
        )

    selected_months = [valid_times[idx] for idx in selected_positions]
    print(f"Mesi coinvolti: {selected_months[0].strftime('%Y-%m')} -> {selected_months[-1].strftime('%Y-%m')}")

    if args.dry_run:
        for ts in selected_months[:12]:
            print(f"  [dry-run] {ts.strftime('%Y-%m')} / giorni={ts.days_in_month}")
        if len(selected_months) > 12:
            print(f"  ... altri {len(selected_months) - 12} mesi")
        return

    for pos in selected_positions:
        ts = valid_times[pos]
        days_in_month = float(ts.days_in_month)
        for var in ACCUMULATION_VARS:
            if var not in ds.data_vars:
                continue
            ds[var][pos, ...] = ds[var].isel(valid_time=pos) / days_in_month

    repaired_tokens.add(repair_tag)
    ds.attrs["future_climate_a_scale_repaired_ranges"] = ",".join(sorted(repaired_tokens))
    ds.attrs["future_climate_a_scale_repair_note"] = (
        "tp/csfr/smlt future months normalized from monthly total to monthly mean daily accumulation"
    )
    for var in ACCUMULATION_VARS:
        if var in ds.data_vars:
            ds[var].attrs["units"] = "m day-1"
            ds[var].attrs["aggregation_note"] = (
                "future months normalized to monthly mean daily accumulation"
            )

    backup_path = dataset_path.with_suffix(".nc.pre_scale_fix.bak")
    if not backup_path.exists():
        print(f"Backup: {backup_path}")
        shutil.copy2(dataset_path, backup_path)

    print(f"Scrittura: {dataset_path}")
    encoding = {var: {"zlib": True, "complevel": 4} for var in ds.data_vars}
    ds.to_netcdf(dataset_path, encoding=encoding)
    print("Correzione completata.")


if __name__ == "__main__":
    main()
