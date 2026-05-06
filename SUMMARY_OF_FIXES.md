# Summary of Fixes Applied

## Issue 1: Export Buttons Not Visible in Frontend

**Status**: Code already has export buttons in `web-ui/components/biomap-dashboard.tsx` at lines 556-577.

**Changes made**:
- Created `.env` file with correct BIOCUBE_DIR path
- Added debug logging to backend NDVI functions

**To apply**: 
1. Rebuild frontend: `cd web-ui && rm -rf .next && npm run build`
2. Start frontend: `npm run start`
3. The buttons should appear ABOVE the table (before line 579)

## Issue 2: NDVI Observed Values = 0 for June 2019

**Root Cause**: The NDVI CSV (`Europe_ndvi_monthly_un_025.csv`) is not being loaded properly, so it falls back to LAI proxy which returns zeros.

**Fixes Applied** (in `tesi_bioanalyst_repo_native/scripts/bioanalyst_model_utils.py`):

1. **Fixed `find_monthly_column` function** to match the CSV format `NDVI_06/2019`:
   - Added candidates: `NDVI_06/2019` and `NDVI_6/2019` formats

2. **Added debug logging to `yearly_column_to_grid`**:
   - Prints matched/total coordinate count
   - Warns if no coordinates match
   - Prints example keys for debugging

3. **Added debug logging to `build_vegetation_group_from_sources`**:
   - Prints which path is taken (CSV or LAI fallback)
   - Checks if NDVI CSV file exists
   - Prints file size

4. **Added debug logging to `build_vegetation_group_from_ndvi_csv`**:
   - Prints when NDVI CSV is being read
   - Prints number of rows and column names
   - Prints which date/year/month columns are found

**Files Modified**:
- `/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/bioanalyst_model_utils.py`
- `/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/.env` (created)

**Next Steps for User (on Windows machine)**:

1. Copy the same changes to `C:\Users\brome_3yy4afy\Desktop\biomap_thesis\tesi_bioanalyst_repo\scripts\bioanalyst_model_utils.py`
2. Create `.env` file in `C:\Users\brome_3yy4afy\Desktop\biomap_thesis\tesi_bioanalyst_repo\` with:
   ```
   BIOCUBE_DIR=C:\biomap_thesis\data\biocube
   BIOANALYST_MODEL_DIR=C:\Users\brome_3yy4afy\Desktop\biomap_thesis\tesi_bioanalyst_repo\models
   PROJECT_OUTPUT_DIR=C:\Users\brome_3yy4afy\Desktop\biomap_thesis\tesi_bioanalyst_repo\outputs
   ```
3. Run the command again with `--input-mode all` and check the debug output
4. Verify NDVI CSV exists at `C:\biomap_thesis\data\biocube\Land\Europe_ndvi_monthly_un_025.csv`

**Expected Debug Output** (after fix):
```
[debug] Provo a caricare NDVI da CSV: C:\biomap_thesis\data\biocube\Land\Europe_ndvi_monthly_un_025.csv
[debug] NDVI CSV esiste: <file_size> bytes
[debug] Leggo NDVI CSV: <path>
[debug] NDVI CSV caricato: 14249 righe, colonne: ['Country', 'Latitude', 'Longitude', ...]
[debug] Date column: None, Year: None, Month: None, NDVI: None
[debug] yearly_column_to_grid: <matched>/<total> coordinate match (saltate <skipped>) per NDVI_06/2019
```

If `matched = 0`, then the coordinate matching is failing.
If the CSV path is not found, check the `.env` file.
