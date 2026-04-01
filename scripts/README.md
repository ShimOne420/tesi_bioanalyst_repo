# Scripts

Questa cartella contiene gli script Python riutilizzabili del progetto.

## Struttura logica

Gli script sono organizzati in tre gruppi:

- setup e controllo ambiente
- accesso e verifica del dataset
- calcolo degli indicatori su un'area selezionata

## Spiegazione dettagliata di ogni script

### [activate_project.sh](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_project.sh)

Serve per aprire il progetto nel modo corretto.

Cosa fa:

- attiva il `venv`
- carica le variabili del file `.env`
- prepara i path di lavoro del progetto

Quando usarlo:

- sempre, appena apri il terminale in `VS Code`

Comando:

```bash
source scripts/activate_project.sh
```

### [check_project_setup.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/check_project_setup.py)

Serve per verificare che il progetto punti alle cartelle giuste.

Cosa controlla:

- esistenza di `BIOCUBE_DIR`
- esistenza di `BIOANALYST_MODEL_DIR`
- esistenza di `PROJECT_OUTPUT_DIR`
- coerenza generale del setup

Quando usarlo:

- dopo avere attivato l'ambiente
- quando cambi macchina o path

Comando:

```bash
python scripts/check_project_setup.py
```

### [biocube_download.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/biocube_download.py)

E' il wrapper locale per scaricare `BioCube`.

Cosa fa:

- legge `BIOCUBE_DIR` da `.env`
- richiama il downloader vero
- permette download completi o parziali

Quando usarlo:

- la prima volta che scarichi il dataset
- se vuoi aggiungere nuovi sottoinsiemi del dataset

Esempi:

```bash
python scripts/biocube_download.py
python scripts/biocube_download.py --download
python scripts/biocube_download.py --download --include "Species/*" --include "Copernicus/*"
```

### [inventory_biocube.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/inventory_biocube.py)

Serve per vedere rapidamente che cosa c'e dentro il dataset locale.

Cosa mostra:

- dimensione complessiva
- cartelle top-level
- tipi di file
- esempi di file presenti

Quando usarlo:

- dopo il download
- quando vuoi verificare se un modulo del dataset e presente davvero

Comando:

```bash
python scripts/inventory_biocube.py
```

### [view_minimum_sources.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/view_minimum_sources.py)

Serve per ispezionare i dati minimi che alimentano i tre indicatori.

Cosa mostra:

- righe di esempio del parquet specie
- variabili e dimensioni dei file climatici
- prime date disponibili
- esempi di valori medi iniziali

Quando usarlo:

- per capire i dati prima di processarli
- per debugging
- prima di lavorare nel notebook

Esempi:

```bash
python scripts/view_minimum_sources.py --source all --rows 3
python scripts/view_minimum_sources.py --source species --rows 5
python scripts/view_minimum_sources.py --source temperature
```

### [minimum_indicator_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/minimum_indicator_utils.py)

Questo non e uno script da lanciare da solo.

E il modulo condiviso che contiene la logica tecnica comune a tutti gli altri script.

Nel concreto contiene:

- il bounding box europeo standard del progetto
- la normalizzazione delle longitudini
- il ritaglio del dataset sull'Europa
- la costruzione della maschera terra
- i filtri temporali mensili per `DataFrame` e `xarray`
- la costruzione di un bounding box a partire da un punto
- il ritaglio di un dataset su un bounding box arbitrario
- la scrittura degli output in `csv`, `excel_csv` e `xlsx`

Perche e importante:

- evita duplicazione di codice
- mantiene coerente la metodologia tra gli script
- rende piu facile evolvere il backend verso una futura interfaccia

In pratica:

- se uno script deve capire `cos'e Europa`
- come filtrare per mese
- come selezionare un'area
- come esportare un output leggibile

allora usa questo file.

### [selected_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/selected_area_indicators.py)

Questo e lo script principale del progetto.

E' pensato come backend unico per la futura interfaccia su mappa, quindi unifica in un solo punto la vecchia logica:

- `cella + mese`
- query su area e periodo

Cosa accetta:

- una `citta` predefinita, per esempio `milano`
- oppure un `punto` con `lat/lon` e finestra spaziale
- oppure un `bounding box` completo, che corrisponde bene alla futura selezione a rettangolo sulla mappa

Cosa richiede:

- `--start`
- `--end`
- una modalita di selezione dell'area

Cosa produce:

- una tabella mensile aggregata dell'area selezionata
- un dataset `cella + mese` limitato alla sola area scelta

Indicatori che restituisce:

- `species_count_observed_area`
- `temperature_mean_area_c`
- `precipitation_mean_area_mm`
- e, nel parquet per cella:
  `species_count_observed_cell`, `temperature_mean_c`, `precipitation_mean_mm`

Perche e il file giusto per il futuro:

- una UI su `Vercel` potra passargli una citta o un rettangolo selezionato sulla mappa
- la logica dei dati restera gia pronta
- non serve duplicare backend diversi per citta, aree o celle

Output principali:

- `selected_<label>_area_monthly.csv`
- `selected_<label>_area_monthly_excel.csv`
- `selected_<label>_area_monthly.xlsx`
- `selected_<label>_cells.parquet`

Comandi tipici:

```bash
python scripts/selected_area_indicators.py --list-cities
python scripts/selected_area_indicators.py --city milano --start 2000-01-01 --end 2000-12-01
python scripts/selected_area_indicators.py --city milano --half-window-deg 1.0 --start 2000-01-01 --end 2000-12-01
python scripts/selected_area_indicators.py --min-lat 44 --max-lat 46 --min-lon 8 --max-lon 10 --start 2000-01-01 --end 2000-12-01
```

### [generate_european_cities_catalog.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/generate_european_cities_catalog.py)

Questo script genera il catalogo locale completo delle citta europee usato dalla UI e dal backend.

**Cosa fa**

- legge i dati dal pacchetto `geonamescache`
- filtra i paesi con `continentcode = EU`
- costruisce un file condiviso in [european_cities.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/data/european_cities.json)
- ordina le citta per popolazione decrescente

**Quando usarlo**

- quando vuoi rigenerare il catalogo delle citta
- quando aggiorni la sorgente dati del catalogo

**Comando**

```bash
python scripts/generate_european_cities_catalog.py
```

Nota metodologica importante:

- `species_count_observed_area` e `species_count_observed_cell` sono basati sulle osservazioni presenti nel dataset
- un `NaN` sulle specie non significa automaticamente assenza biologica reale
- significa che nel dataset non risultano osservazioni per quella cella o area in quel mese
