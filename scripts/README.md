# Scripts

Questo ramo contiene solo gli script che servono ancora alla direzione `BioAnalyst-native first`.

## Cosa Rimane

### Setup e ambiente

- [activate_project.sh](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/activate_project.sh)
- [activate_bioanalyst_model.sh](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/activate_bioanalyst_model.sh)
- [check_project_setup.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/check_project_setup.py)
- [download_bioanalyst_weights.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/download_bioanalyst_weights.py)

### Observed pipeline

- [minimum_indicator_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/minimum_indicator_utils.py)
- [selected_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/selected_area_indicators.py)
- [inventory_biocube.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/inventory_biocube.py)
- [view_minimum_sources.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/view_minimum_sources.py)
- [audit_future_dataset_coverage.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/audit_future_dataset_coverage.py)

### Native forecast

- [bioanalyst_model_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/bioanalyst_model_utils.py)
- [bioanalyst_native_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/bioanalyst_native_utils.py)
- [forecast_native_one_step.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_one_step.py)
- [forecast_native_rollout.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_rollout.py)
- [inspect_native_outputs.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/inspect_native_outputs.py)
- [export_native_output.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/export_native_output.py)
- [plot_native_maps.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/plot_native_maps.py)
- [validate_native_predictions.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/validate_native_predictions.py)
- [native_to_biomap.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/native_to_biomap.py)
- [validate_native_biomap.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/validate_native_biomap.py)
- [activate_bioanalyst_model.ps1](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/activate_bioanalyst_model.ps1)

Oggi i gruppi alimentati da dati reali nel batch nativo sono:

- `surface`
- `edaphic`
- `atmospheric`
- `climate`
- `species`
- `land` da `lsm`
- `vegetation` da `NDVI` CSV oppure proxy `LAI`
- `agriculture` da CSV europeo
- `forest` da CSV europeo

Restano ancora placeholder:

- `redlist`
- `misc`

### Estensione dati futuri

- [extend_era5_to_2026.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/extend_era5_to_2026.py)

## Cosa E Stato Rimosso Di Proposito

Dal ramo native abbiamo tolto:

- gli script forecast `adapter-first`
- gli script di validazione BIOMAP
- gli adapter verso output area-level finali

Il motivo e semplice:

- prima replichiamo BioAnalyst
- poi adattiamo gli output nativi a BIOMAP

## Comandi Da Usare Adesso

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/check_project_setup.py
python scripts/extend_era5_to_2026.py --years 2021 --dry-run
python scripts/extend_era5_to_2026.py --years 2021 2022 2023 2024 --target all_monthly
python scripts/audit_future_dataset_coverage.py --input-mode all --forecast-start 2020-07-01 --forecast-end 2021-12-01
python scripts/forecast_native_one_step.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
python scripts/forecast_native_rollout.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --steps 6
python scripts/inspect_native_outputs.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step
python scripts/export_native_output.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step --batch-kind prediction --group climate --variable t2m
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step --group climate --variable t2m
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_local.json --checkpoint small --device cpu
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_cuda_15cities_template.json --checkpoint small --device cuda
python scripts/native_to_biomap.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step
python scripts/validate_native_biomap.py --cases-json data/native_validation_cases_local.json --checkpoint small --device cpu
```
