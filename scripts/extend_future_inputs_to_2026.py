#!/usr/bin/env python3
"""Orchestra l'estensione completa degli input BioAnalyst fino al 2026.

Questo script non scarica direttamente dai provider: coordina gli script
specializzati gia presenti nel repo, mantenendo l'ordine corretto:

1. ERA5 monthly core per 2022-2026
2. climate_a hourly per 2022-2026
3. vegetation/LAI per 2021-2026
4. audit opzionale clean/all

Uso consigliato sulla macchina universitaria:
    python scripts/extend_future_inputs_to_2026.py --dry-run
    python scripts/extend_future_inputs_to_2026.py
    python scripts/extend_future_inputs_to_2026.py --with-audit
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def years_arg(years: list[int]) -> list[str]:
    return [str(year) for year in years]


def year_range_label(years: list[int]) -> str:
    ordered = sorted(years)
    if ordered[0] == ordered[-1]:
        return str(ordered[0])
    return f"{ordered[0]}-{ordered[-1]}"


def forecast_date_range(years: list[int]) -> tuple[str, str]:
    ordered = sorted(years)
    return f"{ordered[0]}-01-01", f"{ordered[-1]}-12-01"


def run_step(label: str, command: list[str], *, dry_plan: bool = False) -> None:
    print(f"\n{'=' * 72}")
    print(label)
    print(f"{'=' * 72}")
    print(" ".join(command))
    if dry_plan:
        return
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estende tutti gli input futuri BioAnalyst necessari per hindcast 2021-2026.",
    )
    parser.add_argument(
        "--era5-years",
        type=int,
        nargs="+",
        default=[2022, 2023, 2024, 2025, 2026],
        help="Anni per surface/edaphic/atmospheric/climate_b e climate_a.",
    )
    parser.add_argument(
        "--vegetation-years",
        type=int,
        nargs="+",
        default=[2021, 2022, 2023, 2024, 2025, 2026],
        help="Anni per ERA5-Land vegetation LAI.",
    )
    parser.add_argument("--biocube-dir", type=Path, default=None, help="Override di BIOCUBE_DIR.")
    parser.add_argument("--tmp-dir", type=Path, default=None, help="Cartella temporanea condivisa per i download.")
    parser.add_argument("--dry-run", action="store_true", help="Passa --dry-run agli script di estensione.")
    parser.add_argument("--plan-only", action="store_true", help="Stampa i comandi senza eseguirli.")
    parser.add_argument("--with-audit", action="store_true", help="Esegue audit clean/all dopo l'estensione.")
    parser.add_argument("--skip-era5-monthly", action="store_true", help="Salta surface/edaphic/atmospheric/climate_b.")
    parser.add_argument("--skip-climate-a", action="store_true", help="Salta climate_a_hourly.")
    parser.add_argument("--skip-vegetation", action="store_true", help="Salta vegetation/LAI.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    python = sys.executable
    dry_plan = bool(args.plan_only)
    era5_years = sorted(args.era5_years)
    vegetation_years = sorted(args.vegetation_years)
    all_years = sorted(set(era5_years) | set(vegetation_years))
    era5_label = year_range_label(era5_years)
    vegetation_label = year_range_label(vegetation_years)
    all_label = year_range_label(all_years)

    common_paths: list[str] = []
    if args.biocube_dir is not None:
        common_paths.extend(["--biocube-dir", str(args.biocube_dir)])
    if args.tmp_dir is not None:
        common_paths.extend(["--tmp-dir", str(args.tmp_dir)])

    if not args.skip_era5_monthly:
        command = [
            python,
            "scripts/extend_era5_to_2026.py",
            "--years",
            *years_arg(era5_years),
            "--target",
            "all_monthly",
            *common_paths,
        ]
        if args.dry_run:
            command.append("--dry-run")
        run_step(f"Step 1/4 - ERA5 monthly core {era5_label}", command, dry_plan=dry_plan)

    if not args.skip_climate_a:
        command = [
            python,
            "scripts/extend_era5_to_2026.py",
            "--years",
            *years_arg(era5_years),
            "--target",
            "climate_a_hourly",
            *common_paths,
        ]
        if args.dry_run:
            command.append("--dry-run")
        run_step(f"Step 2/4 - climate_a hourly {era5_label}", command, dry_plan=dry_plan)

    if not args.skip_vegetation:
        command = [
            python,
            "scripts/extend_vegetation_to_2026.py",
            "--years",
            *years_arg(vegetation_years),
            *common_paths,
        ]
        if args.dry_run:
            command.append("--dry-run")
        run_step(f"Step 3/4 - vegetation LAI {vegetation_label}", command, dry_plan=dry_plan)

    if args.with_audit:
        audit_common = []
        if args.biocube_dir is not None:
            audit_common.extend(["--biocube-dir", str(args.biocube_dir)])

        clean_start, clean_end = forecast_date_range(era5_years)
        all_start, all_end = forecast_date_range(all_years)
        clean_output = f"outputs/dataset_audit_clean_{era5_label.replace('-', '_')}"
        all_output = f"outputs/dataset_audit_all_{all_label.replace('-', '_')}"

        clean_command = [
            python,
            "scripts/audit_future_dataset_coverage.py",
            "--input-mode",
            "clean",
            "--forecast-start",
            clean_start,
            "--forecast-end",
            clean_end,
            "--output-dir",
            clean_output,
            *audit_common,
        ]
        run_step(f"Step 4a/4 - audit clean {era5_label}", clean_command, dry_plan=dry_plan)

        all_command = [
            python,
            "scripts/audit_future_dataset_coverage.py",
            "--input-mode",
            "all",
            "--forecast-start",
            all_start,
            "--forecast-end",
            all_end,
            "--output-dir",
            all_output,
            *audit_common,
        ]
        run_step(
            f"Step 4b/4 - audit all {all_label}",
            all_command,
            dry_plan=dry_plan,
        )

    print(f"\n{'=' * 72}")
    print("Workflow estensione input futuri completato.")
    print(f"{'=' * 72}")


if __name__ == "__main__":
    main()
