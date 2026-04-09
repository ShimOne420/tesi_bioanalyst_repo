# Tesi BioAnalyst

Questo repository contiene il workspace operativo della tesi.

## Stato Corrente

Stato aggiornato al `2026-04-03`.

Al momento il progetto e diviso in due blocchi:

- `pipeline indicatori osservati`, gia funzionante in locale;
- `modulo forecast BioAnalyst`, integrato tecnicamente ma non ancora validato scientificamente.

La situazione reale oggi e questa:

- `BioCube` e scaricato su `Archivio`;
- il checkpoint ufficiale `small` di `BioAnalyst` e scaricato su `Archivio`;
- il repository ufficiale `bfm-model` e collegato localmente;
- esiste un ambiente dedicato `.venv-bioanalyst`;
- esistono gli script di forecast, adapter BIOMAP e rollout multi-step;
- il test one-step completo con `era5_pressure.nc` e stato chiuso con successo;
- il rollout completo a `+2 mesi` e `+6 mesi` e stato chiuso con successo;
- i valori forecast ottenuti non sono ancora scientificamente interpretabili e vanno trattati come output tecnici da validare.
- la pipeline osservativa e stata verificata su casi reali e oggi restituisce valori plausibili;
- le osservazioni specie vengono allineate alla griglia ERA5 `0.25°` sia negli indicatori osservati sia nella rasterizzazione forecast.
- il backtest forecast esteso su `Milano`, `Madrid`, `Vienna` e `Lisbona` conferma che il checkpoint `small` non e ancora abbastanza accurato per l'uso finale in UI.

La fase attuale del progetto ha un blocco tecnico principale:

- selezione di `citta` o `area` europea
- filtro per `periodo`
- calcolo dei tre indicatori minimi
- output sia aggregato per area sia nel formato `cella + mese`

Lo stack locale consigliato ora e:

- `frontend locale`: Next.js su `localhost:3000`
- `backend locale`: FastAPI su `localhost:8000`
- `dataset`: BioCube su `Archivio`

Il range reale oggi esposto in UI e backend per i tre indicatori minimi e:

- `2000-01 -> 2020-12`

Per la parte modello, invece, vedi il README dedicato:

- [models/README.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/models/README.md)

Per una guida pratica completa, con spiegazione di file, cartelle e comandi da usare in `Visual Studio Code`, vedi:

- [docs/README_OPERATIVO.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/README_OPERATIVO.md)
- [docs/STRATEGIA_BRANCH_FORECAST.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/STRATEGIA_BRANCH_FORECAST.md)
- [docs/PHASE_5_FINDINGS.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/PHASE_5_FINDINGS.md)
- [docs/VALIDAZIONE_FORECAST_CLIMA.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/VALIDAZIONE_FORECAST_CLIMA.md)
- [docs/VALIDAZIONE_GPU_GRATUITA.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/VALIDAZIONE_GPU_GRATUITA.md)
- [docs/PERCHE_FORECAST_NON_VALIDATO.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/PERCHE_FORECAST_NON_VALIDATO.md)

## Obiettivo

Usare `BioCube` in locale per calcolare tre indicatori minimi:

- `numero di specie osservate`
- `temperatura media`
- `precipitazioni medie`

L'architettura attuale e gia pensata per uno step successivo di servizio o interfaccia web, dove un utente non tecnico potra selezionare una localita e un periodo.

## Stato Del Modello

Il sottosistema `BioAnalyst` oggi va letto cosi:

- `fase 1` setup pesi e codice: chiusa;
- `fase 2` primo test di inferenza: chiusa anche in modalita completa con blocco atmosferico reale;
- `fase 3` adapter BIOMAP: chiusa a livello tecnico;
- `fase 4` rollout forecast: avviata e chiusa a livello tecnico su `+2 mesi` e `+6 mesi`;
- `fase 5` diagnostica e backtesting iniziale: chiusa;
- `fase 5` validazione scientifica estesa: ancora aperta.

In pratica:

- i file e gli script ci sono;
- la documentazione c'e;
- il modello ha gia completato run completi one-step e rollout;
- il prossimo passo sicuro e ampliare il backtesting, non piu chiudere il setup.

## Flusso di lavoro attuale

1. attivare il progetto
2. verificare il setup
3. ispezionare i dati minimi
4. avviare il backend locale FastAPI
5. avviare il frontend locale Next.js
6. selezionare una citta o un'area dalla UI

## Comandi principali

```bash
source scripts/activate_project.sh
python scripts/check_project_setup.py
python scripts/inventory_biocube.py
python scripts/view_minimum_sources.py --source all --rows 3
python scripts/selected_area_indicators.py --list-cities
python scripts/selected_area_indicators.py --city milano --start 2000-01-01 --end 2000-12-01
python scripts/selected_area_indicators.py --city madrid --start 2000-06-01 --end 2000-06-01
python scripts/selected_area_indicators.py --city milano --start 2018-01-01 --end 2019-12-01
python scripts/selected_area_indicators.py --min-lat 44 --max-lat 46 --min-lon 8 --max-lon 10 --start 2000-01-01 --end 2000-12-01
uvicorn backend_api.main:app --reload --port 8000
```

Per la UI locale:

```bash
cd web-ui
npm install
npm run dev
```

## Comandi Del Modello

Quando vorrai riprendere il lavoro sul forecast, usa questi comandi e parti da qui:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/download_bioanalyst_weights.py --list
python -m py_compile scripts/bioanalyst_model_utils.py scripts/download_bioanalyst_weights.py scripts/forecast_area_indicators.py scripts/forecast_rollout_area_indicators.py
```

Il comando one-step completo e gia validato tecnicamente:

```bash
python scripts/forecast_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Il comando di backtest minimo oggi consigliato e:

```bash
python scripts/forecast_backtest_one_step.py --cities milano madrid --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Per una validazione piu eterogenea:

```bash
python scripts/forecast_backtest_one_step.py --cities milano madrid vienna lisbon --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Il comando dedicato alla validazione clima su molte citta o aree e questo:

```bash
python scripts/forecast_validate_climate.py --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cuda
python scripts/forecast_validate_climate.py --areas-json data/validation_non_urban_areas.json --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cuda
```

Per leggere rapidamente il report finale:

```bash
python scripts/inspect_forecast_validation_report.py
```

Per una versione guidata direttamente su Colab:

- [02_colab_gpu_validation.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/02_colab_gpu_validation.ipynb)

Il comando smoke test storico resta questo:

```bash
python scripts/forecast_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --fast-smoke-test
```

Il comando rollout multi-step gia validato tecnicamente e questo:

```bash
python scripts/forecast_rollout_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --steps 6
```

Output principali gia generati:

- [forecast_summary.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12/forecast_summary.json)
- [forecast_area_indicators.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12/forecast_area_indicators.xlsx)
- [forecast_rollout_summary.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12_rollout_6m/forecast_rollout_summary.json)
- [forecast_rollout_6m.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12_rollout_6m/forecast_rollout_6m.xlsx)
- [forecast_backtest_one_step.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/phase5_backtest_milano_madrid/forecast_backtest_one_step.xlsx)

## Note importanti

- i dataset pesanti e i modelli stanno fuori dal repo, su `Archivio`
- il repo GitHub contiene solo codice, notebook, documentazione e output piccoli
- il file `.env` definisce i path locali
- per `Excel`, usa preferibilmente i file `.xlsx` o i file `_excel.csv`
- se la UI mostra solo il `2000`, quasi sempre hai una sessione vecchia di frontend o backend: chiudi i processi con `Ctrl + C` e riavviali
- per il modello, la parte tecnica minima e chiusa, ma la validazione scientifica non lo e
- nella fase 5 sono stati trovati e corretti due bug locali: inversione dello scaling e media areale con denominatore errato
- nella fase 5 e stato corretto anche l'allineamento spaziale delle specie sulla griglia ERA5 `0.25°`
- dopo questi fix, il confronto `forecast vs observed` e molto piu leggibile
- il modello continua comunque a sovrastimare soprattutto la parte specie e va ancora validato prima di finire in UI come funzione utente
- oggi la decisione pratica e: `indicatori osservati pronti`, `forecast ancora in validazione`
- il modello `large` non e ancora il prossimo passo operativo: la pipeline locale e oggi parametrizzata esplicitamente per il checkpoint `small`
