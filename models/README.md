# Models

Questa cartella documenta solo il lavoro modello del ramo `forecast-bioanalyst-native`.

## Direttiva Del Ramo

Qui non stiamo ancora costruendo indicatori BIOMAP.

La sequenza corretta e:

1. replicare BioAnalyst nel formato piu nativo possibile
2. ottenere output nativi del modello
3. solo dopo progettare un adapter separato verso BIOMAP

## Riferimenti BioAnalyst Da Rispettare

- configurazione mensile con `T: 2`
- `example_prediction.ipynb` per one-step prediction
- architettura `encoder -> backbone -> decoder`
- dataloader ufficiale `LargeClimateDataset`
- bootstrap modello via `setup_bfm_model`

## Script Attivi Del Modello

- [scripts/bioanalyst_native_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/bioanalyst_native_utils.py)
- [scripts/forecast_native_one_step.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_one_step.py)
- [scripts/forecast_native_rollout.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_rollout.py)
- [scripts/inspect_native_outputs.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/inspect_native_outputs.py)
- [scripts/plot_native_maps.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/plot_native_maps.py)
- [scripts/validate_native_predictions.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/validate_native_predictions.py)
- [scripts/native_to_biomap.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/native_to_biomap.py)

## Artefatti Attesi

Per ogni run vogliamo salvare:

- manifest JSON del run
- config locale usata
- batch predetti `.pt`
- target osservati raw quando disponibili

Questi sono gli artefatti su cui costruiremo in seguito il layer BIOMAP.

Per capire davvero gli output salvati, la guida da aprire e:

- [docs/OUTPUT_NATIVI_BIOANALYST.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/docs/OUTPUT_NATIVI_BIOANALYST.md)
- [docs/MATRICE_DATASET_BIOANALYST.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/docs/MATRICE_DATASET_BIOANALYST.md)

Per il benchmark nativo del modello, prima di qualunque adapter BIOMAP, si usa:

- [scripts/validate_native_predictions.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/validate_native_predictions.py)

Solo dopo, se serve un export area-level minimale, si usa:

- [scripts/native_to_biomap.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/native_to_biomap.py)
