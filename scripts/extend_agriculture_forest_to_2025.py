#!/usr/bin/env python3
"""Estende Agriculture/Forest BioCube fino al 2025 da file tabulari staged.

Questo script non scarica da provider esterni. Si aspetta invece una cartella
`source_root` con file ufficiali gia scaricati in formato tabellare
(`.csv/.parquet/.xlsx`) e li converte nel formato BioCube gia usato dal loader:

- Agriculture/Europe_combined_agriculture_data.csv con colonne `Agri_YYYY`
- Forest/Europe_forest_data.csv con colonne `Forest_YYYY`

Assunzioni del v1:
- 2022-2023 arrivano da staging ufficiale
- 2024-2025 usano carry-forward dell'ultimo anno ufficiale disponibile
- nessuna modifica al formato runtime del modello
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from extend_era5_to_2026 import PROJECT_ROOT, resolve_biocube_dir
from minimum_indicator_utils import snap_coordinates_to_grid


DEFAULT_YEARS = [2022, 2023, 2024, 2025]
OFFICIAL_CUTOFF_YEAR = 2023
SUPPORTED_SUFFIXES = {".csv", ".parquet", ".pq", ".xlsx", ".xls", ".xlsm"}
MODEL_BOUNDS = {
    "min_lat": 32.0,
    "max_lat": 72.0,
    "min_lon": -25.0,
    "max_lon": 45.0,
}
MODEL_AGRICULTURE_VARS = ["Agriculture", "Arable", "Cropland"]
MODEL_FOREST_VARS = ["Forest"]

TARGETS: dict[str, dict[str, Any]] = {
    "agriculture": {
        "relative_path": Path("Agriculture") / "Europe_combined_agriculture_data.csv",
        "sidecar_name": "Europe_combined_agriculture_data.provenance.json",
        "key_columns": ["Latitude", "Longitude", "Variable"],
        "year_prefix": "Agri",
        "required_variables": MODEL_AGRICULTURE_VARS,
        "search_tokens": ("agri", "agriculture", "cropland", "arable"),
    },
    "forest": {
        "relative_path": Path("Forest") / "Europe_forest_data.csv",
        "sidecar_name": "Europe_forest_data.provenance.json",
        "key_columns": ["Latitude", "Longitude"],
        "year_prefix": "Forest",
        "required_variables": MODEL_FOREST_VARS,
        "search_tokens": ("forest", "treecover", "tree_cover"),
    },
}

COORDINATE_ALIASES = {
    "latitude": "Latitude",
    "lat": "Latitude",
    "y": "Latitude",
    "longitude": "Longitude",
    "lon": "Longitude",
    "lng": "Longitude",
    "x": "Longitude",
}

AGRICULTURE_VARIABLE_ALIASES = {
    "agriculture": "Agriculture",
    "agricultural": "Agriculture",
    "arable": "Arable",
    "arableland": "Arable",
    "arablelands": "Arable",
    "cropland": "Cropland",
    "croplands": "Cropland",
    "crop": "Cropland",
    "croplandshare": "Cropland",
}

FOREST_VARIABLE_ALIASES = {
    "forest": "Forest",
    "forestcover": "Forest",
    "forestdensity": "Forest",
    "treecover": "Forest",
    "treecoverdensity": "Forest",
}

VALUE_COLUMN_CANDIDATES = (
    "value",
    "percentage",
    "percent",
    "share",
    "fraction",
    "coverage",
    "cover",
    "mean",
)


def normalize_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def timestamp_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonicalize_agriculture_variable(value: Any) -> str | None:
    token = normalize_token(value)
    return AGRICULTURE_VARIABLE_ALIASES.get(token)


def canonicalize_forest_variable(value: Any) -> str | None:
    token = normalize_token(value)
    return FOREST_VARIABLE_ALIASES.get(token)


def rename_coordinate_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in frame.columns:
        canonical = COORDINATE_ALIASES.get(normalize_token(column))
        if canonical and column != canonical:
            rename_map[column] = canonical
    return frame.rename(columns=rename_map)


def prepare_yearly_grid_frame(frame: pd.DataFrame, source_name: str) -> pd.DataFrame:
    required_columns = {"Latitude", "Longitude"}
    missing_columns = required_columns.difference(frame.columns)
    if missing_columns:
        raise KeyError(f"Colonne mancanti in {source_name}: {sorted(missing_columns)}")
    prepared = frame.copy()
    prepared["Latitude"] = snap_coordinates_to_grid(prepared["Latitude"])
    prepared["Longitude"] = snap_coordinates_to_grid(prepared["Longitude"])
    return prepared[
        prepared["Latitude"].between(MODEL_BOUNDS["min_lat"], MODEL_BOUNDS["max_lat"])
        & prepared["Longitude"].between(MODEL_BOUNDS["min_lon"], MODEL_BOUNDS["max_lon"])
    ]


def match_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    lookup = {normalize_token(column): str(column) for column in columns}
    for candidate in candidates:
        match = lookup.get(normalize_token(candidate))
        if match is not None:
            return match
    return None


def year_column_name(prefix: str, year: int) -> str:
    return f"{prefix}_{year}"


def sidecar_path(target_path: Path) -> Path:
    config = next(item for item in TARGETS.values() if item["relative_path"].name == target_path.name)
    return target_path.with_name(config["sidecar_name"])


def read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        return pd.read_excel(path)
    raise ValueError(f"Formato non supportato: {path}")


def read_existing_target(path: Path, dataset_kind: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File target mancante per {dataset_kind}: {path}")
    frame = pd.read_csv(path)
    frame = rename_coordinate_columns(frame)
    required = set(TARGETS[dataset_kind]["key_columns"])
    missing = required.difference(frame.columns)
    if missing:
        raise KeyError(f"{path.name}: colonne chiave mancanti {sorted(missing)}")
    return frame


def read_existing_sidecar(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"records": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"records": payload}
    if isinstance(payload, dict):
        payload.setdefault("records", [])
        return payload
    raise ValueError(f"Formato sidecar non riconosciuto: {path}")


def write_sidecar(path: Path, dataset_kind: str, target_path: Path, records: list[dict[str, Any]]) -> None:
    payload = {
        "dataset": dataset_kind,
        "target_path": str(target_path),
        "updated_at": timestamp_now(),
        "records": sorted(records, key=lambda item: int(item["year"])),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def find_stage_candidates(source_root: Path, dataset_kind: str) -> list[Path]:
    config = TARGETS[dataset_kind]
    search_tokens = config["search_tokens"]
    preferred_dirs = [source_root / dataset_kind, source_root / dataset_kind.capitalize()]
    paths: list[Path] = []
    for preferred_dir in preferred_dirs:
        if preferred_dir.exists():
            paths.extend(path for path in preferred_dir.rglob("*") if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES)
    if not paths:
        paths.extend(path for path in source_root.rglob("*") if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES)
        paths = [path for path in paths if any(token in path.as_posix().casefold() for token in search_tokens)]
    unique = sorted(dict.fromkeys(path.resolve() for path in paths), key=lambda item: item.as_posix().casefold())
    return unique


def infer_years_from_path(path: Path) -> set[int]:
    return {int(match.group(1)) for match in re.finditer(r"(19|20)\d{2}", path.as_posix())}


def candidate_sort_key(path: Path, dataset_kind: str, year: int) -> tuple[int, int, str]:
    token_score = 0 if any(token in path.as_posix().casefold() for token in TARGETS[dataset_kind]["search_tokens"]) else 1
    year_score = 0 if year in infer_years_from_path(path) else 1
    return (token_score, year_score, path.as_posix().casefold())


def choose_value_column(frame: pd.DataFrame, ignored_columns: set[str]) -> str:
    for candidate in VALUE_COLUMN_CANDIDATES:
        match = match_column(frame.columns.tolist(), (candidate,))
        if match is not None and match not in ignored_columns:
            return match
    numeric_candidates = [
        str(column)
        for column in frame.columns
        if str(column) not in ignored_columns and pd.api.types.is_numeric_dtype(frame[column])
    ]
    if len(numeric_candidates) == 1:
        return numeric_candidates[0]
    raise KeyError(
        "Impossibile individuare una colonna valore univoca. "
        f"Colonne numeriche candidate: {numeric_candidates}"
    )


def coerce_year_filter(frame: pd.DataFrame, year: int, *, source_label: str) -> pd.DataFrame:
    year_col = match_column(frame.columns.tolist(), ("Year", "Anno"))
    if year_col is None:
        return frame
    year_series = pd.to_numeric(frame[year_col], errors="coerce")
    filtered = frame.loc[year_series == year].copy()
    if filtered.empty:
        raise ValueError(f"{source_label}: nessuna riga trovata per l'anno {year}")
    return filtered


def finalize_year_frame(
    frame: pd.DataFrame,
    *,
    dataset_kind: str,
    year: int,
    source_label: str,
) -> pd.DataFrame:
    prepared = prepare_yearly_grid_frame(frame, source_label).copy()
    prefix = TARGETS[dataset_kind]["year_prefix"]
    year_col = year_column_name(prefix, year)
    key_columns = TARGETS[dataset_kind]["key_columns"]
    if dataset_kind == "agriculture":
        prepared["Variable"] = prepared["Variable"].map(canonicalize_agriculture_variable)
        prepared = prepared[prepared["Variable"].isin(TARGETS[dataset_kind]["required_variables"])].copy()
    grouped = prepared.groupby(key_columns, as_index=False)[year_col].mean()
    if grouped.empty:
        raise ValueError(f"{source_label}: nessuna cella utile dopo snap/crop alla griglia modello")
    return grouped


def load_agriculture_year_frame(path: Path, year: int) -> pd.DataFrame:
    source_label = f"agriculture staging {path.name} ({year})"
    frame = rename_coordinate_columns(read_table(path))
    columns = frame.columns.tolist()
    year_col = year_column_name("Agri", year)
    source_year_col = match_column(columns, (year_col,))
    variable_col = match_column(columns, ("Variable", "Layer", "Class", "Category"))

    if variable_col is not None and source_year_col is not None:
        sliced = frame[["Latitude", "Longitude", variable_col, source_year_col]].copy()
        sliced = sliced.rename(columns={variable_col: "Variable", source_year_col: year_col})
        return finalize_year_frame(sliced, dataset_kind="agriculture", year=year, source_label=source_label)

    wide_variable_columns = {
        canonical: match_column(columns, (canonical,))
        for canonical in MODEL_AGRICULTURE_VARS
    }
    wide_variable_columns = {canonical: column for canonical, column in wide_variable_columns.items() if column is not None}

    if wide_variable_columns:
        sliced = coerce_year_filter(frame, year, source_label=source_label)
        melted = sliced[["Latitude", "Longitude", *wide_variable_columns.values()]].melt(
            id_vars=["Latitude", "Longitude"],
            value_vars=list(wide_variable_columns.values()),
            var_name="_wide_variable",
            value_name=year_col,
        )
        reverse_lookup = {column: variable for variable, column in wide_variable_columns.items()}
        melted["Variable"] = melted["_wide_variable"].map(reverse_lookup)
        return finalize_year_frame(
            melted[["Latitude", "Longitude", "Variable", year_col]],
            dataset_kind="agriculture",
            year=year,
            source_label=source_label,
        )

    if variable_col is None:
        raise KeyError(f"{source_label}: manca `Variable` e non trovo colonne wide Agriculture/Arable/Cropland")

    sliced = coerce_year_filter(frame, year, source_label=source_label)
    value_col = choose_value_column(sliced, {"Latitude", "Longitude", variable_col})
    normalized = sliced[["Latitude", "Longitude", variable_col, value_col]].copy()
    normalized = normalized.rename(columns={variable_col: "Variable", value_col: year_col})
    return finalize_year_frame(normalized, dataset_kind="agriculture", year=year, source_label=source_label)


def load_forest_year_frame(path: Path, year: int) -> pd.DataFrame:
    source_label = f"forest staging {path.name} ({year})"
    frame = rename_coordinate_columns(read_table(path))
    columns = frame.columns.tolist()
    year_col = year_column_name("Forest", year)
    source_year_col = match_column(columns, (year_col,))

    if source_year_col is not None:
        sliced = frame[["Latitude", "Longitude", source_year_col]].copy().rename(columns={source_year_col: year_col})
        return finalize_year_frame(sliced, dataset_kind="forest", year=year, source_label=source_label)

    forest_value_col = match_column(columns, ("Forest", "TreeCover", "ForestCover", "ForestDensity"))
    variable_col = match_column(columns, ("Variable", "Layer", "Class"))
    if forest_value_col is None and variable_col is not None:
        forest_rows = frame[frame[variable_col].map(canonicalize_forest_variable).eq("Forest")].copy()
        if not forest_rows.empty:
            forest_value_col = choose_value_column(forest_rows, {"Latitude", "Longitude", variable_col})
            sliced = coerce_year_filter(forest_rows, year, source_label=source_label)
            return finalize_year_frame(
                sliced[["Latitude", "Longitude", forest_value_col]].rename(columns={forest_value_col: year_col}),
                dataset_kind="forest",
                year=year,
                source_label=source_label,
            )

    if forest_value_col is None:
        raise KeyError(f"{source_label}: nessuna colonna `Forest`/`TreeCover` individuata")

    sliced = coerce_year_filter(frame, year, source_label=source_label)
    normalized = sliced[["Latitude", "Longitude", forest_value_col]].copy()
    normalized = normalized.rename(columns={forest_value_col: year_col})
    return finalize_year_frame(normalized, dataset_kind="forest", year=year, source_label=source_label)


def load_official_year_frame(dataset_kind: str, path: Path, year: int) -> pd.DataFrame:
    if dataset_kind == "agriculture":
        return load_agriculture_year_frame(path, year)
    if dataset_kind == "forest":
        return load_forest_year_frame(path, year)
    raise ValueError(f"Dataset non supportato: {dataset_kind}")


def find_official_year_sources(dataset_kind: str, source_root: Path, years: list[int]) -> dict[int, Path]:
    candidates = find_stage_candidates(source_root, dataset_kind)
    if not candidates:
        raise FileNotFoundError(
            f"Nessun file staged trovato per {dataset_kind} sotto {source_root}. "
            "Attesi file .csv/.parquet/.xlsx in cartelle tipo `agriculture/` o `forest/`."
        )

    resolved: dict[int, Path] = {}
    errors: dict[int, list[str]] = {year: [] for year in years}
    for year in years:
        ordered_candidates = sorted(candidates, key=lambda path: candidate_sort_key(path, dataset_kind, year))
        for candidate in ordered_candidates:
            try:
                load_official_year_frame(dataset_kind, candidate, year)
                resolved[year] = candidate
                break
            except Exception as exc:
                errors[year].append(f"{candidate.name}: {exc}")
        if year not in resolved:
            joined_errors = " | ".join(errors[year][:5])
            raise RuntimeError(
                f"Impossibile ricostruire {dataset_kind} {year} dai file staged sotto {source_root}. "
                f"Tentativi: {joined_errors}"
            )
    return resolved


def available_year_columns(frame: pd.DataFrame, prefix: str) -> list[int]:
    years = []
    pattern = re.compile(rf"{re.escape(prefix)}_(\d{{4}})$", flags=re.IGNORECASE)
    for column in frame.columns:
        match = pattern.fullmatch(str(column))
        if match:
            years.append(int(match.group(1)))
    return sorted(set(years))


def upsert_year_column(
    target_frame: pd.DataFrame,
    *,
    source_frame: pd.DataFrame,
    year_col: str,
    key_columns: list[str],
    overwrite: bool,
) -> pd.DataFrame:
    incoming_col = f"{year_col}__incoming"
    incoming = source_frame[key_columns + [year_col]].rename(columns={year_col: incoming_col})
    merged = target_frame.merge(incoming, on=key_columns, how="outer")
    if year_col not in merged.columns:
        merged[year_col] = pd.NA
    if overwrite:
        merged[year_col] = merged[incoming_col].where(merged[incoming_col].notna(), merged[year_col])
    else:
        merged[year_col] = merged[year_col].where(merged[year_col].notna(), merged[incoming_col])
    return merged.drop(columns=[incoming_col])


def apply_carry_forward(
    target_frame: pd.DataFrame,
    *,
    dataset_kind: str,
    target_year: int,
    source_year: int,
    overwrite: bool,
) -> pd.DataFrame:
    prefix = TARGETS[dataset_kind]["year_prefix"]
    source_col = year_column_name(prefix, source_year)
    target_col = year_column_name(prefix, target_year)
    if source_col not in target_frame.columns:
        raise KeyError(f"{dataset_kind}: colonna sorgente carry-forward mancante: {source_col}")
    if target_col in target_frame.columns and not overwrite:
        return target_frame
    if target_col not in target_frame.columns:
        target_frame[target_col] = target_frame[source_col]
    else:
        if overwrite:
            target_frame[target_col] = target_frame[source_col].where(target_frame[source_col].notna(), target_frame[target_col])
        else:
            target_frame[target_col] = target_frame[target_col].where(target_frame[target_col].notna(), target_frame[source_col])
    return target_frame


def ensure_backup(path: Path) -> None:
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)


def sort_target_columns(frame: pd.DataFrame, dataset_kind: str) -> pd.DataFrame:
    prefix = TARGETS[dataset_kind]["year_prefix"]
    key_columns = TARGETS[dataset_kind]["key_columns"]
    year_columns = sorted(
        [column for column in frame.columns if re.fullmatch(rf"{prefix}_\d{{4}}", str(column), flags=re.IGNORECASE)],
        key=lambda item: int(str(item).split("_")[-1]),
    )
    other_columns = [column for column in frame.columns if column not in key_columns and column not in year_columns]
    ordered_columns = key_columns + other_columns + year_columns
    output = frame.copy()
    if dataset_kind == "agriculture" and "Variable" in output.columns:
        output["Variable"] = pd.Categorical(output["Variable"], categories=MODEL_AGRICULTURE_VARS, ordered=True)
        output = output.sort_values(["Variable", "Latitude", "Longitude"], na_position="last")
        output["Variable"] = output["Variable"].astype(str)
    else:
        output = output.sort_values(["Latitude", "Longitude"], na_position="last")
    return output[ordered_columns].reset_index(drop=True)


def provenance_record(*, year: int, mode: str, source_year: int, source_file: str) -> dict[str, Any]:
    return {
        "year": int(year),
        "mode": mode,
        "source_year": int(source_year),
        "source_file": source_file,
        "ingested_at": timestamp_now(),
    }


def extend_dataset(
    *,
    dataset_kind: str,
    source_root: Path,
    biocube_dir: Path,
    years: list[int],
    dry_run: bool,
    overwrite_years: bool,
) -> None:
    config = TARGETS[dataset_kind]
    target_path = biocube_dir / config["relative_path"]
    provenance_path = target_path.with_name(config["sidecar_name"])
    print(f"\n[{dataset_kind}] target: {target_path}")
    target_frame = read_existing_target(target_path, dataset_kind)
    existing_years = available_year_columns(target_frame, config["year_prefix"])
    print(f"  anni gia presenti: {existing_years[0]}-{existing_years[-1]}" if existing_years else "  nessun anno trovato")

    official_years = [year for year in sorted(years) if year <= OFFICIAL_CUTOFF_YEAR]
    carry_years = [year for year in sorted(years) if year > OFFICIAL_CUTOFF_YEAR]
    official_sources = find_official_year_sources(dataset_kind, source_root, official_years) if official_years else {}

    for year in official_years:
        year_col = year_column_name(config["year_prefix"], year)
        if year_col in target_frame.columns and not overwrite_years:
            print(f"  [{year}] skip: colonna gia presente ({year_col})")
            continue
        source_path = official_sources[year]
        print(f"  [{year}] official <- {source_path}")

    carry_source_year = None
    combined_available_years = sorted(set(existing_years) | set(official_years))
    official_basis_years = [year for year in combined_available_years if year <= OFFICIAL_CUTOFF_YEAR]
    if carry_years:
        if not official_basis_years:
            raise RuntimeError(f"{dataset_kind}: impossibile applicare carry-forward senza almeno un anno ufficiale disponibile")
        carry_source_year = max(official_basis_years)
        carry_source_file = str(official_sources.get(carry_source_year, target_path))
        for year in carry_years:
            year_col = year_column_name(config["year_prefix"], year)
            if year_col in target_frame.columns and not overwrite_years:
                print(f"  [{year}] skip: colonna gia presente ({year_col})")
                continue
            print(f"  [{year}] carry_forward <- {carry_source_year}")

    if dry_run:
        print("  [dry-run] nessuna scrittura eseguita")
        return

    ensure_backup(target_path)
    records_by_year = {int(record["year"]): record for record in read_existing_sidecar(provenance_path).get("records", [])}

    for year in official_years:
        year_col = year_column_name(config["year_prefix"], year)
        if year_col in target_frame.columns and not overwrite_years:
            continue
        source_path = official_sources[year]
        source_frame = load_official_year_frame(dataset_kind, source_path, year)
        target_frame = upsert_year_column(
            target_frame,
            source_frame=source_frame,
            year_col=year_col,
            key_columns=config["key_columns"],
            overwrite=overwrite_years,
        )
        records_by_year[year] = provenance_record(
            year=year,
            mode="official",
            source_year=year,
            source_file=str(source_path),
        )

    if carry_source_year is not None:
        carry_source_file = str(official_sources.get(carry_source_year, target_path))
        for year in carry_years:
            year_col = year_column_name(config["year_prefix"], year)
            if year_col in target_frame.columns and not overwrite_years:
                continue
            target_frame = apply_carry_forward(
                target_frame,
                dataset_kind=dataset_kind,
                target_year=year,
                source_year=carry_source_year,
                overwrite=overwrite_years,
            )
            records_by_year[year] = provenance_record(
                year=year,
                mode="carry_forward",
                source_year=carry_source_year,
                source_file=carry_source_file,
            )

    target_frame = sort_target_columns(target_frame, dataset_kind)
    target_frame.to_csv(target_path, index=False)
    write_sidecar(provenance_path, dataset_kind, target_path, list(records_by_year.values()))
    print(f"  scritto: {target_path}")
    print(f"  provenance: {provenance_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Estende Agriculture/Forest BioCube 2022-2025 da file ufficiali staged.",
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Cartella staging con file raw ufficiali tabulari (csv/parquet/xlsx).",
    )
    parser.add_argument("--biocube-dir", type=Path, default=None, help="Override di BIOCUBE_DIR.")
    parser.add_argument("--years", type=int, nargs="+", default=DEFAULT_YEARS, help="Anni da costruire.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra i passaggi previsti senza scrivere.")
    parser.add_argument(
        "--overwrite-years",
        action="store_true",
        help="Sovrascrive le colonne annuali gia presenti invece di mantenerle.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    years = sorted(set(args.years))
    invalid_years = [year for year in years if year < 1900 or year > 2100]
    if invalid_years:
        raise SystemExit(f"Anni non validi: {invalid_years}")
    source_root = args.source_root.expanduser().resolve()
    if not source_root.exists():
        raise SystemExit(f"source_root non trovato: {source_root}")
    biocube_dir = resolve_biocube_dir(args.biocube_dir)

    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"BioCube dir: {biocube_dir}")
    print(f"Source root: {source_root}")
    print(f"Anni richiesti: {', '.join(str(year) for year in years)}")
    print(f"Overwrite: {bool(args.overwrite_years)}")

    extend_dataset(
        dataset_kind="agriculture",
        source_root=source_root,
        biocube_dir=biocube_dir,
        years=years,
        dry_run=bool(args.dry_run),
        overwrite_years=bool(args.overwrite_years),
    )
    extend_dataset(
        dataset_kind="forest",
        source_root=source_root,
        biocube_dir=biocube_dir,
        years=years,
        dry_run=bool(args.dry_run),
        overwrite_years=bool(args.overwrite_years),
    )

    print("\n=== Estensione Agriculture/Forest completata. ===")
    print("Verifica con:")
    print(
        "  python scripts/audit_future_dataset_coverage.py "
        "--input-mode all --forecast-start 2021-01-01 --forecast-end 2025-12-01"
    )


if __name__ == "__main__":
    main()
