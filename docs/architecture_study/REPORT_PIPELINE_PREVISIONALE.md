# Report operativo tecnico - Pipeline previsionale BioMap

## 1. Scopo

Questo report spiega la pipeline previsionale BioMap nella copia piu aggiornata individuata:

- root tecnica: `TCBiomap/tesi_bioanalyst_repo_native`
- branch: `main`
- ultimo commit del worktree native: `4c25135`, `2026-06-22 17:07:44 +0200`, messaggio `flip griglia rollout multistep`
- documento operativo piu recente: `docs/REPORT_ROLLOUT_MULTISTEP_PIPELINE_PREVISIONALE.md`, creato/modificato il `2026-06-22`

La pipeline previsionale usa BioAnalyst in modalita native-first. Il modello viene eseguito offline o su macchina universitaria, produce output nativi e workbook `cell_matrix`; la dashboard non riesegue il modello, ma legge una cache forecast gia pubblicata.

## 2. Ruolo nel progetto

La pipeline previsionale risponde alla domanda:

> data un'area europea, quali proiezioni mensili future sono gia state calcolate dal modello e possono essere visualizzate in dashboard?

La scelta architetturale centrale e:

- run pesante del modello: offline, via script Python;
- pubblicazione risultati: cache `previsioni/YYYY-MM/cell_matrix`;
- uso dashboard: sola lettura cache tramite backend.

Questo rende la UI reattiva e mantiene separati forecast, backtest e osservazioni reali.

## 3. Workflow sorgente

Il workflow visuale sorgente e:

- `docs/architecture_study/workflow_previsionale.mmd`

Il diagramma separa tre zone:

- produzione offline del forecast;
- storage/cache e artefatti;
- lettura online da backend e frontend.

## 4. Script usati nella pipeline previsionale

### Setup e ambiente

| File | Ruolo |
| --- | --- |
| `scripts/activate_bioanalyst_model.sh` | Attiva ambiente Python e variabili per BioAnalyst. |
| `scripts/activate_bioanalyst_model.ps1` | Variante Windows PowerShell. |
| `scripts/download_bioanalyst_weights.py` | Recupera o prepara i checkpoint locali. |
| `scripts/check_project_setup.py` | Controllo path e dipendenze. |
| `scripts/patch_bfm_attention_chunking.py` | Supporto per attention chunking quando la VRAM e un collo di bottiglia. |

### Core BioAnalyst native

| File | Ruolo |
| --- | --- |
| `scripts/bioanalyst_model_utils.py` | Costruisce batch `.pt`, risolve dati, checkpoint, config Hydra, griglia modello e gruppi variabili. |
| `scripts/bioanalyst_native_utils.py` | Orchestrazione nativa: contesto run, runtime modello, one-step, rollout, salvataggio manifest e `.pt`. |
| `scripts/biomap_metric_utils.py` | Helper per metriche, unita display e colonne cella-per-cella. |
| `scripts/spatial_alignment.py` | Metadata e correzioni di allineamento geografico della prediction. |

### Runner forecast

| File | Ruolo |
| --- | --- |
| `scripts/forecast_native_one_step.py` | Runner puro one-step: produce output nativi `.pt` e manifest. |
| `scripts/forecast_native_rollout.py` | Runner puro rollout: produce batch nativi multi-step. |
| `scripts/run.py` | Runner operativo one-step da tesi: esegue modello, esporta mappe, workbook, cache mensile e workbook finale. |
| `scripts/run_rollout.py` | Runner operativo rollout: esegue multi-step e pubblica direttamente la cache `previsioni/YYYY-MM/cell_matrix`. |
| `scripts/publish_forecast_cache_from_existing_run.py` | Pubblica nella cache un run gia esistente senza rieseguire il modello. |

### Ispezione, validazione e export

| File | Ruolo |
| --- | --- |
| `scripts/inspect_native_outputs.py` | Ispeziona manifest, batch, shape, timestamp, variabili e sanity check. |
| `scripts/export_native_output.py` | Esporta batch `.pt` nativo in workbook/CSV leggibili. |
| `scripts/plot_native_maps.py` | Produce mappe PNG di prediction, observed e differenze. |
| `scripts/validate_native_predictions.py` | Benchmark multi-caso nello spazio nativo BioAnalyst. |
| `scripts/native_to_biomap.py` | Adapter minimale da output nativo a indicatori area-level BIOMAP. |
| `scripts/validate_native_biomap.py` | Validazione dello strato BIOMAP derivato dai run nativi. |
| `scripts/analyze_latest_native_tests.py` | Analisi rapida degli ultimi test nativi. |
| `scripts/debug_native_cuda_shapes.py` | Debug shape/tensori su CUDA. |
| `scripts/biomap_curated_features.py` | Feature curate per export BIOMAP. |
| `scripts/biomap_final_workbook.py` | Aggiorna il workbook finale BIOMAP cumulativo. |

## 5. Gruppi dati del batch nativo

`bioanalyst_model_utils.py` definisce il dominio e i gruppi del modello:

- dominio: Europa, latitudine `32..72`, longitudine `-25..45`
- griglia: `160 x 280`
- input temporale: due mesi per il one-step nativo
- `lead_time`: impostato coerentemente con BioAnalyst

| Gruppo | Variabili principali | Stato |
| --- | --- | --- |
| `surface` | `t2m`, `msl`, `slt`, `z`, `u10`, `v10`, `lsm` | reale |
| `edaphic` | `swvl1`, `swvl2`, `stl1`, `stl2` | reale |
| `atmospheric` | `z`, `t`, `u`, `v`, `q` | reale se non `fast-smoke-test` |
| `climate` | `tp`, `avg_tprate`, `t2m`, `d2m`, energia/moisture | reale |
| `species` | 28 canali specie target | reale rasterizzato |
| `land` | `Land` | ricostruito da `lsm` |
| `vegetation` | `NDVI` | reale da CSV oppure proxy dichiarata |
| `agriculture` | `Agriculture`, `Arable`, `Cropland` | reale da CSV |
| `forest` | `Forest` | reale da CSV |
| `redlist` | `RLI` | placeholder |
| `misc` | `avg_slhtf`, `avg_pevr` | placeholder |

La CLI supporta:

- `--input-mode all`: usa anche vegetation, agriculture, forest quando disponibili;
- `--input-mode clean`: usa solo gruppi core e mette a zero i gruppi extra.

Questa distinzione serve a capire se gli input extra aiutano o destabilizzano il forecast.

## 6. Pipeline offline one-step

Il one-step e il caso base:

- input: due mesi osservati;
- output: mese successivo.

Esempio concettuale:

- input: `2026-02`, `2026-03`;
- forecast: `2026-04`.

### Sequenza nel codice

1. `scripts/run.py` o `scripts/forecast_native_one_step.py` legge argomenti CLI.
2. `prepare_native_forecast_environment` carica `.env`, BioCube, modello e path progetto.
3. `build_native_run_context` risolve area, periodo, checkpoint, device e cartella run.
4. `prepare_native_saved_windows` chiama `save_window_batches`.
5. `save_window_batches` usa `build_raw_batch_for_months` per creare `window_00000.pt`.
6. `build_raw_batch_for_months` legge surface, edaphic, atmospheric, climate, species, vegetation, agriculture, forest.
7. `build_native_runtime` carica `LargeClimateDataset`, `setup_bfm_model`, checkpoint safetensors e scaling.
8. `run_native_one_step` esegue il modello e ricostruisce il batch predetto.
9. `save_native_one_step_artifacts` salva manifest e `.pt`.
10. `run.py` esporta mappe, workbook e cache mensile.

### Artefatti one-step

| Artefatto | Significato |
| --- | --- |
| `forecast_native_manifest.json` | Manifest del run, area, input, checkpoint, path output. |
| `forecast_native_config.yaml` | Config Hydra effettiva. |
| `native_prediction_original.pt` | Batch predetto riscalato in spazio originale. |
| `native_target_original.pt` | Target osservato raw, se disponibile. |
| `plots/` | Mappe PNG. |
| `exports/` | Workbook e CSV di analisi. |
| `previsioni/YYYY-MM/cell_matrix` | Workbook leggibili dal backend forecast. |

## 7. Pipeline offline rollout multi-step

Il rollout multi-step estende il one-step in modo autoregressivo.

Sequenza concettuale:

- febbraio + marzo -> aprile predetto;
- marzo + aprile predetto -> maggio predetto;
- aprile predetto + maggio predetto -> giugno predetto;
- continua fino a `steps`.

La funzione centrale e:

- `run_native_rollout` in `scripts/bioanalyst_native_utils.py`

La funzione:

1. carica il batch iniziale scalato;
2. esegue il modello per ogni `rollout_step`;
3. costruisce il nuovo batch con `build_new_batch_with_prediction`;
4. usa la prediction precedente come input del passo successivo;
5. riscalda ogni batch nello spazio originale;
6. restituisce `rollout_batches_original` e `forecast_months`.

### Runner operativo rollout

`scripts/run_rollout.py` e il runner piu vicino alla dashboard. Dopo il rollout:

1. legge il manifest;
2. risolve `FORECAST_CACHE_DIR` o usa `PROJECT_OUTPUT_DIR/previsioni`;
3. per ogni mese previsto crea `previsioni/YYYY-MM/cell_matrix`;
4. chiama `export_reliable_feature_workbooks`;
5. scrive `_forecast_cache_manifest.json`;
6. stampa un summary con mesi pubblicati.

Questo e il percorso da usare quando il forecast deve alimentare la dashboard.

## 8. Cache forecast

La cache e la struttura ponte tra modello e UI:

```text
previsioni/
  2026-04/
    cell_matrix/
      t2m_cell_matrix.xlsx
      NDVI_cell_matrix.xlsx
      swvl1_cell_matrix.xlsx
      ...
    _forecast_cache_manifest.json
  2026-05/
    cell_matrix/
      ...
```

Il backend non legge direttamente `.pt`. Legge i workbook `cell_matrix.xlsx`, in particolare il foglio:

- `full_grid`

Ogni workbook deve contenere coordinate e una colonna `predicted_*`.

Variabili lette dalla dashboard forecast:

- `temperature` -> workbook prefix `t2m`
- `ndvi` -> `NDVI`
- `swvl1` -> `swvl1`
- `swvl2` -> `swvl2`
- `stl1` -> `stl1`
- `stl2` -> `stl2`
- `cropland` -> `Cropland`
- `arable` -> `Arable`
- `forest` -> `Forest`

## 9. Backend forecast

File:

- `backend_api/main.py`

Endpoint forecast:

| Endpoint | Funzione | Ruolo |
| --- | --- | --- |
| `POST /api/forecast` | `forecast` -> `run_forecast_cache_job` | Legge cache forecast e restituisce risposta dashboard. |
| `GET /api/forecast/cells/{label}` | `forecast_cells` | Legge Parquet celle forecast per mappa. |
| `GET /api/metadata` | `metadata` | Include mesi target e mesi disponibili forecast. |

Funzioni chiave:

| Funzione | Cosa fa |
| --- | --- |
| `get_forecast_cache_dir` | Legge `FORECAST_CACHE_DIR`. |
| `get_forecast_target_months` | Legge `FORECAST_TARGET_MONTHS` oppure usa default `2026-04..2026-09`. |
| `build_forecast_metadata` | Dichiara mesi disponibili alla UI. |
| `resolve_selection_bounds` | Converte citta/bbox in bounds. |
| `list_forecast_months_until_target` | Se target e giugno, restituisce aprile, maggio, giugno. |
| `forecast_cell_matrix_path` | Trova workbook `cell_matrix` per mese e variabile. |
| `load_forecast_variable_layer` | Legge `full_grid`, trova lat/lon e colonna `predicted_*`, normalizza unita. |
| `build_forecast_month_cell_frame` | Unisce le variabili forecast cella-per-cella e ritaglia sul bounding box. |
| `compute_forecast_monthly` | Aggrega con peso latitudinale in righe area-mese. |
| `run_forecast_cache_job` | Orchestrazione completa della risposta forecast. |

Il backend scrive anche:

- `outputs/local_preview/forecast_<label>_cells.parquet`

Questo file serve per la mappa forecast.

## 10. Frontend forecast

File principali:

| File | Ruolo |
| --- | --- |
| `web-ui/components/biomap-dashboard.tsx` | Toggle `Osservazione / Previsione`, selezione mese target, chiamata forecast. |
| `web-ui/app/api/forecast/route.ts` | Proxy Next.js verso FastAPI `/api/forecast`. |
| `web-ui/app/api/forecast/cells/[label]/route.ts` | Proxy Next.js verso FastAPI `/api/forecast/cells/{label}`. |
| `web-ui/components/indicator-map.tsx` | Riusa la stessa mappa tematica per celle forecast. |
| `web-ui/components/trend-chart.tsx` | Riusa il grafico trend sui mesi forecast. |
| `web-ui/lib/types.ts` | `DashboardMode`, `IndicatorResponse`, `CellRow`. |
| `web-ui/lib/observed-variables.ts` | Variabili visualizzabili anche in modalita forecast. |

In modalita forecast l'utente:

1. mantiene area da citta, mappa o coordinate;
2. sceglie un solo mese target;
3. la UI chiama `/api/forecast`;
4. se il target e il primo mese configurato, la risposta e one-step;
5. se il target e successivo, la risposta include la sequenza rollout fino al target.

## 11. Contratto dati forecast

La risposta riusa `IndicatorResponse`, ma con:

| Campo | Valore forecast |
| --- | --- |
| `dashboardMode` | `forecast` |
| `sourceMode` | `forecast_cache` |
| `targetMonth` | Mese finale richiesto |
| `forecastMonths` | Sequenza di mesi inclusi |
| `monthly` | Righe aggregate area-mese predette |
| `cellsUrl` | `/api/forecast/cells/{label}` |
| `downloads` | non usato come download backend osservativo |
| `notes` | specifica che la cache e precomputata |

Le colonne mensili sono volutamente compatibili con quelle osservate:

- `temperature_mean_area_c`
- `ndvi_mean_area`
- `swvl1_mean_area`
- `swvl2_mean_area`
- `stl1_mean_area`
- `stl2_mean_area`
- `cropland_mean_area`
- `arable_mean_area`
- `forest_mean_area`
- `cell_count_land`

Le specie in forecast dashboard sono lasciate a `None`/vuote nel backend cache attuale.

## 12. Perche la UI forecast non mostra metriche di errore

La dashboard forecast e una vista di proiezione futura. Per un mese futuro reale non esiste ancora l'osservato, quindi non avrebbe senso mostrare:

- `Observed`
- `MAE`
- `RMSE`
- `Bias`
- `WAPE`
- `SMAPE`
- `SMAAPE`

Queste metriche restano importanti nei benchmark e nei workbook tecnici, ma non nella vista forecast finale. Questa separazione va spiegata chiaramente in tesi.

## 13. Comandi operativi principali

### One-step operativo con export dashboard

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/run.py --label Europe_native_large_all_2019_06 --min-lat 32.0 --max-lat 72.0 --min-lon -25.0 --max-lon 45.0 --start 2019-04-01 --end 2019-05-01 --checkpoint large --device cuda --input-mode all --group climate --variable t2m --export-native-full --export-native-group-csvs --no-history
```

### Rollout con pubblicazione cache

```bash
python scripts/run_rollout.py --city madrid --start 2026-02-01 --end 2026-03-01 --checkpoint small --device cuda --input-mode all --steps 6
```

### Ripubblicare un run esistente

```bash
python scripts/publish_forecast_cache_from_existing_run.py --run-dir outputs/local_preview/model_forecast/NOME_RUN --month 2026-04
```

### Ispezione output nativi

```bash
python scripts/inspect_native_outputs.py --run-dir outputs/local_preview/model_forecast/NOME_RUN --group climate --variable t2m
```

### Validazione multi-caso

```bash
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_local.json --checkpoint small --device cpu
```

## 14. Configurazione backend/UI

Root `.env.local`:

```env
BIOCUBE_DIR=F:/biomap_store/biocube
PROJECT_OUTPUT_DIR=F:/biomap_store/outputs/local_preview
BIOANALYST_MODEL_DIR=models
FORECAST_CACHE_DIR=F:/output/previsioni 3.0/previsioni
FORECAST_TARGET_MONTHS=2026-04,2026-05,2026-06,2026-07,2026-08,2026-09
```

Frontend `web-ui/.env.local`:

```env
PYTHON_API_BASE_URL=http://127.0.0.1:8000
```

## 15. Validazione consigliata

### Strutturale

- `forecast_native_manifest.json` esiste.
- I mesi forecast sono corretti.
- Ogni mese ha `cell_matrix`.
- Ogni workbook ha foglio `full_grid`.
- Ogni workbook ha lat/lon e colonna `predicted_*`.

### Geografica

- Il bounding box selezionato interseca celle valide.
- `spatial_alignment` e presente o ricostruibile.
- I valori letti dalla UI provengono dall'area corretta.

### Numerica

- I valori non sono tutti nulli.
- I valori non sono costanti.
- Le unita sono corrette: temperatura in Celsius, non Kelvin.
- NDVI non va interpretato senza controllo di plausibilita.
- Il rollout non deve degenerare rapidamente dopo i primi step.

## 16. Limiti attuali

- Il rollout accumula errore autoregressivo.
- `t2m` e la variabile piu solida, soprattutto nei mesi caldi.
- NDVI e utile ma piu fragile in rollout.
- `tp` resta instabile come indicatore principale.
- Forest, Arable e Cropland sono utili per contesto territoriale, ma non vanno venduti come forecast dinamico affidabile allo stesso livello di `t2m`.
- La cache deve essere aggiornata dopo ogni correzione di allineamento o export.
- Un rollout a 12 mesi va trattato come esplorativo, non default operativo.

## 17. Punto chiave da ricordare

La pipeline previsionale e composta da due sistemi collegati ma distinti:

1. sistema offline pesante: costruisce batch BioAnalyst, esegue il modello e pubblica cache;
2. sistema online leggero: backend e frontend leggono cache, ritagliano l'area selezionata e visualizzano tabella, mappa e trend.

Questa separazione e la ragione per cui la dashboard puo mostrare forecast senza dipendere da una GPU o da un run live a ogni click.
