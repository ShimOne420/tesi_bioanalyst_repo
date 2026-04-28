# Workflow Estensione BioCube 2020-2026 Per Inferenza Futura

Stato documento: 2026-04-28

## Obiettivo

L'obiettivo non e solo far girare BioAnalyst con nuovi mesi.

L'obiettivo corretto e:

1. estendere i dati di input oltre il periodo 2000-2020;
2. ricostruire batch compatibili con BioAnalyst;
3. validare il modello fuori periodo con hindcast 2020-2026;
4. solo dopo usare il modello per scenari futuri oltre il 2026.

Questo approccio e molto piu solido di un semplice "carico ERA5 e vedo se gira".

## Risposta breve alla domanda principale

### Basta aggiungere solo ERA5?

No, non per una replica fedele del workflow BioAnalyst/BioCube.

Le fonti ufficiali BioCube mostrano che il dataset usato da BioAnalyst non contiene solo clima ERA5, ma un insieme multimodale che include:

- climate / surface / atmospheric ERA5;
- single-level variables;
- NDVI;
- species observations;
- descriptions;
- eDNA;
- distribution trends;
- red list;
- agriculture;
- forest.

Quindi:

- per un test minimo di generalizzazione climatica, ERA5 puo bastare come primo blocco;
- per una estensione coerente del fusion model, ERA5 da solo non basta.

### E fattibile estendere fino al 2026?

Si, tecnicamente e fattibile, ma in modo graduale.

La strada piu realistica e:

1. estendere prima i blocchi abiotici e vegetazionali;
2. validare il modello su 2020-2026;
3. decidere solo dopo come trattare species, red list ed eventuali scenari 2027+.

## Cosa dicono le fonti ufficiali

### 1. Orizzonte temporale ufficiale BioCube

La dataset card ufficiale di BioCube dichiara che le modalita sono allineate su griglia WGS84 a 0.25 gradi e coprono il periodo 2000-2020. Solo NDVI e indicata a 0.1 gradi prima del riallineamento.

Questo significa che non esiste, nelle fonti ufficiali che abbiamo verificato, un BioCube gia pronto 2020-2026 da scaricare direttamente.

### 2. Modalita ufficiali

Le fonti ufficiali elencano queste famiglie di dati:

- Surface Climate da ERA5
- Atmospheric Variables da ERA5
- Single-Level Variables da ERA5
- Species Observations
- Descriptions
- eDNA
- Distribution Trends
- Red List Index
- NDVI
- Agriculture Indicators
- Forest Indicators

Quindi il modello nasce davvero come fusion model, non come climate model puro.

### 3. Procedura ufficiale per aggiungere nuovi dati

Il repository ufficiale `BioDT/bfm-data` dice esplicitamente che il codice supporta:

- download;
- ingestion;
- preprocessing;
- dataset creation;
- batch creation.

Nel README compaiono esempi operativi molto chiari:

- download ERA5 con:
  - `era5(mode='range', start_year='2020', end_year='2024')`
- processing agriculture con:
  - `run_agriculture_data_processing(...)`
  - `run_agriculture_merging()`
- species dataset con:
  - `create_species_dataset(...)`
- batch mensili con:
  - `scan_biocube.py`
  - `build_batches_monthly.py`
- statistiche per normalizzazione con:
  - `batch_stats.py`

Questa e la base ufficiale da seguire.

## Implicazione metodologica importante

Se vogliamo essere rigorosi, dobbiamo distinguere tre livelli.

### Livello A - Test minimo di generalizzazione

Obiettivo:

- capire se BioAnalyst-small riesce a generalizzare fuori periodo almeno su variabili fisiche ben osservabili.

Dati minimi:

- ERA5 surface
- ERA5 atmospheric
- ERA5 single-level
- ERA5 edaphic

Molto consigliato aggiungere subito anche:

- NDVI

### Livello B - Estensione parziale ma credibile del fusion model

Obiettivo:

- mantenere una struttura piu simile a BioCube, senza pretendere di ricostruire da subito tutto il dataset completo.

Dati da aggiungere:

- ERA5 completo
- NDVI
- agriculture
- forest
- land

Questa e, ad oggi, la strategia migliore per la tesi.

### Livello C - Replica multimodale piu completa

Obiettivo:

- avvicinarsi davvero alla filosofia BioCube/BioAnalyst completa.

Richiederebbe inoltre:

- species observations aggiornate;
- descriptions / taxa metadata;
- eDNA;
- red list / RLI aggiornati;
- distribution trends.

Questa fase e la piu ambiziosa e non la userei come primo target operativo.

## Dataset che servono davvero

## Blocco 1 - ERA5 climatico e fisico

Questo e il primo blocco da estendere.

Serve:

- `t2m`
- `u10`
- `v10`
- `msl`
- `lsm`
- `z`
- `slt`
- `swvl1`
- `swvl2`
- `stl1`
- `stl2`
- atmospheric multilevel:
  - `z`
  - `t`
  - `q`
  - `u`
  - `v`
- climate group:
  - `tp`
  - `smlt`
  - `csfr`
  - `avg_sdswrf`
  - `avg_snswrf`
  - `avg_snlwrf`
  - `avg_tprate`
  - `avg_sdswrfcs`
  - `sd`
  - `d2m`
  - `t2m`

Motivo:

- sono i blocchi piu dinamici;
- sono i piu facili da validare contro osservato;
- sono il cuore della generalizzazione fuori periodo.

## Blocco 2 - NDVI

NDVI va esteso quasi subito.

Motivo:

- collega clima e vegetazione;
- e una delle variabili piu promettenti per BIOMAP;
- il dataset card BioCube lo considera parte ufficiale del cubo.

Nota operativa:

- NDVI originale non e nativamente sulla stessa risoluzione dei batch finali;
- va aggregato / riallineato coerentemente alla griglia BioCube.

## Blocco 3 - Agriculture / Forest / Land

Questi dati non sono necessariamente mensili.

La strategia consigliata e:

- se trovi aggiornamenti 2020-2026 coerenti, li usi;
- se i dati restano annuali, replichi il valore annuale su tutti i mesi dell'anno;
- se alcuni layer restano quasi statici, li tratti come contesto, non come target dinamico.

Questo blocco e importante per BIOMAP perche lega il forecast ambientale a indicatori di pressione antropica.

## Blocco 4 - Species / Red List / Distribution Trends

Questo e il blocco piu delicato.

Dal punto di vista della tesi, io lo tratterei cosi:

- non come primo step per validare la generalizzazione 2020-2026;
- ma come estensione successiva, dopo che la pipeline abiotica e vegetazionale e stabile.

Motivo:

- i dati specie sono molto piu complessi da aggiornare, filtrare e riallineare;
- le metriche non sono solo MAE/RMSE, ma anche F1, Jaccard, Sorensen;
- il rischio di rumore e molto piu alto.

## Cosa possiamo realisticamente fare nella tesi

La strategia piu solida e questa.

### Fase 1 - Estensione abiotica + vegetazionale

Estendiamo:

- ERA5
- NDVI
- Agriculture
- Forest
- Land

Obiettivo:

- mantenere il modello il piu possibile "fusion" senza bloccarci subito sul modulo specie.

### Fase 2 - Hindcast 2020-2026

Per ogni mese:

- input = due mesi osservati
- output = previsione del mese successivo
- confronto = dato reale del mese previsto

Esempio:

- maggio 2020 + giugno 2020 -> previsione luglio 2020
- confronto con osservato luglio 2020

Questo e il test serio di generalizzazione fuori periodo.

### Fase 3 - Valutazione per variabile

Variabili prioritarie:

- `t2m`
- `tp`
- `swvl1`
- `swvl2`
- `NDVI`
- `Cropland`

Metriche:

- `observed`
- `predicted`
- `difference`
- `MAE`
- `RMSE`
- `bias`
- `correlation`
- `relative_mae_pct`

Per species, solo in una fase successiva:

- `tp`
- `fp`
- `fn`
- `tn`
- `precision`
- `recall`
- `F1`
- `Jaccard`
- `Sorensen`

### Fase 4 - Scenari futuri oltre il 2026

Solo dopo la validazione fuori periodo:

- input reale fino al 2026
- rollout 2027+

Questo non va descritto come previsione certificata, ma come:

- scenario esplorativo autoregressivo ottenuto da BioAnalyst-small senza fine-tuning.

## Workflow operativo consigliato

## Step 0 - Definire il target della prima estensione

Primo target realistico:

- Europa
- griglia BioAnalyst
- dati 2020-2026
- checkpoint `small`
- input mode il piu completo possibile

La prima domanda pratica non e "riusciamo a fare 2027?" ma:

- quali gruppi riusciamo ad aggiornare davvero fino al 2026?

## Step 1 - Audit locale della copertura dati

Prima di scaricare altro, dobbiamo misurare cosa abbiamo gia.

Per ogni sorgente locale dobbiamo costruire una tabella con:

- file
- gruppo BioAnalyst
- variabili
- copertura temporale
- copertura spaziale
- frequenza
- stato

Output atteso:

- matrice di gap 2020-2026

Questo e il primo step che possiamo fare subito nel progetto.

## Step 2 - Estendere ERA5 con workflow ufficiale

Seguendo il README di `bfm-data`:

1. scaricare i nuovi dati ERA5 per il range 2020-2026;
2. mantenere la struttura di cartelle compatibile;
3. uniformare naming e aggregazione mensile;
4. verificare che i file risultanti siano leggibili dal builder dei batch.

Questo e il primo blocco realmente dinamico da allungare.

## Step 3 - Estendere NDVI

Dobbiamo verificare:

- sorgente disponibile;
- copertura 2020-2026;
- formato;
- metodo di aggregazione mensile;
- riallineamento alla griglia 0.25 gradi.

NDVI e una priorita alta, non un extra marginale.

## Step 4 - Estendere agriculture / forest / land

Per questi gruppi la regola pratica e:

- aggiornare fino al 2026 se troviamo fonti coerenti;
- altrimenti usare valori annuali o quasi statici, esplicitando questa scelta nel manifest.

Questa e una soluzione metodologicamente accettabile, purche sia dichiarata.

## Step 5 - Decidere la strategia species

Qui dobbiamo scegliere in modo esplicito tra due strade.

### Strada prudente

- tenere species come nel dataset gia disponibile;
- usare 2020 come ultimo anno "nativo" specie;
- non usare species come prova primaria della generalizzazione lunga.

### Strada estesa

- raccogliere / processare osservazioni specie aggiornate;
- ricostruire il parquet specie;
- riallineare la pipeline di rasterizzazione.

Per la tesi, la strada prudente e piu gestibile.

## Step 6 - Ricostruire batch mensili compatibili

Una volta estese le sorgenti:

1. indicizzare il BioCube locale;
2. ricostruire i batch mensili;
3. calcolare statistiche e controlli di compatibilita;
4. verificare shapes, canali, lat/lon, tempi, scaling.

Questa e la parte dove non basta "avere i dati": serve compatibilita con la struttura del modello.

## Step 7 - Validazione fuori periodo

Qui iniziano i veri test.

Ordine consigliato:

1. luglio 2020 - dicembre 2021
2. gennaio 2022 - dicembre 2024
3. gennaio 2025 - dicembre 2026

Motivo:

- ci permette di partire subito fuori dal range 2000-2020;
- mantiene il test interpretabile;
- evita di mescolare subito tutti gli anni.

## Step 8 - Decisione BIOMAP

Dopo i test dobbiamo classificare ogni variabile in tre gruppi:

### Pronta per BIOMAP

Esempio probabile:

- `t2m`
- forse `swvl1`, `swvl2`, `NDVI`

### Utile come layer di contesto

Esempio probabile:

- `Cropland`
- `Forest`
- `Land`
- `tp` se troppo instabile come forecast ma utile come contesto

### Ancora esplorativa

Esempio probabile:

- species
- red list dinamica

## Primo step che possiamo fare subito

Il primo step migliore non e ancora scaricare tutto.

Il primo step corretto e:

1. inventario completo dei file attuali;
2. tabella copertura temporale per gruppo;
3. gap analysis 2020-2026;
4. decisione su quali gruppi estendere nella prima iterazione.

Questa fase risponde a una domanda fondamentale:

- quali dati siamo davvero in grado di aggiungere adesso senza rompere la pipeline?

## Ordine pratico consigliato

1. audit dei dati attuali
2. estensione ERA5
3. estensione NDVI
4. estensione agriculture / forest / land
5. scelta species prudente o estesa
6. ricostruzione batch mensili
7. validazione 2020-2026
8. scenari 2027+

## Giudizio finale di fattibilita

Si, il progetto e fattibile, ma con queste condizioni:

- non trattare ERA5 come unica sorgente sufficiente;
- usare il workflow ufficiale `bfm-data` come riferimento;
- partire da un'estensione parziale ma coerente;
- validare prima di parlare di previsione futura;
- tenere distinta la fase di hindcast dalla fase di scenario.

La conclusione piu forte per la tesi sarebbe questa:

- BioAnalyst-small viene testato fuori dal periodo originale su batch estesi e compatibili;
- l'errore viene misurato su 2020-2026;
- solo le variabili che reggono la validazione entrano nel framework BIOMAP per restoration/damage;
- gli scenari oltre il 2026 vengono presentati come esplorativi, non come forecast certificati.

## Fonti ufficiali usate

- BioCube dataset card: [https://huggingface.co/datasets/BioDT/BioCube](https://huggingface.co/datasets/BioDT/BioCube)
- BioDT bfm-data repository: [https://github.com/BioDT/bfm-data](https://github.com/BioDT/bfm-data)
- BioAnalyst paper page: [https://huggingface.co/papers/2507.09080](https://huggingface.co/papers/2507.09080)
