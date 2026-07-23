# BioMAP — Ecosystem Assessment and Forecasting with BioAnalyst

BioMAP is a thesis research project for ecosystem assessment with geospatial foundation models. It combines observed biodiversity and climate indicators with a native-first integration of the BioAnalyst forecasting model, then exposes the results through a FastAPI service and a Next.js dashboard.

The repository is designed for reproducible local research. Source code, configuration examples, tests, and documentation are versioned; large datasets, model weights, generated forecasts, and machine-specific settings remain outside Git.

## Project status

The project currently supports two related workflows:

1. **Observed assessment** — computes area-level and cell-level indicators from BioCube data for a selected European city, bounding box, and monthly period.
2. **Forecast experimentation** — prepares native BioAnalyst batches, runs one-step or multi-step inference, validates predictions, and converts selected outputs into BioMAP-ready tables and forecast caches.

The observed pipeline is operational. The forecast pipeline is technically integrated, but its outputs remain research results and must not be interpreted as validated ecological predictions without the documented evaluation steps.

## Core capabilities

- Select a European city or draw a custom area.
- Query monthly observed indicators at area and grid-cell level.
- Process temperature, precipitation, species, NDVI, soil, land, agriculture, and forest variables when their sources are available.
- Build BioAnalyst-compatible batches with explicit real, proxy, and placeholder inputs.
- Run native one-step and autoregressive multi-step forecasts.
- Export maps, CSV files, Parquet files, JSON manifests, and Excel workbooks.
- Serve observed and forecast data through FastAPI.
- Explore the results in an interactive Next.js dashboard.

## Architecture

```text
BioCube and local model assets
          |
          v
Python processing and validation scripts
          |
          +---- observed indicators ----> CSV / Parquet / XLSX
          |
          +---- BioAnalyst inference ----> native tensors / manifests
                                          |
                                          v
                                  BioMAP conversion and cache
          |
          v
FastAPI backend <----> Next.js dashboard
```

The main directories are:

| Path | Purpose |
| --- | --- |
| `backend_api/` | FastAPI application and API endpoints. |
| `scripts/` | Data preparation, observed indicators, model inference, validation, export, and utility commands. |
| `web-ui/` | Next.js dashboard for area selection and result exploration. |
| `data/` | Small versioned catalogs and validation case definitions. Large BioCube data is ignored. |
| `models/` | Model documentation. Checkpoints are ignored. |
| `notebooks/` | Exploratory and reproducibility notebooks. |
| `docs/` | Operational guides, methodology notes, validation reports, and architecture studies. |
| `outputs/` | Generated local results. The directory is ignored by Git. |
| `external/` | Placeholder for external source repositories such as `bfm-model`; contents are ignored. |

## Requirements

- Python 3.11 or 3.12 is recommended.
- Node.js 18 or newer is required for the dashboard.
- Git is required to retrieve the external BioAnalyst implementation.
- A CUDA-capable environment is recommended for full model inference.

The base Python dependencies are listed in `requirements.txt`. Development checks are declared in `requirements-dev.txt`. BioAnalyst itself may require additional PyTorch and CUDA versions dictated by the external `bfm-model` repository and the target machine.

## Installation

Clone the repository and create an isolated Python environment:

```bash
git clone https://github.com/ShimOne420/tesi_bioanalyst_repo.git
cd tesi_bioanalyst_repo
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

Install the dashboard dependencies:

```bash
cd web-ui
npm ci
cd ..
```

## Configuration

Copy the environment templates:

```bash
cp .env.example .env
cp web-ui/.env.local.example web-ui/.env.local
```

Set the local paths in `.env`. The most important variables are:

| Variable | Description |
| --- | --- |
| `BIOCUBE_DIR` | Root directory of the local BioCube dataset. |
| `BIOANALYST_MODEL_DIR` | Local checkout or installation directory of the BioAnalyst model. |
| `PROJECT_OUTPUT_DIR` | Destination for generated outputs. |

Never commit `.env`, `.env.local`, datasets, checkpoints, or generated outputs. The repository already ignores these files.

See [the model guide](models/README.md), [the macOS setup guide](docs/SETUP_MAC_VSCODE.md), and [the Windows CUDA setup guide](docs/SETUP_WINDOWS_CUDA.md) for machine-specific details.

## Data

BioMAP expects BioCube sources to be stored locally under `BIOCUBE_DIR`. The exact available variables can differ between installations. Before running an analysis, inspect the configured sources:

```bash
python scripts/check_project_setup.py
python scripts/inventory_biocube.py
python scripts/view_minimum_sources.py --source all --rows 3
```

Large source files are intentionally excluded from this repository. Small catalogs under `data/` define supported European cities and validation cases.

## Observed indicator workflow

List the available cities:

```bash
python scripts/selected_area_indicators.py --list-cities
```

Run an observed analysis for a city:

```bash
python scripts/selected_area_indicators.py \
  --city madrid \
  --start 2019-01-01 \
  --end 2019-12-01
```

Run the same workflow for a custom bounding box:

```bash
python scripts/selected_area_indicators.py \
  --min-lat 40 \
  --max-lat 41 \
  --min-lon -4 \
  --max-lon -3 \
  --start 2019-01-01 \
  --end 2019-12-01
```

Outputs are written below `PROJECT_OUTPUT_DIR` and include machine-readable metadata describing the selected area, period, sources, units, and indicator semantics.

## Native BioAnalyst workflow

The forecast path follows the upstream model's native batch structure before converting results into BioMAP products. This separation makes model behavior easier to audit.

Activate the model environment:

```bash
source scripts/activate_bioanalyst_model.sh
```

Run native one-step inference:

```bash
python scripts/forecast_native_one_step.py \
  --city madrid \
  --start 2019-11-01 \
  --end 2019-12-01 \
  --checkpoint small \
  --device cpu
```

Run a six-step rollout:

```bash
python scripts/forecast_native_rollout.py \
  --city madrid \
  --start 2019-11-01 \
  --end 2019-12-01 \
  --checkpoint small \
  --device cuda \
  --steps 6
```

The higher-level runners combine inference, exports, plots, and optional cache publication:

```bash
python scripts/run.py --help
python scripts/run_rollout.py --help
```

Input modes are explicit:

- `clean` uses the core real-valued groups and leaves optional groups at zero.
- `all` also loads vegetation, agriculture, and forest sources when available.

Each run manifest records whether a group came from real data, a declared proxy, or a zero placeholder.

## Validation and exports

Inspect a native output:

```bash
python scripts/inspect_native_outputs.py \
  --run-dir outputs/local_preview/model_forecast/your_run \
  --group climate \
  --variable t2m
```

Create prediction and difference maps:

```bash
python scripts/plot_native_maps.py \
  --run-dir outputs/local_preview/model_forecast/your_run \
  --group climate \
  --variable t2m \
  --difference
```

Run a local validation matrix:

```bash
python scripts/validate_native_predictions.py \
  --cases-json data/native_validation_cases_local.json \
  --checkpoint small \
  --device cpu
```

Convert a native run into BioMAP outputs:

```bash
python scripts/native_to_biomap.py \
  --run-dir outputs/local_preview/model_forecast/your_run
```

For methodology and output interpretation, read:

- [Native BioAnalyst outputs](docs/OUTPUT_NATIVI_BIOANALYST.md)
- [Dataset-to-model mapping](docs/MATRICE_DATASET_BIOANALYST.md)
- [Observed frontend workflow](docs/README_FRONTEND_OSSERVATIVO.md)
- [Forecast frontend workflow](docs/README_OPERATIVO_FRONTEND_FORECAST.md)
- [Multi-step rollout report](docs/REPORT_ROLLOUT_MULTISTEP_PIPELINE_PREVISIONALE.md)

## API and dashboard

Start the backend from the repository root:

```bash
uvicorn backend_api.main:app --reload --port 8000
```

Start the frontend in another terminal:

```bash
cd web-ui
npm run dev
```

Open `http://localhost:3000`. The frontend forwards requests to the local backend and exposes observed or cached forecast results depending on the selected workflow.

## Quality checks

Run the Python checks:

```bash
ruff check backend_api scripts test_*.py
python -m compileall -q backend_api scripts
pytest
```

Run the frontend checks:

```bash
cd web-ui
npm run check
```

Some model-oriented tests import PyTorch and the external BioAnalyst code. Run them inside the configured model environment.

## Reproducibility rules

- Keep all machine-specific paths in environment files.
- Use `npm ci` to reproduce the locked frontend dependency tree.
- Record the checkpoint, input mode, bounds, dates, and source availability for every forecast.
- Treat generated manifests as part of the scientific audit trail.
- Do not substitute missing data silently; declare proxies and placeholders.
- Do not commit local caches, virtual environments, model weights, or outputs.

## Known limitations

- Forecast quality depends on the checkpoint, geographic domain, input coverage, and rollout horizon.
- A technically successful inference is not evidence of ecological validity.
- Optional BioCube variables may have different temporal coverage.
- Multi-step autoregressive forecasts accumulate uncertainty.
- Full-resolution model runs can require substantial GPU memory.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes. Keep commits focused, document new environment variables and outputs, and run the checks relevant to the modified pipeline.

## License and research use

No standalone license is currently declared in this repository. Before redistribution or production use, verify the licenses of BioCube, BioAnalyst, upstream datasets, and all external model assets.
