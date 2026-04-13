# Tesi BioAnalyst

Questo ramo `forecast-bioanalyst-native` serve a replicare BioAnalyst nel modo piu fedele possibile a repository, documentazione e paper.

## Obiettivo Del Ramo

In questo ramo non stiamo ancora costruendo output BIOMAP come deliverable principale.

L'obiettivo attuale e solo questo:

- preparare batch compatibili con `bfm-model`
- eseguire il modello ufficiale con `T=2`
- ottenere output nativi one-step e rollout
- salvare batch predetti, target osservati e metadata del run

Observed pipeline, backend e UI restano disponibili nel repository, ma non sono il focus del lavoro su questo ramo.

## Allineamento Con BioAnalyst

I punti fermi presi da repository e documentazione ufficiale sono:

- forecast mensile con `2` timestep in input
- example notebook pensato per `one timestep ahead prediction`
- architettura `encoder -> backbone -> decoder`
- runner ufficiale costruito attorno a `LargeClimateDataset` e `setup_bfm_model`

Quindi, nel ramo native:

- niente forecast area-level BIOMAP come criterio di riuscita
- niente validazione finale del progetto nello spazio BIOMAP
- niente adapter custom come passaggio iniziale

prima chiudiamo il comportamento nativo del modello.

## Copertura Dati Reale Del Batch

Nel ramo native, oggi i gruppi che usano dati reali sono:

- `surface`
- `edaphic`
- `atmospheric`
- `climate`
- `species`
- `land`, ricostruito dal canale reale `lsm`

Nel BioCube locale e presente anche:

- `Copernicus/ERA5-monthly/era5-land-vegetation`

ma per ora non forziamo ancora una mappatura diretta verso:

- `NDVI`
- `Forest`
- `Agriculture`
- `Arable`
- `Cropland`
- `RLI`
- `misc`

perche i file disponibili (`lai_hv`, `lai_lv`, `cvh`, `cvl`, `tvh`, `tvl`) non coincidono ancora in modo documentato con i canali che BioAnalyst si aspetta. Per adesso questi gruppi restano placeholder a zero e il manifest del run lo dichiara esplicitamente.

## Script Principali

- [scripts/bioanalyst_native_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/bioanalyst_native_utils.py)
- [scripts/forecast_native_one_step.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_one_step.py)
- [scripts/forecast_native_rollout.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_rollout.py)
- [scripts/inspect_native_outputs.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/inspect_native_outputs.py)
- [scripts/plot_native_maps.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/plot_native_maps.py)
- [scripts/validate_native_predictions.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/validate_native_predictions.py)

Gli script BIOMAP restano disponibili, ma vengono dopo:

- [scripts/native_to_biomap.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/native_to_biomap.py)
- [scripts/validate_native_biomap.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/validate_native_biomap.py)

## Comandi Base

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/check_project_setup.py
python -m py_compile scripts/bioanalyst_model_utils.py scripts/bioanalyst_native_utils.py scripts/forecast_native_one_step.py scripts/forecast_native_rollout.py scripts/inspect_native_outputs.py scripts/plot_native_maps.py scripts/validate_native_predictions.py scripts/native_to_biomap.py scripts/validate_native_biomap.py
```

One-step nativo:

```bash
python scripts/forecast_native_one_step.py --city madrid --start 2019-11-01 --end 2019-12-01 --checkpoint small --device cpu
```

Rollout nativo:

```bash
python scripts/forecast_native_rollout.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --steps 6
```

Ispezione output:

```bash
python scripts/inspect_native_outputs.py --run-dir outputs/local_preview/model_forecast/madrid_2019_12_native_one_step --group climate --variable t2m
```

Mappa della temperatura:

```bash
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/madrid_2019_12_native_one_step --group climate --variable t2m
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/madrid_2019_12_native_one_step --group climate --variable t2m --difference
```

Benchmark nativo multi-caso:

```bash
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_local.json --checkpoint small --device cpu
```

Benchmark CUDA pronto per 15 citta x 4 stagioni:

```bash
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_cuda_15cities_template.json --checkpoint small --device cuda
```

Export BIOMAP minimo dal run nativo:

```bash
python scripts/native_to_biomap.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step
```

## Output Attesi

Ogni run salva:

- `forecast_native_manifest.json`
- `forecast_native_config.yaml`
- batch nativi `.pt` del forecast
- target osservato raw, se disponibile
- `native_inspection_summary.json` quando usi lo script di ispezione
- `.png` delle mappe quando usi lo script di plotting
- workbook di benchmark nativo in `native_prediction_validation_.../native_prediction_validation.xlsx`
- export BIOMAP minimale in `run_dir/biomap` solo se lanci gli script BIOMAP

Questi artefatti sono il punto di arrivo della replica native-first. Solo dopo entra lo strato BIOMAP.

## Workflow Minimo Da Ripetere Sul Mac

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/check_project_setup.py
python scripts/forecast_native_one_step.py --city madrid --start 2019-11-01 --end 2019-12-01 --checkpoint small --device cpu
python scripts/inspect_native_outputs.py --run-dir outputs/local_preview/model_forecast/madrid_2019_12_native_one_step --group climate --variable t2m
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/madrid_2019_12_native_one_step --group climate --variable t2m
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/madrid_2019_12_native_one_step --group climate --variable t2m --difference
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_local.json --checkpoint small --device cpu
```

## Guide Utili

- [Output nativi BioAnalyst](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/docs/OUTPUT_NATIVI_BIOANALYST.md)
- [Matrice dataset BioAnalyst](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/docs/MATRICE_DATASET_BIOANALYST.md)
- [Setup Windows con GPU NVIDIA](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/docs/SETUP_WINDOWS_CUDA.md)
