# Report operativo workbook unico BIOMAP

## Obiettivo implementato

Da ora la pipeline puo aggiornare sempre lo stesso workbook finale BIOMAP a fine run, invece di lasciare il file finale scollegato dal forecast appena eseguito.

Workbook canonico:

`outputs/local_preview/model_forecast/SINTESI_AFFIDABILITA_MODEL_FORECAST_2017_2020/BIOMAP_FINAL_FEATURE_ANALYSIS_NATIVE_BIOANALYST.xlsx`

## Cosa e stato fatto

### 1. Nuovo modulo dedicato

E stato creato:

`scripts/biomap_final_workbook.py`

Questo modulo:

- scansiona i run BioAnalyst disponibili sotto `outputs/local_preview/model_forecast`;
- calcola le metriche cumulative su tutti i run trovati;
- rigenera il workbook finale BIOMAP;
- crea/aggiorna un documento operativo collegato.

### 2. Aggancio automatico in `run.py`

`scripts/run.py` ora richiama automaticamente il builder del workbook finale a fine forecast, salvo opt-out esplicito.

Nuove opzioni CLI:

- `--biomap-final-workbook`
- `--no-biomap-final-workbook`

### 3. Unificazione del rebuild manuale

Lo script storico:

`outputs/local_preview/model_forecast/SINTESI_AFFIDABILITA_MODEL_FORECAST_2017_2020/build_final_biomap_analysis.py`

ora e un wrapper leggero che usa la stessa logica del nuovo modulo. Questo evita di avere due pipeline diverse per lo stesso file finale.

## Struttura attuale del workbook

### Fogli cumulativi

Questi fogli vengono ricostruiti usando tutti i run trovati:

- `Dashboard_BIOMAP`
- `BIOMAP_Indicator_Map`
- `Coverage`
- `Metric_Guide`
- `Species_Biodiversity`
- `All_Variables`

### Fogli di dettaglio latest-run

Per ogni feature disponibile nel batch native del run piu recente vengono creati fogli dedicati con dettaglio cella-per-cella.

Per ogni foglio variabile sono presenti:

- `lat`
- `lon`
- `observed`
- `predicted`
- `difference`
- `abs_error`
- `mae`
- `rmse`
- `bias`
- `correlation`
- `relative_mae_pct`

In piu, quando la feature appartiene al gruppo `species`, vengono aggiunte anche metriche binarie:

- `tp`
- `fp`
- `fn`
- `tn`
- `precision`
- `recall`
- `f1_score`
- `jaccard_similarity`
- `sorensen_similarity`

## Scelta tecnica importante

Non e stata implementata una cronologia completa cella-per-cella di **tutti** i run dentro ogni singolo foglio variabile.

Motivo:

con test Europe-wide e molte feature native, salvare ogni run come nuove righe dentro ogni pagina del workbook porterebbe molto rapidamente a limiti pratici di Excel per dimensione, numero di celle e tempi di apertura/salvataggio.

Per questo la soluzione adottata e:

- **storico cumulativo** nelle pagine di sintesi;
- **dettaglio cella-per-cella del latest run** nelle pagine variabile.

Questa scelta mantiene il file unico, aggiornato e ancora utilizzabile.

## Verifiche fatte

- compilazione Python riuscita con `py_compile`;
- aggancio in `run.py` verificato sintatticamente;
- wrapper storico riallineato alla nuova pipeline.

Nota:

il rebuild completo del workbook con fogli di dettaglio Europe-wide puo richiedere tempo significativo. La struttura e pronta, ma le performance reali vanno validate sulla macchina BioAnalyst principale durante un run reale.

## Prossimi step consigliati

1. Validare un run reale end-to-end sulla macchina principale e misurare tempo di scrittura del workbook finale.
2. Se il tempo e troppo alto, spostare lo storico cella-per-cella completo in CSV/Parquet e lasciare in Excel solo il latest run + le sintesi cumulative.
3. Aggiungere l'export multi-feature tabellare del singolo run in `exports/reliable_features/`.
4. Se vuoi una lettura biologica piu forte, estendere le specie con metriche threshold-specific piu esplicite per singola specie.
