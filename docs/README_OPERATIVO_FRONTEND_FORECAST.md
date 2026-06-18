# README Operativo: Validazione Osservativa e Forecast BioMap

## Obiettivo

Questo documento definisce il flusso operativo per:

- validare e proteggere la dashboard osservativa gia pronta su `main`;
- creare un branch separato per la parte forecast;
- implementare il forecast one-step come previsione futura, senza confronto con osservati nella UI;
- sperimentare il rollout multi-step a 6 mesi e poi a 12 mesi.

La regola principale e semplice: la vista osservativa validata resta stabile, mentre il forecast entra in un branch dedicato e con contratto dati separato.

## 1. Validare La Parte Osservativa Su `main`

Prima di qualsiasi lavoro forecast, validare `main` sulla macchina universitaria Broan con dati reali BioCube.

### Controllo branch e setup

Dalla root del repository:

```powershell
git switch main
git pull
git status

Test-Path F:\biomap_store\biocube
python -m py_compile scripts/selected_area_indicators.py backend_api/main.py
```

Il risultato atteso e:

- branch corrente: `main`;
- worktree pulita o con sole modifiche note;
- `Test-Path F:\biomap_store\biocube` restituisce `True`;
- compilazione Python senza errori.

### Configurazione backend

Creare o aggiornare `.env.local` nella root del repository:

```env
BIOCUBE_DIR=F:/biomap_store/biocube
PROJECT_OUTPUT_DIR=F:/biomap_store/outputs/local_preview
BIOANALYST_MODEL_DIR=models
```

Se il BioCube e in un path diverso, modificare solo `BIOCUBE_DIR` mantenendo il formato con slash `/`.

### Configurazione frontend

Creare o aggiornare `web-ui/.env.local`:

```env
PYTHON_API_BASE_URL=http://127.0.0.1:8000
```

Ogni modifica a `web-ui/.env.local` richiede il riavvio di `npm run dev`.

### Avvio backend

Terminale 1, dalla root del repository:

```powershell
uvicorn backend_api.main:app --reload --port 8000
curl.exe http://127.0.0.1:8000/api/metadata
```

Se `/api/metadata` fallisce, non testare ancora il frontend: prima sistemare path BioCube, ambiente Python o configurazione `.env.local`.

### Avvio frontend

Terminale 2:

```powershell
cd web-ui
npm install
npx tsc --noEmit
npm run build
npm run dev
```

Aprire:

```text
http://localhost:3000
```

### Test manuali obbligatori

Eseguire almeno questi scenari:

- selezione tramite citta europea;
- selezione tramite rettangolo disegnato sulla mappa;
- selezione tramite coordinate manuali;
- periodo breve `2001-01 -> 2001-03`;
- periodo critico `2020-06 -> 2020-08`;
- tabella osservativa con una riga per mese e variabili in colonne;
- export `CSV`;
- export `Excel`;
- download backend, se disponibili: `Scarica CSV`, `Scarica CSV per Excel`, `Scarica XLSX`;
- mappa tematica per temperatura, precipitazione, NDVI, SWVL1, SWVL2 e Cropland;
- tooltip delle celle sulla mappa;
- grafico trend della variabile selezionata.

### Criterio di accettazione osservativo

La parte osservativa e validata solo se:

- non compaiono dati demo o mock;
- la UI usa il backend FastAPI reale;
- non compaiono colonne o metriche forecast nella vista osservativa;
- i mesi mancanti non causano crash e vengono mostrati come `n.d.`;
- export CSV ed Excel contengono la stessa tabella visibile;
- mappa, grafico e tabella sono coerenti con lo stesso calcolo.

## 2. Congelare La Versione Osservativa

Dopo validazione positiva su Broan, creare un branch/tag di protezione.

```powershell
git switch main
git pull
git branch observed-ui-validated-2026-06-18
```

Se si vuole salvare il punto anche su remoto:

```powershell
git push origin observed-ui-validated-2026-06-18
```

Da questo momento, `main` e la versione osservativa validata non vanno usati per esperimenti forecast.

## 3. Creare Il Branch Forecast

Creare il branch di sviluppo forecast partendo da `main` validato:

```powershell
git switch main
git pull
git switch -c feature/forecast-ui-native
```

Regole del branch:

- la modalita osservativa non va rifatta;
- il forecast deve avere route API, tipi e componenti separati;
- la UI forecast non deve mostrare metriche di errore;
- eventuali backtest predetto/osservato restano analisi tecniche fuori dalla vista utente principale.

## 4. Implementare Forecast One-Step

### Scelta UX

Aggiungere un toggle alto:

```text
Osservativo | Previsionale
```

La modalita `Osservativo` resta identica.

La modalita `Previsionale` riusa l'area selezionata, ma ha un contratto separato:

- area da citta, mappa o coordinate;
- due mesi osservati come input del modello;
- un mese futuro come output;
- valori previsti;
- metadati del run;
- nessun confronto con osservati nella UI.

### Endpoint backend da aggiungere

Contratto minimo consigliato:

```text
POST /api/forecast
GET /api/forecast/{label}
GET /api/forecast/{label}/cells?month=YYYY-MM
GET /api/forecast/{label}/download
```

`POST /api/forecast` deve:

- ricevere area e mesi input;
- lanciare il runner nativo one-step;
- forzare la modalita senza confronto osservato;
- convertire l'output nativo in formato BIOMAP minimale;
- restituire label, bounds, input months, forecast month, summary e link agli output.

### Comando tecnico iniziale

Su Broan:

```powershell
python scripts/forecast_native_one_step.py --city madrid --start 2020-11-01 --end 2020-12-01 --checkpoint small --device cuda --no-compare-observed
python scripts/native_to_biomap.py --run-dir F:\biomap_store\outputs\local_preview\model_forecast\madrid_2020_12_native_one_step
```

### Output UI one-step

La UI forecast one-step deve mostrare:

- area selezionata;
- mesi input;
- mese previsto;
- checkpoint;
- device;
- tabella valori previsti;
- export tabella;
- mappa previsiva se sono disponibili celle o matrici esportabili;
- grafico solo se esiste una serie temporale forecast.

Nota importante: l'adapter BIOMAP attuale esporta forecast minimo per temperatura, precipitazione e species proxy. NDVI, SWVL1, SWVL2 e Cropland forecast vanno aggiunti solo dopo verifica che siano disponibili, correttamente mappati e scientificamente descrivibili.

## 5. Implementare Rollout Multi-Step

Dopo il one-step funzionante, aggiungere selezione orizzonte:

```text
1 mese | 6 mesi | 12 mesi
```

Regola operativa:

- `1 mese` usa one-step;
- `6 mesi` usa rollout ed e l'MVP multi-step;
- `12 mesi` usa rollout ma resta sperimentale finche non si valuta stabilita e plausibilita.

### Comando tecnico per 6 mesi

```powershell
python scripts/forecast_native_rollout.py --city madrid --start 2020-11-01 --end 2020-12-01 --checkpoint small --device cuda --steps 6
python scripts/native_to_biomap.py --run-dir F:\biomap_store\outputs\local_preview\model_forecast\madrid_2020_12_native_rollout_6m
```

### Comando tecnico per 12 mesi

```powershell
python scripts/forecast_native_rollout.py --city madrid --start 2020-11-01 --end 2020-12-01 --checkpoint small --device cuda --steps 12
python scripts/native_to_biomap.py --run-dir F:\biomap_store\outputs\local_preview\model_forecast\madrid_2020_12_native_rollout_12m
```

### Output UI rollout

La UI rollout deve mostrare:

- lista ordinata dei mesi previsti;
- tabella con una riga per mese previsto;
- grafico trend forecast futuro;
- selezione mese per mappa previsiva;
- export CSV/Excel;
- messaggio chiaro che il rollout e una proiezione multi-step e non una osservazione.

### Accettazione rollout

Il rollout e accettabile se:

- produce `forecast_months` ordinati;
- produce un valore per ogni mese previsto;
- non produce serie interamente nulle o costanti;
- non rompe il one-step;
- la UI distingue chiaramente 6 mesi MVP e 12 mesi sperimentale;
- i file esportati sono leggibili.

## 6. Validazione Forecast Senza Osservati

Il prodotto forecast deve essere validato senza confronto con osservati nella UI.

Controlli richiesti:

- run completato senza errori;
- `forecast_native_manifest.json` presente;
- `forecast_month` o `forecast_months` futuri e corretti;
- coordinate coerenti con l'area selezionata;
- valori non tutti nulli;
- valori non tutti costanti;
- unita corrette;
- range plausibili per temperatura e precipitazione;
- export leggibile;
- UI senza `MAE`, `RMSE`, `Bias`, `WAPE`, `SMAPE` o metriche di errore.

Eventuali confronti predetto/osservato possono restare disponibili come backtest tecnico separato, utile per sviluppo e debugging, ma non devono entrare nel contratto utente della modalita forecast.

## 7. Checklist Finale Prima Di Merge

Prima di riportare il forecast su `main`:

```powershell
python -m py_compile scripts/selected_area_indicators.py backend_api/main.py scripts/forecast_native_one_step.py scripts/forecast_native_rollout.py scripts/native_to_biomap.py

cd web-ui
npx tsc --noEmit
npm run build
```

Test manuali:

- osservativo ancora funzionante;
- forecast one-step funzionante;
- rollout 6 mesi funzionante;
- rollout 12 mesi marcato come sperimentale;
- export forecast leggibile;
- nessuna metrica osservata nella UI forecast;
- nessuna metrica forecast nella UI osservativa.

Solo dopo questi controlli il branch `feature/forecast-ui-native` puo essere candidato a merge su `main`.

## Assunzioni

- `main` contiene la parte osservativa stabile.
- Il branch forecast parte solo dopo validazione osservativa su Broan.
- Il forecast principale e futuro, non backtest.
- Il rollout a 6 mesi e il primo obiettivo multi-step.
- Il rollout a 12 mesi e fattibile tecnicamente, ma sperimentale dal punto di vista scientifico.
