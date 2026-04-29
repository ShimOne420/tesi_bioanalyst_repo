# Report operativo workbook unico BIOMAP

## Obiettivo implementato

Il workbook finale BIOMAP viene aggiornato sempre sullo stesso file a fine run, ma con una struttura piu filtrabile e piu sostenibile per i test Europe-wide.

Workbook canonico:

`outputs/local_preview/model_forecast/SINTESI_AFFIDABILITA_MODEL_FORECAST_2017_2020/BIOMAP_FINAL_FEATURE_ANALYSIS_NATIVE_BIOANALYST.xlsx`

## Correzione architetturale

La prima idea teneva nel workbook anche il dettaglio storico cella-per-cella di tutte le variabili principali e di tutte le specie. In pratica questo rendeva molto lenta la fase finale di scrittura Excel.

La struttura aggiornata separa due livelli:

- workbook finale filtrabile e leggibile;
- storico full-grid esterno in CSV leggibili da Excel.

## Struttura attuale del workbook

### Fogli cumulativi di sintesi

- `Dashboard_BIOMAP`
- `BIOMAP_Indicator_Map`
- `Coverage`
- `Metric_Guide`
- `Species_Biodiversity`
- `All_Variables`

### Fogli indice

- `Run_Index`
- `City_Area_Index`
- `Species_Index`

### Fogli principali filtrabili

- `Temperature_t2m`
- `Precipitation_tp`
- `Vegetation_NDVI`
- `Edaphic_swvl1`
- `Edaphic_swvl2`
- `Agriculture_Cropland`

Ogni riga rappresenta un run su una certa area, quindi il file si puo filtrare per:

- anno
- mese
- area/citta
- variabile
- checkpoint
- input mode

Le colonne principali sono:

- `run_id`
- `forecast_month`
- `forecast_year`
- `forecast_month_num`
- `label`
- `area_label`
- `selection_mode`
- `center_lat`
- `center_lon`
- `min_lat`
- `max_lat`
- `min_lon`
- `max_lon`
- `predicted_mean`
- `observed_mean`
- `predicted_min`
- `predicted_max`
- `observed_min`
- `observed_max`
- `mae`
- `rmse`
- `bias`
- `correlation`
- `relative_mae_pct`

### Foglio unico specie

Le 28 specie non sono piu salvate come 28 fogli separati.

Adesso esiste:

- `Species_All`

Con una riga per:

- run
- area
- specie

Colonne principali:

- `species_id`
- `species_channel`
- `tp`
- `fp`
- `fn`
- `tn`
- `precision`
- `recall`
- `f1_score`
- `jaccard_similarity`
- `sorensen_similarity`
- `mae`
- `rmse`
- `bias`
- `correlation`
- `relative_mae_pct`

`Species_Index` serve invece come lookup iniziale degli ID specie. Per ora mostra gli ID dei canali target BioAnalyst; il nome scientifico potra essere aggiunto quando avremo una lookup tassonomica leggibile.

## Storico full-grid esterno

Il dettaglio cella-per-cella Europe-wide resta fuori dal workbook finale.

Questo storico continua a essere utile per:

- mappe;
- verifiche locali;
- analisi piu profonde;
- futuro front-end.

I file esterni principali sono:

- `*_cell_matrix_full_grid.csv`
- `*_cell_matrix_selected_area.csv`
- `*_area_summary.csv`
- `bioanalyst_native_full_output_group_csv/*.csv`
- `biomap_final_*.csv`

## CSV compatibili con Excel italiano

Per evitare il problema "Excel apre tutto in una colonna", i CSV vengono ora scritti in formato Excel-friendly:

- `encoding = utf-8-sig`
- `sep = ;`
- `decimal = ,`

Quindi, quando apri il CSV in Excel italiano, le colonne dovrebbero gia risultare separate correttamente.

## Risultato pratico

Con questa struttura:

- il workbook finale resta unico;
- ogni run aggiunge nuovi dati senza creare workbook separati;
- il filtro per anno/mese/area diventa realistico;
- le specie sono consultabili in un'unica pagina;
- il full-grid storico non si perde, ma non appesantisce il workbook finale.

## Prossimi step consigliati

1. Validare un run reale end-to-end con questa nuova struttura.
2. Aggiungere una lookup tassonomica per `Species_Index`.
3. Valutare un export multi-feature full-grid del singolo run, sempre in CSV Excel-friendly.
4. Preparare un layer intermedio per citta/aree specifiche, utile al futuro front-end BIOMAP.
