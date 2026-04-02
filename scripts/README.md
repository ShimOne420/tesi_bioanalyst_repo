# Scripts

Questa cartella contiene gli script Python riutilizzabili del progetto.

## Struttura logica

Gli script sono organizzati in tre gruppi:

- setup e controllo ambiente
- accesso e verifica del dataset
- calcolo degli indicatori su un'area selezionata
- forecasting locale con il modello BioAnalyst

## Stato Del Blocco Forecast

Il blocco `BioAnalyst forecast` oggi e in questo stato:

- i file necessari sono presenti;
- i pesi `small` sono stati scaricati su `Archivio`;
- il repo ufficiale `bfm-model` e collegato localmente;
- l'ambiente `.venv-bioanalyst` esiste;
- l'adapter BIOMAP esiste;
- il primo smoke test locale del modello e stato completato con output salvati;
- il forecast one-step completo con `era5_pressure.nc` e stato eseguito con successo;
- il rollout completo a `+2 mesi` e `+6 mesi` e stato eseguito con successo.

Quindi i file forecast qui sotto non sono "teorici", ma vanno letti come:

- `setup pronto`
- `infrastruttura pronta`
- `one-step completo chiuso`
- `rollout multi-step chiuso a livello tecnico`
- `validazione scientifica ancora aperta`

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

### [activate_bioanalyst_model.sh](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_bioanalyst_model.sh)

Serve per entrare nel sottosistema del modello `BioAnalyst` senza sporcare l'ambiente principale del progetto.

Cosa fa:

- attiva l'ambiente Python dedicato `.venv-bioanalyst`
- carica le variabili del `.env`
- esporta il path del repo ufficiale `bfm-model`
- aggiunge il repo al `PYTHONPATH` come fallback

Quando usarlo:

- ogni volta che lavori sulla parte forecast o sui pesi del modello
- e il primo comando da eseguire quando riprendi il lavoro sul modello

Comando:

```bash
source scripts/activate_bioanalyst_model.sh
```

### [download_bioanalyst_weights.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/download_bioanalyst_weights.py)

Scarica i checkpoint ufficiali di BioAnalyst nel path esterno definito da `BIOANALYST_MODEL_DIR`.

Cosa fa:

- legge la cartella pesi dal `.env`
- usa il repository ufficiale Hugging Face `BioDT/bfm-pretrained`
- scarica o riprende il download del checkpoint `small` o `large`

Perche e utile:

- tiene i pesi fuori da GitHub
- rende ripetibile il setup per tutti i collaboratori

Stato attuale:

- il checkpoint `small` e gia presente in `BIOANALYST_MODEL_DIR`
- questo script resta utile per verifiche, listing o download futuri
- `pyarrow` e stato installato nel venv modello per supportare il parquet specie

Comandi tipici:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/download_bioanalyst_weights.py --checkpoint small
python scripts/download_bioanalyst_weights.py --list
```

### [bioanalyst_model_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/bioanalyst_model_utils.py)

Questo file non va lanciato direttamente.

E il modulo di supporto del forecasting e contiene la logica comune che serve a:

- risolvere il dominio 160x280 del modello
- costruire i batch `.pt` a partire da `BioCube`
- mappare la selezione `citta / punto / bbox`
- caricare le variabili ufficiali del modello dai file `ERA5`
- riempire con placeholder i gruppi che non abbiamo ancora scaricato
- aggregare il forecast finale sull'area selezionata

In pratica questo file fa il ponte tra:

- dati raw di `BioCube`
- formato batch richiesto da `bfm-model`
- output finale leggibile da `BIOMAP`

Nota importante:

- questo file non va lanciato da solo
- e il modulo centrale del forecast
- e gia usato da [forecast_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py)
- e gia usato da [forecast_rollout_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_rollout_area_indicators.py)

### [forecast_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py)

Questo e lo script principale della fase forecast.

Cosa fa:

- prende una selezione `area + periodo`
- usa gli ultimi due mesi osservati del periodo come input del modello
- costruisce localmente batch `.pt` compatibili con `bfm-model`
- carica il checkpoint `BioAnalyst`
- esegue un forecast a `+1 mese`
- aggrega l'output predetto sull'area selezionata
- se disponibile, confronta la previsione con il mese osservato successivo

Perche e importante:

- e l'adapter BIOMAP della fase 3
- parte gia da `city / point / bbox + periodo`
- prepara l'output forecast in formato leggibile dalla UI e dalla tesi

Stato attuale:

- lo script e implementato
- il comando di test e definito
- il run `--fast-smoke-test` e stato eseguito con successo
- la modalita completa con blocco atmosferico reale e stata eseguita con successo
- il bug sul catalogo citta del modulo forecast e gia stato corretto

Comando tipico:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Interpretazione corretta del comando sopra:

- e il test one-step completo gia chiuso a livello tecnico
- produce un forecast del mese successivo a partire dagli ultimi due mesi osservati del periodo selezionato

Comando smoke test gia validato:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --fast-smoke-test
```

Che cosa dimostra questo smoke test:

- il checkpoint si carica;
- il modello esegue il forward;
- gli output vengono salvati;
- l'adapter BIOMAP e compatibile con il formato richiesto da `bfm-model`.

Che cosa NON dimostra ancora:

- validita scientifica dei valori forecast;
- robustezza scientifica del forecast su piu casi e piu finestre storiche.

Nota pratica:

- il parametro `--city` ora supporta sia i nomi del catalogo sia alcuni alias comuni usati da CLI, per esempio `milano`

Output prodotti:

- `forecast_area_indicators.csv`
- `forecast_area_indicators_excel.csv`
- `forecast_area_indicators.xlsx`
- `forecast_config.yaml`
- `forecast_summary.json`
- cartella `batches/` con i batch raw usati nel test

Perche e importante:

- e il primo adapter vero tra la nostra selezione UI `area + periodo` e il modello ufficiale `BioAnalyst`
- consente un test locale riproducibile prima di portare il forecast nell'interfaccia

### [forecast_rollout_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_rollout_area_indicators.py)

Questo e lo script della fase 4.

Cosa fa:

- riusa il batch iniziale costruito per il forecast one-step
- esegue rollout ricorsivi a `+N mesi`
- salva una tabella forecast mese per mese
- aggiunge, quando possibile, il confronto con l'osservato reale fino a `2020-12`

Perche e importante:

- e il primo forecast multi-step compatibile con BIOMAP
- prepara il formato che useremo poi nell'interfaccia per il bottone `previsione`
- separa bene la fase tecnica di forecasting dalla futura fase di validazione

Stato attuale:

- il rollout `+2 mesi` completo e stato eseguito con successo
- il rollout `+6 mesi` completo e stato eseguito con successo
- gli output vengono salvati in `csv`, `excel_csv`, `xlsx`, `json` e `yaml`
- i valori risultano ancora non plausibili dal punto di vista scientifico, quindi il file va letto come strumento tecnico e non ancora come risultato finale

Comando tipico:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_rollout_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --steps 6
```

Output prodotti:

- `forecast_rollout_6m.csv`
- `forecast_rollout_6m_excel.csv`
- `forecast_rollout_6m.xlsx`
- `forecast_rollout_summary.json`
- `forecast_rollout_config.yaml`
- cartella `batches/` con i batch raw usati per l'inferenza

Nota pratica:

- su CPU locale il rollout `+6 mesi` richiede diversi minuti, quindi e normale vedere lunghi intervalli senza log tra `[4/8]` e `[5/8]`
- oggi i forecast prodotti mostrano ancora pattern sospetti, per esempio valori costanti mese su mese; la validazione di questi output appartiene alla fase 5 della roadmap
