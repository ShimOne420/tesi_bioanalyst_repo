# Report operativo tecnico - Pipeline osservativa BioMap

## 1. Scopo

Questo report spiega la pipeline osservativa del progetto BioMap nella copia piu aggiornata individuata:

- root tecnica: `TCBiomap/tesi_bioanalyst_repo_native`
- branch: `main`
- ultimo commit del worktree native: `4c25135`, `2026-06-22 17:07:44 +0200`, messaggio `flip griglia rollout multistep`
- stato Git native al momento dell'analisi: solo `docs/REPORT_ROLLOUT_MULTISTEP_PIPELINE_PREVISIONALE.md` risulta non tracciato

La pipeline osservativa e la parte che calcola indicatori reali, non predetti, a partire dai dataset BioCube locali. L'utente seleziona una citta, una bounding box disegnata sulla mappa o coordinate manuali; il sistema calcola valori mensili osservati e li mostra in dashboard.

## 2. Ruolo nel progetto

La pipeline osservativa risponde alla domanda:

> dato un territorio europeo e un periodo mensile, quali valori osservati sono disponibili per clima, vegetazione, suolo, copertura agricola/forestale e specie?

Non esegue BioAnalyst, non produce forecast e non mostra metriche di backtest. E il layer stabile della dashboard, separato dalla modalita previsionale.

## 3. Architettura ad alto livello

Il flusso e:

1. `web-ui/components/biomap-dashboard.tsx` raccoglie area e periodo.
2. La route Next.js `web-ui/app/api/indicators/route.ts` inoltra la richiesta al backend Python.
3. `backend_api/main.py` riceve `POST /api/indicators`.
4. Il backend costruisce un comando CLI e lancia `scripts/selected_area_indicators.py`.
5. Lo script legge BioCube, costruisce una tabella cella-mese e una tabella area-mese.
6. Lo script scrive CSV, CSV Excel-friendly, XLSX, JSON summary e Parquet celle.
7. Il backend rilegge gli output e restituisce un `IndicatorResponse` JSON.
8. La dashboard usa il JSON per tabella e grafico; usa `GET /api/cells/{label}` per la mappa cella-per-cella.

Il workflow sorgente e salvato in:

- `docs/architecture_study/workflow_osservativo.mmd`

## 4. Script usati nella pipeline osservativa

### Script principali

| File | Ruolo |
| --- | --- |
| `scripts/selected_area_indicators.py` | Script principale osservativo. Risolve area/periodo, legge BioCube, calcola output cella-mese e area-mese. |
| `scripts/minimum_indicator_utils.py` | Utility geospaziali e di export: bounding box, maschere, filtri temporali, medie pesate, output tabellari. |
| `scripts/generate_european_cities_catalog.py` | Genera o aggiorna `data/european_cities.json`, catalogo usato da backend e UI. |
| `scripts/view_minimum_sources.py` | Ispeziona campioni e metadati delle sorgenti minime. |
| `scripts/inventory_biocube.py` | Inventaria la struttura locale del BioCube. |
| `scripts/biocube_download.py` | Supporto al download BioCube. |
| `scripts/download_biocube_minimal.py` | Download minimo di sorgenti BioCube utili in setup/test. |
| `scripts/check_project_setup.py` | Controlla path e ambiente locale. |
| `scripts/activate_project.sh` | Attiva ambiente di progetto lato osservativo. |

### Script presenti ma non centrali per il flusso osservativo UI

| File | Uso |
| --- | --- |
| `scripts/audit_biocube_2021_sources.py` | Audit mirato su sorgenti BioCube 2021. |
| `scripts/resume_wekeo_rest.py` | Ripresa download/REST WEkEO. |
| `scripts/extend_agriculture_forest_to_2025.py` | Estensione dataset agriculture/forest fino al 2025. |

## 5. Sorgenti dati osservate

Il backend ricava i path da `.env` e `.env.local`, soprattutto da `BIOCUBE_DIR`.

| Variabile dashboard | Sorgente |
| --- | --- |
| `temperature_mean_area_c` / `temperature_mean_c` | `Copernicus/ERA5-monthly/era5-single/era5_single.nc`, variabile `t2m`, convertita Kelvin -> Celsius |
| `precipitation_mean_area_mm` / `precipitation_mean_mm` | `era5-climate-energy-moisture-0.nc`, preferenza `avg_tprate`, fallback `tp`, convertita in `mm/mese` |
| `swvl1`, `swvl2` | `Copernicus/ERA5-monthly/era5-edaphic/era5-edaphic-0.nc` |
| `stl1`, `stl2` | stesso file edaphic, convertito Kelvin -> Celsius |
| `ndvi_mean` | `Land/Europe_ndvi_monthly_un_025.csv`, con fallback vegetation se presente |
| `cropland_mean`, `arable_mean` | `Agriculture/Europe_combined_agriculture_data.csv` |
| `forest_mean` | `Forest/Europe_forest_data.csv` |
| `species_count_observed_cell` / `species_count_observed_area` | `Species/europe_species.parquet` |

Nota importante: `NaN` sulle specie non significa assenza ecologica reale; significa assenza di osservazioni nel dataset su quella cella/area e in quel mese.

## 6. Funzioni principali Python

### `scripts/selected_area_indicators.py`

| Funzione | Responsabilita |
| --- | --- |
| `build_parser` | Definisce CLI: citta, coordinate, bounding box, periodo, output mode. |
| `resolve_selection` | Trasforma citta/punto/bbox in bounds normalizzati. |
| `resolve_source_paths` | Costruisce i path delle sorgenti BioCube. |
| `compute_species_cell_month` | Rasterizza le osservazioni specie su griglia cella-mese. |
| `compute_species_area_monthly` | Aggrega il numero specie osservate a livello area-mese. |
| `load_climate_datasets` | Apre e ritaglia temperatura, precipitazione, edaphic e land mask. |
| `load_vegetation_dataset` | Carica eventuale fonte vegetation/NDVI alternativa. |
| `build_selected_cell_month_frame` | Crea la tabella completa per ogni cella e mese. |
| `compute_area_climate_monthly` | Aggrega le celle in una riga mensile area-level. |
| `main` | Orchestrazione end-to-end e scrittura output. |

### `scripts/minimum_indicator_utils.py`

| Funzione | Responsabilita |
| --- | --- |
| `normalize_longitude` | Normalizza longitudini. |
| `subset_europe` | Limita dataset al dominio europeo. |
| `build_land_mask` | Costruisce maschera terra. |
| `filter_dataframe_month_range` | Filtra tabelle per periodo mensile. |
| `filter_dataset_month_range` | Filtra dataset xarray per periodo mensile. |
| `build_bbox_from_point` | Crea bounding box da punto e semiampiezza. |
| `snap_coordinates_to_grid` | Allinea coordinate alla griglia. |
| `compute_weighted_land_mean_series` | Calcola medie pesate per latitudine. |
| `write_tabular_outputs` | Scrive summary, CSV, CSV Excel-friendly e XLSX. |

## 7. Backend osservativo

File:

- `backend_api/main.py`

Endpoint usati:

| Endpoint | Funzione Python | Ruolo |
| --- | --- | --- |
| `GET /api/health` | `health` | Verifica backend acceso. |
| `GET /api/cities` | `list_cities` | Restituisce catalogo citta. |
| `GET /api/metadata` | `metadata` | Restituisce range temporale reale e metadati forecast disponibili. |
| `POST /api/indicators` | `indicators` -> `run_indicator_job` | Esegue pipeline osservativa. |
| `GET /api/cells/{label}` | `cells` | Legge Parquet celle per mappa. |
| `GET /api/download/{label}/{file_format}` | `download_result` | Espone CSV, CSV Excel-friendly, XLSX. |

Funzioni backend chiave:

| Funzione | Cosa fa |
| --- | --- |
| `get_source_paths` | Mappa `BIOCUBE_DIR` alle sorgenti richieste. |
| `validate_source_paths` | Blocca la pipeline se mancano file obbligatori. |
| `get_dataset_metadata` | Calcola periodo reale disponibile dai layer climatici. |
| `build_indicator_command` | Converte richiesta JSON in comando CLI per `selected_area_indicators.py`. |
| `run_indicator_job` | Esegue subprocess, legge output e costruisce la risposta UI. |
| `read_monthly_csv` | Converte il CSV area-mese in lista di righe JSON. |
| `read_cells_parquet` | Converte il Parquet celle in JSON per la mappa. |

## 8. Frontend osservativo

File principali:

| File | Ruolo |
| --- | --- |
| `web-ui/app/page.tsx` | Renderizza `BiomapDashboard`. |
| `web-ui/components/biomap-dashboard.tsx` | Stato UI, toggle, form area/periodo, chiamate API, tabella, export. |
| `web-ui/components/europe-selection-map.tsx` | Selezione rettangolare su mappa Europa. |
| `web-ui/components/indicator-map.tsx` | Mappa tematica cella-per-cella con Leaflet. |
| `web-ui/components/trend-chart.tsx` | Grafico trend SVG per variabile selezionata. |
| `web-ui/lib/observed-variables.ts` | Definizione variabili disponibili e palette. |
| `web-ui/lib/types.ts` | Contratti TypeScript tra UI e API. |
| `web-ui/app/api/indicators/route.ts` | Proxy Next.js verso FastAPI `/api/indicators`. |
| `web-ui/app/api/cells/[label]/route.ts` | Proxy celle verso FastAPI `/api/cells/{label}`. |
| `web-ui/app/api/download/[label]/[format]/route.ts` | Proxy download file. |
| `web-ui/app/api/metadata/route.ts` | Proxy metadati dataset. |

La UI non contiene fallback demo: se FastAPI o BioCube non sono configurati, mostra l'errore reale.

## 9. Contratto dati della risposta

Tipo principale:

- `IndicatorResponse` in `web-ui/lib/types.ts`

Campi principali:

| Campo | Significato |
| --- | --- |
| `dashboardMode` | `observed` per la pipeline osservativa. |
| `sourceMode` | `local`, cioe calcolo reale locale. |
| `label` | Label normalizzata dell'area. |
| `selectionMode` | `city` o `bbox`. |
| `bounds` | Coordinate effettive usate. |
| `start`, `end` | Periodo calcolato. |
| `monthly` | Righe area-mese. |
| `cellsUrl` | Endpoint per recuperare celle del mese selezionato. |
| `downloads` | Link a CSV, CSV Excel-friendly, XLSX. |
| `notes` | Note semantiche, specie e schema osservativo. |

## 10. Output scritti

Per ogni label il backend forza `PROJECT_OUTPUT_DIR` su:

- `outputs/local_preview`

Output tipici:

| File | Uso |
| --- | --- |
| `selected_<label>_area_monthly_summary.json` | Summary operativo e sorgenti usate. |
| `selected_<label>_area_monthly.csv` | Tabella mensile area-level. |
| `selected_<label>_area_monthly_excel.csv` | CSV compatibile Excel italiano. |
| `selected_<label>_area_monthly.xlsx` | Workbook Excel. |
| `selected_<label>_cells.parquet` | Tabella cella-mese per mappa. |

## 11. Comandi operativi

Setup:

```bash
source scripts/activate_project.sh
python scripts/check_project_setup.py
python scripts/inventory_biocube.py
```

Backend:

```bash
uvicorn backend_api.main:app --reload --port 8000
```

Frontend:

```bash
cd web-ui
npm install
npm run dev
```

Script osservativo diretto:

```bash
python scripts/selected_area_indicators.py --city milano --start 2001-01-01 --end 2001-03-01 --output-mode both
```

Bounding box:

```bash
python scripts/selected_area_indicators.py --label nord_italia --min-lat 44 --max-lat 46 --min-lon 8 --max-lon 10 --start 2001-01-01 --end 2001-03-01
```

Controlli tecnici:

```bash
python -m py_compile scripts/selected_area_indicators.py backend_api/main.py
cd web-ui
npx tsc --noEmit
npm run build
```

## 12. Lettura della dashboard osservativa

La dashboard osservativa va interpretata cosi:

- la tabella mensile e area-level;
- la mappa e cella-level per un singolo mese;
- il grafico trend usa le stesse righe mensili della tabella;
- le esportazioni CSV/Excel lato UI esportano la tabella visibile;
- i download backend scaricano i file prodotti dallo script Python;
- `cells_with_species_records` indica quante celle hanno osservazioni specie;
- `valid_cell_count` indica quante celle hanno almeno una variabile valida tra quelle osservate.

## 13. Limiti e cautele

- La pipeline dipende da `BIOCUBE_DIR` e dai file locali reali.
- La disponibilita temporale viene limitata dai layer climatici core.
- NDVI puo usare fallback/proxy se la tabella ufficiale non copre il mese.
- Le specie sono osservazioni disponibili, non assenza/presenza ecologica certificata.
- Non vanno introdotte colonne `predicted`, `observed`, `MAE`, `RMSE` nella vista osservativa: quelle appartengono a validazioni forecast o backtest.

## 14. Punto chiave da ricordare

La pipeline osservativa e un ETL geospaziale locale: BioCube viene ritagliato su area e periodo, trasformato in una matrice cella-mese, aggregato in area-mese e servito alla UI. Backend e frontend non inventano dati: orchestrano, leggono e visualizzano gli output reali prodotti dagli script Python.
