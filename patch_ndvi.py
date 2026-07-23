#!/usr/bin/env python3
"""
Patch script to add NDVI loading capability to tesi_bioanalyst_repo.
Run this on the Windows machine: python patch_ndvi.py
"""
import sys
from pathlib import Path

# Path to the target file
target_file = Path("scripts/bioanalyst_model_utils.py")
if not target_file.exists():
    print(f"ERROR: {target_file} not found!")
    print("Please run this script from the tesi_bioanalyst_repo directory")
    sys.exit(1)

# Read the current file
content = target_file.read_text(encoding="utf-8")

# Check if already patched
if "def build_vegetation_group_from_ndvi_csv" in content:
    print("Already patched! NDVI functions already exist.")
    sys.exit(0)

# Add the necessary imports (if not already present)
if "import re" not in content:
    # Add after the existing imports
    content = content.replace(
        "import pandas as pd",
        "import pandas as pd\nimport re"
    )

# Find where to insert the new functions (before build_raw_batch_for_months)
insert_marker = "# Costruiamo il raw batch"
if insert_marker not in content:
    print("ERROR: Could not find insertion point!")
    sys.exit(1)

# The functions to add (simplified for the tesi_bioanalyst_repo which uses different MODEL_SOURCE_FILES)
new_functions = '''

# === ADDED FOR NDVI LOADING ===
def prepare_yearly_grid_frame(frame: pd.DataFrame, expected_name: str) -> pd.DataFrame:
    """Normalizziamo il frame CSV grezzo prima di usarlo per rasterizzazione."""
    prepared = frame.copy()
    prepared.columns = [str(column).strip() for column in prepared.columns]
    if "Latitude" not in prepared.columns and "latitude" in prepared.columns:
        prepared = prepared.rename(columns={"latitude": "Latitude"})
    if "Longitude" not in prepared.columns and "longitude" in prepared.columns:
        prepared = prepared.rename(columns={"longitude": "Longitude"})
    prepared["Latitude"] = snap_coordinates_to_grid(prepared["Latitude"])
    prepared["Longitude"] = snap_coordinates_to_grid(prepared["Longitude"])
    return prepared[
        prepared["Latitude"].between(MODEL_BOUNDS["min_lat"], MODEL_BOUNDS["max_lat"])
        & prepared["Longitude"].between(MODEL_BOUNDS["min_lon"], MODEL_BOUNDS["max_lon"])
    ]


def yearly_column_to_grid(
    frame: pd.DataFrame,
    column_name: str,
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> torch.Tensor:
    """Rasterizza una colonna annuale CSV in una mappa [H, W] allineata al batch."""
    if column_name not in frame.columns:
        raise KeyError(f"Colonna annuale non trovata nel dataset: {column_name}")

    lat_index = {round(float(value), 2): idx for idx, value in enumerate(latitudes)}
    lon_index = {round(float(value), 2): idx for idx, value in enumerate(longitudes)}
    tensor = torch.zeros((MODEL_HEIGHT, MODEL_WIDTH), dtype=torch.float32)

    useful = frame[["Latitude", "Longitude", column_name]].dropna(subset=[column_name])
    grouped = useful.groupby(["Latitude", "Longitude"], as_index=False)[column_name].mean()

    matched = 0
    skipped = 0
    for lat_value, lon_value, data_value in grouped[["Latitude", "Longitude", column_name]].itertuples(index=False, name=None):
        lat_key = round(float(lat_value), 2)
        lon_key = round(float(lon_value), 2)
        if lat_key not in lat_index or lon_key not in lon_index:
            skipped += 1
            continue
        tensor[lat_index[lat_key], lon_index[lon_key]] = float(data_value)
        matched += 1

    total = len(grouped)
    print(f"  [debug] yearly_column_to_grid: {matched}/{total} coordinate match (saltate {skipped}) per {column_name}", flush=True)
    if matched == 0 and total > 0:
        print(f"  [warn] Nessuna coordinata CSV allineata alla griglia del modello!", flush=True)
    return tensor


def find_monthly_column(columns: list[str], variable_name: str, month: pd.Timestamp) -> str:
    """Trova una colonna mensile in CSV BioCube accettando i formati piu probabili."""
    month = to_month_start(month)
    month_number = int(month.month)
    candidates = [
        f"{variable_name}_{month:%Y_%m}",
        f"{variable_name}_{month:%Y-%m}",
        f"{variable_name}_{month:%Y%m}",
        f"{variable_name}_{month:%Y-%m-%d}",
        f"{variable_name}_{month.year}_{month_number:02d}",
        f"{variable_name}_{month.year}-{month_number}",
        f"{variable_name}_{month_number:02d}/{month.year}",
        f"{variable_name}_{month_number}/{month.year}",
        f"{month:%Y_%m}_{variable_name}",
        f"{month:%Y-%m}_{variable_name}",
        f"{month:%Y_%m}",
        f"{month:%Y-%m}",
        f"{month:%Y%m}",
        f"{month:%Y-%m-%d}",
        f"{month.year}_{month_number}",
        f"{month.year}-{month_number}",
    ]
    lookup = {str(column).casefold(): str(column) for column in columns}
    for candidate in candidates:
        match = lookup.get(candidate.casefold())
        if match is not None:
            return match
    raise KeyError(f"Colonna mensile {variable_name} non trovata per {month:%Y-%m}")


def build_vegetation_group_from_ndvi_csv(
    ndvi_path: Path,
    months: list[pd.Timestamp],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> dict[str, torch.Tensor]:
    """Costruisce il canale NDVI dal CSV ufficiale BioCube quando e disponibile."""
    print(f"  [debug] Leggo NDVI CSV: {ndvi_path}", flush=True)
    ndvi_frame = prepare_yearly_grid_frame(pd.read_csv(ndvi_path), "ndvi")
    print(f"  [debug] NDVI CSV caricato: {len(ndvi_frame)} righe", flush=True)
    
    maps = []
    for month in months:
        column_name = find_monthly_column(ndvi_frame.columns.tolist(), "NDVI", month)
        print(f"  [debug] Using column {column_name} for {month:%Y-%m}", flush=True)
        maps.append(yearly_column_to_grid(ndvi_frame, column_name, latitudes, longitudes))
    
    return {"NDVI": torch.stack(maps)}


def build_vegetation_group_from_sources(
    source_paths: dict[str, Path],
    months: list[pd.Timestamp],
    latitudes: np.ndarray,
    longitudes: np.ndarray,
) -> dict[str, torch.Tensor]:
    """Preferisce il CSV NDVI ufficiale BioCube; altrimenti usa placeholder zero."""
    if "land_ndvi_csv" in source_paths:
        ndvi_csv_path = source_paths["land_ndvi_csv"]
        print(f"  [debug] Provo a caricare NDVI da CSV: {ndvi_csv_path}", flush=True)
        if not ndvi_csv_path.exists():
            print(f"  [warn] NDVI CSV non trovato: {ndvi_csv_path}", flush=True)
        else:
            try:
                return build_vegetation_group_from_ndvi_csv(ndvi_csv_path, months, latitudes, longitudes)
            except Exception as exc:
                print(f"  [warn] NDVI CSV non utilizzabile ({exc}); uso zero placeholder", flush=True)
    
    print(f"  [debug] Uso zero placeholder per NDVI", flush=True)
    return build_zero_group(MODEL_VEGETATION_VARS, months)


# === END OF ADDED FUNCTIONS ===

'''

# Insert the new functions
content = content.replace(
    insert_marker,
    new_functions + "\n" + insert_marker
)

# Now update line 552 to use the new function
# Find: "vegetation_variables": build_zero_group(MODEL_VEGETATION_VARS, months),
# Replace with: conditional loading

old_line = '"vegetation_variables": build_zero_group(MODEL_VEGETATION_VARS, months),'
new_line = '''"vegetation_variables": build_vegetation_group_from_sources(
            source_paths, months, latitudes, longitudes
        ),'''

if old_line in content:
    content = content.replace(old_line, new_line)
    print("Updated vegetation_variables line")
else:
    print("WARNING: Could not find the vegetation_variables line to update!")
    print("You may need to manually update line ~552")

# Write the patched file
backup_file = target_file.with_suffix(".py.backup")
target_file.rename(backup_file)
print(f"Created backup: {backup_file}")

target_file.write_text(content, encoding="utf-8")
print(f"Patched {target_file} successfully!")
print("\nPlease now:")
print("1. Create/update .env file with BIOCUBE_DIR pointing to your BioCube data")
print("2. Run your command again")
print("3. Check for [debug] messages about NDVI loading")
