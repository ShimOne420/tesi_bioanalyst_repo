#!/usr/bin/env python3
"""Converte i tile raw WEkEO di Forest/Agriculture nel formato BioCube.

Uso tipico:

  python scripts/extend_agriculture_forest_to_2025.py \
    --source-root data/staging/agriculture_forest \
    --datasets forest \
    --years 2022 2023 \
    --dry-run

Supporta i dataset scaricati via WEkEO REST/HDA nelle cartelle:

  - forest_bulk/tcd_YYYY_query/*.zip
  - agriculture_bulk/crop_types_YYYY_query/*.zip

e aggiorna i target BioCube:

  - data/biocube/Forest/Europe_forest_data.csv
  - data/biocube/Agriculture/Europe_combined_agriculture_data.csv
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from minimum_indicator_utils import snap_coordinates_to_grid

try:
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.enums import Resampling
    from rasterio.transform import from_origin
    from rasterio.warp import reproject
except ImportError:  # pragma: no cover
    rasterio = None
    MemoryFile = None
    Resampling = None
    from_origin = None
    reproject = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BIOCUBE_DIR = PROJECT_ROOT / "data" / "biocube"
DEFAULT_YEARS = [2022, 2023, 2024, 2025]
OFFICIAL_CUTOFF_YEAR = 2023
GRID_STEP_DEGREES = 0.25
TARGET_HEIGHT = 160
TARGET_WIDTH = 280
MODEL_BOUNDS = {
    "min_lat": 32.0,
    "max_lat": 72.0,
    "min_lon": -25.0,
    "max_lon": 45.0,
}
MODEL_AGRICULTURE_VARS = ["Agriculture", "Arable", "Cropland"]
MODEL_FOREST_VARS = ["Forest"]
TIFF_SUFFIXES = {".tif", ".tiff"}

AGRICULTURE_ARABLE_CODES = {
    1110, 1120, 1130, 1140, 1150,
    1210, 1220, 1310, 1320,
    1410, 1420, 1430, 1440,
    3100,
}
AGRICULTURE_CROPLAND_CODES = {
    1110, 1120, 1130, 1140, 1150,
    1210, 1220, 1310, 1320,
    1410, 1420, 1430, 1440,
    2100, 2200, 2310, 2320,
    3100, 3200,
}

TARGETS: dict[str, dict[str, Any]] = {
    "agriculture": {
        "relative_path": Path("Agriculture") / "Europe_combined_agriculture_data.csv",
        "sidecar_name": "Europe_combined_agriculture_data.provenance.json",
        "key_columns": ["Latitude", "Longitude", "Variable"],
        "year_prefix": "Agri",
    },
    "forest": {
        "relative_path": Path("Forest") / "Europe_forest_data.csv",
        "sidecar_name": "Europe_forest_data.provenance.json",
        "key_columns": ["Latitude", "Longitude"],
        "year_prefix": "Forest",
    },
}


def timestamp_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def year_column_name(prefix: str, year: int) -> str:
    return f"{prefix}_{year}"


def model_latitudes() -> np.ndarray:
    return np.round(
        MODEL_BOUNDS["max_lat"] - np.arange(TARGET_HEIGHT, dtype=np.float32) * GRID_STEP_DEGREES,
        2,
    )


def model_longitudes() -> np.ndarray:
    return np.round(
        MODEL_BOUNDS["min_lon"] + np.arange(TARGET_WIDTH, dtype=np.float32) * GRID_STEP_DEGREES,
        2,
    )


def target_grid_transform() -> Any:
    if from_origin is None:
        raise ImportError("Manca rasterio: installa `pip install rasterio`.")
    return from_origin(
        MODEL_BOUNDS["min_lon"] - GRID_STEP_DEGREES / 2.0,
        MODEL_BOUNDS["max_lat"] + GRID_STEP_DEGREES / 2.0,
        GRID_STEP_DEGREES,
        GRID_STEP_DEGREES,
    )


def source_description(source: Any) -> str:
    if isinstance(source, list):
        if not source:
            return "[]"
        return f"{Path(source[0]).parent} ({len(source)} archive)"
    return str(source)


def read_existing_target(path: Path, dataset_kind: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"File target mancante per {dataset_kind}: {path}")
    frame = pd.read_csv(path)
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
    return {"records": []}


def write_sidecar(path: Path, dataset_kind: str, target_path: Path, records: list[dict[str, Any]]) -> None:
    payload = {
        "dataset": dataset_kind,
        "target_path": str(target_path),
        "updated_at": timestamp_now(),
        "records": sorted(records, key=lambda item: int(item["year"])),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def provenance_record(*, year: int, mode: str, source_year: int, source_file: str) -> dict[str, Any]:
    return {
        "year": int(year),
        "mode": mode,
        "source_year": int(source_year),
        "source_file": source_file,
        "ingested_at": timestamp_now(),
    }


def ensure_backup(path: Path) -> None:
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup)


def raw_query_dir_name(dataset_kind: str, year: int) -> str:
    if dataset_kind == "forest":
        return f"tcd_{year}_query"
    if dataset_kind == "agriculture":
        return f"crop_types_{year}_query"
    raise ValueError(f"Dataset non supportato: {dataset_kind}")


def collect_raw_query_archives(query_dir: Path) -> list[Path]:
    archives = sorted(query_dir.glob("*.zip"), key=lambda item: item.name.casefold())
    if archives:
        return archives
    rasters = sorted(
        [path for path in query_dir.rglob("*") if path.is_file() and path.suffix.casefold() in TIFF_SUFFIXES],
        key=lambda item: item.as_posix().casefold(),
    )
    if rasters:
        return rasters
    raise FileNotFoundError(
        f"Nessun archive .zip o raster .tif trovato in {query_dir}. "
        "Verifica che il download WEkEO sia completo e che i file veri siano presenti."
    )


def find_raw_year_sources(dataset_kind: str, source_root: Path, years: list[int]) -> dict[int, list[Path]]:
    bulk_dir = source_root / f"{dataset_kind}_bulk"
    if not bulk_dir.exists():
        raise FileNotFoundError(f"Cartella bulk non trovata per {dataset_kind}: {bulk_dir}")
    resolved: dict[int, list[Path]] = {}
    for year in years:
        query_dir = bulk_dir / raw_query_dir_name(dataset_kind, year)
        if query_dir.exists():
            resolved[year] = collect_raw_query_archives(query_dir)
    return resolved


def iter_raster_datasets(tile_paths: list[Path]):
    if rasterio is None or MemoryFile is None:
        raise ImportError("Manca rasterio: installa `pip install rasterio`.")
    for tile_path in tile_paths:
        suffix = tile_path.suffix.casefold()
        if suffix in TIFF_SUFFIXES:
            with rasterio.open(tile_path) as ds:
                yield ds, tile_path.name
            continue
        if suffix != ".zip":
            raise ValueError(f"Formato non supportato: {tile_path}")
        with zipfile.ZipFile(tile_path) as archive:
            raster_members = [
                member
                for member in archive.namelist()
                if member.lower().endswith((".tif", ".tiff"))
            ]
            if not raster_members:
                raise ValueError(f"{tile_path.name}: zip senza raster .tif/.tiff")
            for member in raster_members:
                with archive.open(member) as handle:
                    payload = handle.read()
                with MemoryFile(payload) as memfile:
                    with memfile.open() as ds:
                        yield ds, f"{tile_path.name}!{member}"


def build_base_summary_from_tiles(
    tile_paths: list[Path],
    *,
    mask_builder,
    resampling: Any,
    valid_range: tuple[float, float] | None = None,
) -> np.ndarray:
    if rasterio is None or reproject is None or Resampling is None:
        raise ImportError("Manca rasterio: installa `pip install rasterio`.")

    destination = np.full((TARGET_HEIGHT, TARGET_WIDTH), np.nan, dtype=np.float32)
    destination_transform = target_grid_transform()

    for ds, source_name in iter_raster_datasets(tile_paths):
            source = ds.read(1).astype(np.float32)
            nodata = ds.nodata
            if valid_range is not None:
                lower, upper = valid_range
                source[(source < lower) | (source > upper)] = np.nan
            if nodata is not None:
                source[source == float(nodata)] = np.nan

            source_data = mask_builder(source).astype(np.float32)
            tile_destination = np.full((TARGET_HEIGHT, TARGET_WIDTH), np.nan, dtype=np.float32)
            reproject(
                source=source_data,
                destination=tile_destination,
                src_transform=ds.transform,
                src_crs=ds.crs,
                src_nodata=np.nan,
                dst_transform=destination_transform,
                dst_crs="EPSG:4326",
                dst_nodata=np.nan,
                resampling=resampling,
            )
            update_mask = np.isfinite(tile_destination)
            destination[update_mask] = tile_destination[update_mask]

    return destination


def grid_array_to_frame(array: np.ndarray, *, year_col: str, variable: str | None = None) -> pd.DataFrame:
    latitudes = model_latitudes()
    longitudes = model_longitudes()
    lat_grid = np.repeat(latitudes[:, None], TARGET_WIDTH, axis=1)
    lon_grid = np.repeat(longitudes[None, :], TARGET_HEIGHT, axis=0)
    mask = np.isfinite(array)
    frame = pd.DataFrame(
        {
            "Latitude": lat_grid[mask].astype(np.float32),
            "Longitude": lon_grid[mask].astype(np.float32),
            year_col: array[mask].astype(np.float32),
        }
    )
    frame["Latitude"] = snap_coordinates_to_grid(frame["Latitude"])
    frame["Longitude"] = snap_coordinates_to_grid(frame["Longitude"])
    if variable is not None:
        frame["Variable"] = variable
        return frame[["Latitude", "Longitude", "Variable", year_col]]
    return frame[["Latitude", "Longitude", year_col]]


def load_forest_year_frame_from_rasters(tile_paths: list[Path], year: int) -> pd.DataFrame:
    year_col = year_column_name("Forest", year)
    array = build_base_summary_from_tiles(
        tile_paths,
        mask_builder=lambda source: source,
        resampling=Resampling.average,
        valid_range=(0.0, 100.0),
    )
    frame = grid_array_to_frame(array, year_col=year_col)
    return frame.groupby(["Latitude", "Longitude"], as_index=False)[year_col].mean()


def load_agriculture_year_frame_from_rasters(tile_paths: list[Path], year: int) -> pd.DataFrame:
    year_col = year_column_name("Agri", year)

    def cropland_mask(source: np.ndarray) -> np.ndarray:
        valid = np.isfinite(source) & np.isin(source.astype(np.int32), list(AGRICULTURE_CROPLAND_CODES))
        return np.where(valid, 100.0, 0.0)

    def arable_mask(source: np.ndarray) -> np.ndarray:
        valid = np.isfinite(source) & np.isin(source.astype(np.int32), list(AGRICULTURE_ARABLE_CODES))
        return np.where(valid, 100.0, 0.0)

    cropland = build_base_summary_from_tiles(
        tile_paths,
        mask_builder=cropland_mask,
        resampling=Resampling.average,
    )
    arable = build_base_summary_from_tiles(
        tile_paths,
        mask_builder=arable_mask,
        resampling=Resampling.average,
    )
    agriculture = cropland.copy()
    combined = pd.concat(
        [
            grid_array_to_frame(agriculture, year_col=year_col, variable="Agriculture"),
            grid_array_to_frame(arable, year_col=year_col, variable="Arable"),
            grid_array_to_frame(cropland, year_col=year_col, variable="Cropland"),
        ],
        ignore_index=True,
    )
    return combined.groupby(["Latitude", "Longitude", "Variable"], as_index=False)[year_col].mean()


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
        raise KeyError(f"Colonna sorgente carry-forward mancante: {source_col}")
    if target_col in target_frame.columns and not overwrite:
        return target_frame
    if target_col not in target_frame.columns:
        target_frame[target_col] = target_frame[source_col]
    else:
        target_frame[target_col] = target_frame[source_col].where(
            target_frame[source_col].notna(),
            target_frame[target_col],
        )
    return target_frame


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
    if dataset_kind == "agriculture":
        output["Variable"] = pd.Categorical(output["Variable"], categories=MODEL_AGRICULTURE_VARS, ordered=True)
        output = output.sort_values(["Variable", "Latitude", "Longitude"], na_position="last")
        output["Variable"] = output["Variable"].astype(str)
    else:
        output = output.sort_values(["Latitude", "Longitude"], na_position="last")
    return output[ordered_columns].reset_index(drop=True)


def load_official_year_frame(dataset_kind: str, paths: list[Path], year: int) -> pd.DataFrame:
    if dataset_kind == "forest":
        return load_forest_year_frame_from_rasters(paths, year)
    if dataset_kind == "agriculture":
        return load_agriculture_year_frame_from_rasters(paths, year)
    raise ValueError(f"Dataset non supportato: {dataset_kind}")


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
    raw_sources = find_raw_year_sources(dataset_kind, source_root, official_years) if official_years else {}

    for year in official_years:
        year_col = year_column_name(config["year_prefix"], year)
        if year_col in target_frame.columns and not overwrite_years:
            print(f"  [{year}] skip: colonna gia presente ({year_col})")
            continue
        if year not in raw_sources:
            raise RuntimeError(f"{dataset_kind}: sorgente raw mancante per {year}")
        print(f"  [{year}] official <- {source_description(raw_sources[year])}")

    carry_source_year = None
    official_basis_years = sorted(set(existing_years) | set(official_years))
    official_basis_years = [year for year in official_basis_years if year <= OFFICIAL_CUTOFF_YEAR]
    if carry_years:
        if not official_basis_years:
            raise RuntimeError(f"{dataset_kind}: impossibile applicare carry-forward senza anni base")
        carry_source_year = max(official_basis_years)
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
        source_frame = load_official_year_frame(dataset_kind, raw_sources[year], year)
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
            source_file=source_description(raw_sources[year]),
        )

    if carry_source_year is not None:
        carry_source_desc = source_description(raw_sources.get(carry_source_year, [target_path]))
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
                source_file=carry_source_desc,
            )

    target_frame = sort_target_columns(target_frame, dataset_kind)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_frame.to_csv(target_path, index=False)
    write_sidecar(provenance_path, dataset_kind, target_path, list(records_by_year.values()))
    print(f"  scritto: {target_path}")
    print(f"  provenance: {provenance_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Converte i tile raw WEkEO di Forest/Agriculture nel formato BioCube.")
    parser.add_argument("--source-root", type=Path, required=True, help="Cartella staging agriculture_forest.")
    parser.add_argument("--biocube-dir", type=Path, default=DEFAULT_BIOCUBE_DIR, help="Override della cartella data/biocube.")
    parser.add_argument("--years", type=int, nargs="+", default=DEFAULT_YEARS, help="Anni da costruire.")
    parser.add_argument(
        "--datasets",
        nargs="+",
        choices=sorted(TARGETS.keys()),
        default=sorted(TARGETS.keys()),
        help="Dataset da trasformare.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Mostra i passaggi previsti senza scrivere.")
    parser.add_argument("--overwrite-years", action="store_true", help="Sovrascrive le colonne annuali gia presenti.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    source_root = args.source_root.expanduser().resolve()
    biocube_dir = args.biocube_dir.expanduser().resolve()
    years = sorted(set(int(year) for year in args.years))

    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"BioCube dir: {biocube_dir}")
    print(f"Source root: {source_root}")
    print(f"Anni richiesti: {', '.join(str(year) for year in years)}")
    print(f"Overwrite: {bool(args.overwrite_years)}")

    for dataset_kind in args.datasets:
        extend_dataset(
            dataset_kind=dataset_kind,
            source_root=source_root,
            biocube_dir=biocube_dir,
            years=years,
            dry_run=bool(args.dry_run),
            overwrite_years=bool(args.overwrite_years),
        )

    print("\n=== Conversione Agriculture/Forest completata. ===")


if __name__ == "__main__":
    main()
