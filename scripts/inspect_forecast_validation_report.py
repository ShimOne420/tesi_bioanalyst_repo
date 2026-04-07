#!/usr/bin/env python3
"""Legge e interpreta un report di validazione clima gia prodotto.

Questo script serve quando il run di validazione e gia terminato e vogliamo:

- vedere rapidamente le metriche globali;
- capire quali citta o aree vanno meglio e peggio;
- trovare i file giusti senza cercare a mano negli output;
- salvare un breve report Markdown da condividere con il team.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from bioanalyst_model_utils import load_project_env, require_path


# Costruiamo una CLI semplice: possiamo puntare una cartella run specifica o usare l'ultima disponibile.
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ispeziona un report di validazione clima gia generato.")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Cartella del run da leggere. Se omessa, usa l'ultimo run disponibile.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Quante citta/aree mostrare tra migliori e peggiori.",
    )
    return parser


# Cerchiamo l'ultimo run valido scandendo i summary JSON gia scritti negli output.
def resolve_run_dir(run_dir_arg: str | None) -> Path:
    if run_dir_arg:
        run_dir = Path(run_dir_arg).expanduser().resolve()
        if not run_dir.exists():
            raise SystemExit(f"Cartella run non trovata: {run_dir}")
        return run_dir

    load_project_env()
    project_output_dir = require_path("PROJECT_OUTPUT_DIR")
    summaries = sorted(
        (project_output_dir / "model_forecast").glob("**/forecast_validation_climate_summary.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not summaries:
        raise SystemExit("Nessun report `forecast_validation_climate_summary.json` trovato negli output.")
    return summaries[0].parent


# Apriamo JSON, city summary e cases scegliendo prima XLSX e poi CSV come fallback.
def load_run_artifacts(run_dir: Path) -> tuple[dict[str, object], pd.DataFrame, pd.DataFrame]:
    summary_path = run_dir / "forecast_validation_climate_summary.json"
    city_xlsx = run_dir / "forecast_validation_climate_city_summary.xlsx"
    city_csv = run_dir / "forecast_validation_climate_city_summary.csv"
    cases_xlsx = run_dir / "forecast_validation_climate_cases.xlsx"
    cases_csv = run_dir / "forecast_validation_climate_cases.csv"

    if not summary_path.exists():
        raise SystemExit(f"Summary JSON mancante: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if city_xlsx.exists():
        city_df = pd.read_excel(city_xlsx)
    elif city_csv.exists():
        city_df = pd.read_csv(city_csv)
    else:
        raise SystemExit(f"City summary mancante in {run_dir}")

    if cases_xlsx.exists():
        cases_df = pd.read_excel(cases_xlsx)
    elif cases_csv.exists():
        cases_df = pd.read_csv(cases_csv)
    else:
        raise SystemExit(f"Cases table mancante in {run_dir}")

    return summary, city_df, cases_df


# Selezioniamo best e worst performer per temperatura e precipitazione.
def build_rankings(city_df: pd.DataFrame, limit: int) -> dict[str, pd.DataFrame]:
    if city_df.empty:
        return {
            "best_temperature": city_df,
            "worst_temperature": city_df,
            "best_precipitation": city_df,
            "worst_precipitation": city_df,
        }

    sorted_temp = city_df.sort_values(["temperature_mae_c", "label"], ascending=[True, True])
    sorted_precip = city_df.sort_values(["precipitation_mean_smape_pct", "label"], ascending=[True, True])
    return {
        "best_temperature": sorted_temp.head(limit),
        "worst_temperature": sorted_temp.tail(limit).sort_values(["temperature_mae_c", "label"], ascending=[False, True]),
        "best_precipitation": sorted_precip.head(limit),
        "worst_precipitation": sorted_precip.tail(limit).sort_values(
            ["precipitation_mean_smape_pct", "label"], ascending=[False, True]
        ),
    }


# Convertiamo una tabella corta in blocco Markdown leggibile e riusabile nel README o nei report.
def dataframe_to_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_nessun dato disponibile_"
    return frame.to_markdown(index=False)


# Salviamo un report Markdown dentro la cartella del run, cosi resta vicino ai file originali.
def write_markdown_report(
    run_dir: Path,
    summary: dict[str, object],
    city_df: pd.DataFrame,
    rankings: dict[str, pd.DataFrame],
) -> Path:
    overall = summary.get("overall_summary", {})
    metadata_lines = [
        "# Report Validazione Forecast Clima",
        "",
        f"- run_dir: `{run_dir}`",
        f"- checkpoint: `{summary.get('checkpoint_kind', 'unknown')}`",
        f"- device: `{summary.get('device', 'unknown')}`",
        f"- casi: `{overall.get('cases', 'n/a')}`",
        f"- citta_aree: `{overall.get('cities', 'n/a')}`",
        f"- temperatura_mae_media_c: `{overall.get('temperature_mae_c_mean', 'n/a')}`",
        f"- temperatura_pct_error_kelvin_media: `{overall.get('temperature_pct_error_kelvin_mean', 'n/a')}`",
        f"- precipitazione_mae_media_mm: `{overall.get('precipitation_mae_mm_mean', 'n/a')}`",
        f"- precipitazione_smape_media_pct: `{overall.get('precipitation_smape_pct_mean', 'n/a')}`",
        f"- quota_casi_temp_sotto_soglia_pct: `{overall.get('temperature_pass_share_pct', 'n/a')}`",
        f"- quota_casi_temp_sotto_soglia_abs: `{overall.get('temperature_pass_share_abs', 'n/a')}`",
        f"- quota_casi_precip_sotto_soglia_pct: `{overall.get('precipitation_pass_share_pct', 'n/a')}`",
        f"- quota_casi_precip_sotto_soglia_abs: `{overall.get('precipitation_pass_share_abs', 'n/a')}`",
        f"- quota_citta_pass_completo: `{overall.get('city_climate_pass_share', 'n/a')}`",
        "",
        "## Riassunto Per Citta",
        "",
        dataframe_to_markdown(city_df),
        "",
        "## Migliori Citta Per Temperatura",
        "",
        dataframe_to_markdown(rankings["best_temperature"]),
        "",
        "## Peggiori Citta Per Temperatura",
        "",
        dataframe_to_markdown(rankings["worst_temperature"]),
        "",
        "## Migliori Citta Per Precipitazione",
        "",
        dataframe_to_markdown(rankings["best_precipitation"]),
        "",
        "## Peggiori Citta Per Precipitazione",
        "",
        dataframe_to_markdown(rankings["worst_precipitation"]),
        "",
    ]
    report_path = run_dir / "forecast_validation_climate_report.md"
    report_path.write_text("\n".join(metadata_lines), encoding="utf-8")
    return report_path


# Stampiamo un riepilogo da terminale che aiuta a decidere subito se il blocco clima e credibile o no.
def print_terminal_summary(
    run_dir: Path,
    summary: dict[str, object],
    report_path: Path,
    rankings: dict[str, pd.DataFrame],
) -> None:
    overall = summary.get("overall_summary", {})
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nRUN DIR: {run_dir}")
    print(f"REPORT MD: {report_path}")

    if not rankings["best_temperature"].empty:
        best_temp = rankings["best_temperature"].iloc[0]
        worst_temp = rankings["worst_temperature"].iloc[0]
        best_precip = rankings["best_precipitation"].iloc[0]
        worst_precip = rankings["worst_precipitation"].iloc[0]

        print("\nBEST TEMPERATURE:")
        print(best_temp.to_string())
        print("\nWORST TEMPERATURE:")
        print(worst_temp.to_string())
        print("\nBEST PRECIPITATION:")
        print(best_precip.to_string())
        print("\nWORST PRECIPITATION:")
        print(worst_precip.to_string())

    print("\nOVERALL:")
    print(
        json.dumps(
            {
                "temperature_mae_c_mean": overall.get("temperature_mae_c_mean"),
                "temperature_pct_error_kelvin_mean": overall.get("temperature_pct_error_kelvin_mean"),
                "precipitation_mae_mm_mean": overall.get("precipitation_mae_mm_mean"),
                "precipitation_smape_pct_mean": overall.get("precipitation_smape_pct_mean"),
                "temperature_pass_share_pct": overall.get("temperature_pass_share_pct"),
                "temperature_pass_share_abs": overall.get("temperature_pass_share_abs"),
                "precipitation_pass_share_pct": overall.get("precipitation_pass_share_pct"),
                "precipitation_pass_share_abs": overall.get("precipitation_pass_share_abs"),
                "city_climate_pass_share": overall.get("city_climate_pass_share"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )


# Coordiniamo tutta l'ispezione del report, dalla ricerca del run fino alla scrittura del Markdown.
def main() -> None:
    args = build_parser().parse_args()
    run_dir = resolve_run_dir(args.run_dir)
    summary, city_df, cases_df = load_run_artifacts(run_dir)
    rankings = build_rankings(city_df=city_df, limit=args.limit)
    report_path = write_markdown_report(run_dir=run_dir, summary=summary, city_df=city_df, rankings=rankings)
    print_terminal_summary(run_dir=run_dir, summary=summary, report_path=report_path, rankings=rankings)
    print(f"\nCASES: {len(cases_df)}")
    print(f"CITY_ROWS: {len(city_df)}")


# Rendiamo lo script eseguibile dal terminale di VS Code e anche comodo dopo un run Colab.
if __name__ == "__main__":
    main()
