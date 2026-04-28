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

### Fogli di dettaglio cumulativi

Per le variabili principali BIOMAP e per tutte le specie native vengono creati fogli dedicati con dettaglio cella-per-cella.

Le righe restano sempre quelle della griglia BioAnalyst (`lat`, `lon`), mentre ogni nuovo run aggiunge nuove colonne alla stessa pagina.

Per ogni foglio variabile sono presenti:

- `lat`
- `lon`
- `observed__<run_id>`
- `predicted__<run_id>`
- `difference__<run_id>`
- `abs_error__<run_id>`
- `mae__<run_id>`
- `rmse__<run_id>`
- `bias__<run_id>`
- `correlation__<run_id>`
- `relative_mae_pct__<run_id>`

In piu, quando la feature appartiene al gruppo `species`, vengono aggiunte anche metriche binarie per ogni run:

- `tp__<run_id>`
- `fp__<run_id>`
- `fn__<run_id>`
- `tn__<run_id>`
- `precision__<run_id>`
- `recall__<run_id>`
- `f1_score__<run_id>`
- `jaccard_similarity__<run_id>`
- `sorensen_similarity__<run_id>`

## Scelta tecnica importante

La cronologia cella-per-cella viene aggiunta **per colonne**, non per nuove righe.

Motivo:

con test Europe-wide, aggiungere 44.800 nuove righe per ogni run in ogni foglio porterebbe troppo presto a limiti pratici di Excel. Aggiungendo invece nuove colonne per run, il file resta unico, cumulativo e piu leggibile.

La soluzione adottata e quindi:

- **storico cumulativo** nelle pagine di sintesi;
- **storico cumulativo per colonne** nelle pagine di dettaglio principali e specie.

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
