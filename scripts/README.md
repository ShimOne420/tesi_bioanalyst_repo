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

### Native forecast

- [bioanalyst_model_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/bioanalyst_model_utils.py)
- [bioanalyst_native_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/bioanalyst_native_utils.py)
- [forecast_native_one_step.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_one_step.py)
- [forecast_native_rollout.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_rollout.py)

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
python scripts/forecast_native_one_step.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
python scripts/forecast_native_rollout.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --steps 6
```
