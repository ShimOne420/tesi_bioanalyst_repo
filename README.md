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
- `Land/Europe_ndvi_monthly_un_025.csv`
- `Agriculture/Europe_combined_agriculture_data.csv`
- `Forest/Europe_forest_data.csv`

La mappatura attuale distingue due modalita operative:

- `--input-mode clean`: usa solo i gruppi core reali e lascia `vegetation`, `agriculture`, `forest` a zero per fare un test pulito.
- `--input-mode all`: aggiunge `agriculture`, `forest` e `vegetation`; quest'ultima usa il CSV NDVI ufficiale se presente, altrimenti una proxy dichiarata da `lai_hv + lai_lv`.

`redlist` e `misc` restano placeholder a zero. Il manifest del run dichiara sempre quali gruppi sono reali, proxy o placeholder.

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
python -m py_compile scripts/bioanalyst_model_utils.py scripts/bioanalyst_native_utils.py scripts/forecast_native_one_step.py scripts/forecast_native_rollout.py scripts/inspect_native_outputs.py scripts/export_native_output.py scripts/plot_native_maps.py scripts/validate_native_predictions.py scripts/native_to_biomap.py scripts/validate_native_biomap.py
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

Excel dell'output `.pt` nativo:

```bash
python scripts/export_native_output.py --run-dir outputs/local_preview/model_forecast/madrid_2019_12_native_one_step --batch-kind prediction --group climate --variable t2m
```

Run + export completo dei valori nativi:

```bash
python scripts/run.py --label Europe_native_large_all_2019_06 --min-lat 32.0 --max-lat 72.0 --min-lon -25.0 --max-lon 45.0 --start 2019-04-01 --end 2019-05-01 --checkpoint large --device cuda --input-mode all --group climate --variable t2m --export-native-full --export-native-group-csvs --no-history
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
- [Workflow universita Windows CUDA](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/docs/WORKFLOW_UNIVERSITA_WINDOWS_CUDA.md)
- [Setup Windows con GPU NVIDIA](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/docs/SETUP_WINDOWS_CUDA.md)
