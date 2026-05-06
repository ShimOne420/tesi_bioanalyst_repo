#!/usr/bin/env python3
"""Test script to verify NDVI column matching fix."""
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import pandas as pd
from bioanalyst_model_utils import find_monthly_column, to_month_start
from datetime import datetime

# Read just the header of the NDVI CSV
csv_path = Path("../data/biocube/Land/Europe_ndvi_monthly_un_025.csv")
if not csv_path.exists():
    print(f"ERROR: NDVI CSV not found at {csv_path}")
    sys.exit(1)

columns = pd.read_csv(csv_path, nrows=0).columns.tolist()
print(f"CSV columns (first 10): {columns[:10]}")
print(f"Total columns: {len(columns)}")

# Test finding June 2019 column
month = pd.Timestamp("2019-06-01")
print(f"\nTesting find_monthly_column for {month:%Y-%m}...")
try:
    result = find_monthly_column(columns, "NDVI", month)
    print(f"SUCCESS: Found column '{result}'")
except SystemExit as e:
    print(f"FAILED: {e}")
    # Try to find it manually
    expected = "NDVI_06/2019"
    if expected in columns:
        print(f"MANUAL CHECK: Column '{expected}' exists in CSV!")
    else:
        print(f"MANUAL CHECK: Column '{expected}' NOT found in CSV")
        # Search for similar columns
        matches = [c for c in columns if "06" in c and "2019" in c]
        print(f"Similar columns: {matches[:5]}")
