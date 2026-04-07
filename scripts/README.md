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
- il backtest minimo su `Milano` e `Madrid` e stato eseguito;
- il backtest esteso su `Milano`, `Madrid`, `Vienna` e `Lisbona` e stato eseguito;
- la pipeline osservativa e stata ricontrollata con valori plausibili.

Quindi i file forecast qui sotto non sono "teorici", ma vanno letti come:

- `setup pronto`
- `infrastruttura pronta`
- `one-step completo chiuso`
- `rollout multi-step chiuso a livello tecnico`
- `validazione scientifica ancora aperta`

Conclusione pratica:

- gli script osservativi sono pronti per alimentare backend e UI;
- gli script forecast sono pronti per test interni, non ancora per output utente finali.

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
- la costante della griglia ERA5 `0.25°`
- lo snapping di coordinate puntuali alla griglia ERA5
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

### [bioanalyst_model_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/bioanalyst_model_utils.py)

Questo non e uno script da lanciare da solo.

E il modulo comune del blocco forecast BioAnalyst.

Cosa contiene:

- risoluzione di citta, punti e bounding box
- path dei file sorgente BioCube usati dal modello
- costruzione dei batch `.pt` compatibili con `bfm-model`
- snapping delle osservazioni specie alla griglia ERA5 `0.25°`
- supporto a `cpu`, `mps` e `cuda`
- funzioni di scaling e inverse-scaling
- aggregazione area-level delle predizioni
- scrittura coerente di `csv`, `excel_csv`, `xlsx` e `json`

Perche e importante:

- separa la logica del modello dagli script eseguibili
- rende piu semplice validare il forecast senza duplicare codice
- e il punto centrale da cui dipendono `forecast_area_indicators.py`, `forecast_backtest_one_step.py`, `forecast_rollout_area_indicators.py` e `forecast_validate_climate.py`

### [forecast_validate_climate.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_validate_climate.py)

Questo e lo script principale per la validazione scientifica del forecast clima.

Cosa fa:

- esegue backtest `one-step` su molte citta o aree
- valida solo `temperatura` e `precipitazione`
- salva sia tabella `caso per caso` sia tabella `riassuntiva per citta`
- misura errori assoluti e percentuali robuste

Metriche chiave:

- `temperature_abs_error_c`
- `temperature_pct_error_kelvin`
- `precipitation_abs_error_mm`
- `precipitation_pct_error`
- `precipitation_smape_pct`

Regola pass/fail:

- temperatura valida solo se passa sia la soglia percentuale sia la soglia assoluta
- precipitazione valida solo se passa sia la soglia percentuale sia la soglia assoluta

Quando usarlo:

- quando vuoi capire se il checkpoint `small` e abbastanza credibile sul clima
- prima di provare a validare anche la parte specie

Esempi:

```bash
python scripts/forecast_validate_climate.py --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cuda
python scripts/forecast_validate_climate.py --areas-json data/validation_non_urban_areas.json --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cuda
```

### [inspect_forecast_validation_report.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/inspect_forecast_validation_report.py)

Serve per leggere rapidamente un run di validazione gia terminato.

Cosa fa:

- trova l'ultimo report disponibile oppure legge una cartella run specifica
- apre il `summary.json` e le tabelle `xlsx/csv`
- mostra da terminale migliori e peggiori citta o aree
- salva un report Markdown gia pronto nella cartella del run

Quando usarlo:

- subito dopo che un test GPU e terminato
- quando vuoi capire senza aprire a mano tutti gli Excel se il run e andato bene

Esempi:

```bash
python scripts/inspect_forecast_validation_report.py
python scripts/inspect_forecast_validation_report.py --run-dir /Volumes/Archivio/biomap_thesis/outputs/model_forecast/nome_run
```

### [prepare_colab_validation_subset.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/prepare_colab_validation_subset.py)

Serve per preparare il subset minimo del progetto da portare su Colab o su un'altra GPU gratuita.

Cosa copia:

- i file BioCube minimi necessari al modello
- il checkpoint `small`
- una cartella `outputs`
- un `manifest.json` finale

Quando usarlo:

- prima di spostare la validazione su Colab
- quando vuoi evitare di copiare l'intero BioCube

Esempio:

```bash
python scripts/prepare_colab_validation_subset.py --target-dir /percorso/del/tuo/staging_colab --clean
```
- `precipitation_mean_area_mm`
- e, nel parquet per cella:
  `species_count_observed_cell`, `temperature_mean_c`, `precipitation_mean_mm`

Perche e il file giusto per il futuro:

- una UI su `Vercel` potra passargli una citta o un rettangolo selezionato sulla mappa
- la logica dei dati restera gia pronta
- non serve duplicare backend diversi per citta, aree o celle

Nota metodologica importante:

- le osservazioni specie vengono allineate alla griglia ERA5 `0.25°` prima del merge con il clima
- questo riduce errori spaziali tra coordinate puntuali e celle climatiche

Output principali:

- `selected_<label>_area_monthly.csv`
- `selected_<label>_area_monthly_excel.csv`
- `selected_<label>_area_monthly.xlsx`
- `selected_<label>_cells.parquet`

Comandi tipici:

```bash
python scripts/selected_area_indicators.py --list-cities
python scripts/selected_area_indicators.py --city milano --start 2000-01-01 --end 2000-12-01
python scripts/selected_area_indicators.py --city madrid --start 2000-06-01 --end 2000-06-01
python scripts/selected_area_indicators.py --city milano --start 2018-01-01 --end 2019-12-01
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

### [prepare_colab_validation_subset.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/prepare_colab_validation_subset.py)

Prepara un subset minimo del progetto da portare su `Google Colab` o su un'altra GPU gratuita.

Cosa fa:

- copia solo i file BioCube minimi necessari al forecast;
- copia il checkpoint `small`;
- prepara una cartella `outputs`;
- scrive un `manifest.json` finale.

Perche e utile:

- evita di spostare tutto BioCube;
- rende la validazione GPU molto piu leggera;
- mantiene il workflow integrato con il progetto esistente.

Comando tipico:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/prepare_colab_validation_subset.py --target-dir /percorso/del/tuo/staging_colab --clean
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
- il modello resta ancora troppo aggressivo per essere esposto in UI come funzione finale

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

### [forecast_backtest_one_step.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_backtest_one_step.py)

Questo e lo script principale della fase 5.

Cosa fa:

- esegue forecast one-step su una o piu citta
- confronta forecast e observed sul mese successivo reale
- misura errori su temperatura, precipitazione e specie proxy
- verifica che il roundtrip `raw -> scaled -> original` sia coerente
- salva un report tabellare pronto per la tesi

Perche e importante:

- separa i bug della pipeline dai limiti del modello
- rende la validazione ripetibile
- permette di decidere se e quando portare il forecast nella UI

Stato attuale:

- testato su `Milano` e `Madrid`
- roundtrip corretto (`MAE = 0`) dopo il fix locale dello scaling
- conferma che il modello `small` tende ancora a sovrastimare soprattutto la parte specie

Comando tipico:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_backtest_one_step.py --cities milano madrid --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Comando esteso usato per il test eterogeneo:

```bash
python scripts/forecast_backtest_one_step.py --cities milano madrid vienna lisbon --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Output prodotti:

- `forecast_backtest_one_step.csv`
- `forecast_backtest_one_step_excel.csv`
- `forecast_backtest_one_step.xlsx`
- `forecast_backtest_summary.json`
- `forecast_backtest_details.json`

Nota pratica:

- questo script e il modo piu pulito per proseguire la fase 5
- se vuoi aggiungere nuove citta, basta estendere `--cities`

### [forecast_validate_climate.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_validate_climate.py)

Questo e lo script dedicato alla validazione scientifica del forecast `clima`, separato dalla parte specie.

Cosa fa:

- esegue molti backtest `one-step` su piu citta e piu mesi;
- supporta anche aree custom non urbane tramite `--areas-json`;
- usa sempre la stessa logica ufficiale a `2 timesteps` del modello;
- misura errori di temperatura e precipitazione con metriche piu stabili;
- salva sia i casi singoli sia un riassunto per citta.

Perche e utile:

- evita di giudicare il modello solo su `Milano` o `Madrid`;
- permette di testare un set piu eterogeneo di condizioni climatiche;
- aiuta a capire se il checkpoint `small` e recuperabile almeno sul blocco clima.

Metriche principali:

- `temperature_abs_error_c`
- `temperature_pct_error_kelvin`
- `precipitation_abs_error_mm`
- `precipitation_pct_error`
- `precipitation_smape_pct`

Comandi tipici:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_validate_climate.py --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cpu
```

```bash
python scripts/forecast_validate_climate.py --forecast-start 2000-03-01 --forecast-end 2020-12-01 --month-stride 3 --checkpoint small --device cpu
```

Comando su aree non urbane:

```bash
python scripts/forecast_validate_climate.py --areas-json data/validation_non_urban_areas.json --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cpu
```

Output prodotti:

- `forecast_validation_climate_cases.csv`
- `forecast_validation_climate_cases_excel.csv`
- `forecast_validation_climate_cases.xlsx`
- `forecast_validation_climate_city_summary.csv`
- `forecast_validation_climate_city_summary_excel.csv`
- `forecast_validation_climate_city_summary.xlsx`
- `forecast_validation_climate_summary.json`

Nota pratica:

- `month-stride 1` usa tutti i mesi e puo richiedere molto tempo;
- `month-stride 3` e una versione piu leggera, utile per una prima validazione sul periodo 2000-2020;
- la specie non entra ancora nel giudizio finale di questo script: qui validiamo solo il forecast clima.
