# Tesi BioAnalyst

Questo ramo `forecast-bioanalyst-native` serve a replicare BioAnalyst nel modo piu fedele possibile a repository, documentazione e paper.

## Obiettivo Del Ramo

In questo ramo non stiamo ancora costruendo output BIOMAP.

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

- niente forecast area-level BIOMAP
- niente validazione clima BIOMAP
- niente adapter custom finale

prima chiudiamo il comportamento nativo del modello.

## Script Principali

- [scripts/bioanalyst_native_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/bioanalyst_native_utils.py)
- [scripts/forecast_native_one_step.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_one_step.py)
- [scripts/forecast_native_rollout.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/scripts/forecast_native_rollout.py)

## Comandi Base

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/check_project_setup.py
python -m py_compile scripts/bioanalyst_model_utils.py scripts/bioanalyst_native_utils.py scripts/forecast_native_one_step.py scripts/forecast_native_rollout.py
```

One-step nativo:

```bash
python scripts/forecast_native_one_step.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Rollout nativo:

```bash
python scripts/forecast_native_rollout.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --steps 6
```

## Output Attesi

Ogni run salva:

- `forecast_native_manifest.json`
- `forecast_native_config.yaml`
- batch nativi `.pt` del forecast
- target osservato raw, se disponibile

Questi artefatti sono il punto di partenza per il passo successivo, cioe l'adattamento BIOMAP, che pero in questo ramo non viene ancora implementato.
