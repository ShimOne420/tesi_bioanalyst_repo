# README Operativo

Questa guida serve per usare il progetto da sola in `Visual Studio Code` e per capire, in modo chiaro, cosa contiene ogni file principale del repository.

## 1. Obiettivo del progetto

In questa fase la tesi ha un obiettivo operativo molto preciso:

- usare `BioCube` in locale;
- verificare che il setup del progetto funzioni;
- calcolare i `3 indicatori minimi`:
  - `numero di specie`
  - `temperatura media`
  - `precipitazioni medie`

Per ora non stiamo facendo:

- training del modello;
- fine-tuning;
- mappe finali complete;
- integrazione con dataset esterni aggiuntivi.

## 2. Dove stanno le cose

### Repository locale

Questo e il codice del progetto:

- [repo locale](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo)

Qui vanno:

- script Python
- README
- notebook
- documentazione
- file di configurazione

### Dataset e output pesanti

Questi stanno fuori dal repo, sul disco esterno `Archivio`:

- [BioCube](/Volumes/Archivio/biomap_thesis/data/biocube)
- [modelli](/Volumes/Archivio/biomap_thesis/models/bioanalyst_pretrained)
- [output pesanti](/Volumes/Archivio/biomap_thesis/outputs)

Questo serve a non riempire il Mac e a non mettere dati enormi su GitHub.

## 3. Cosa contiene ogni file e cartella

### File principali in root

- [README.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/README.md)
  File principale del progetto. Spiega obiettivo, setup e scelta metodologica iniziale.

- [CONTRIBUTING.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/CONTRIBUTING.md)
  Regole di collaborazione per lavorare in piu persone con GitHub.

- [requirements.txt](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/requirements.txt)
  Elenco delle librerie Python necessarie. Ora include anche `netCDF4`, che serve per leggere i file `.nc`.

- [.env.example](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/.env.example)
  Esempio di configurazione dei path locali.

- [.env](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/.env)
  Configurazione reale del tuo computer. Non va su GitHub.

- [.gitignore](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/.gitignore)
  Dice a Git cosa non tracciare, per esempio `.venv`, dati pesanti e output locali.

### Cartella `docs/`

- [README_OPERATIVO.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/README_OPERATIVO.md)
  Questa guida pratica.

- [STRUTTURA_PROGETTO.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/STRUTTURA_PROGETTO.md)
  Spiegazione sintetica della struttura del repository.

- [SETUP_MAC_VSCODE.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/SETUP_MAC_VSCODE.md)
  Note di setup per Mac e VS Code.

- [STEP_02_DATASET_SETUP.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/STEP_02_DATASET_SETUP.md)
  Note sul download e sul posizionamento di BioCube.

- [ROADMAP_OPERATIVA_BIOANALYST.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/ROADMAP_OPERATIVA_BIOANALYST.md)
  Documento di lavoro piu vicino alla roadmap complessiva della tesi.

### Cartella `scripts/`

- [activate_project.sh](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_project.sh)
  Attiva il `venv` e carica le variabili del file `.env`.

- [check_project_setup.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/check_project_setup.py)
  Verifica che i path del progetto siano corretti.

- [biocube_download.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/biocube_download.py)
  Wrapper del downloader di BioCube. Usa automaticamente `BIOCUBE_DIR`.

- [inventory_biocube.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/inventory_biocube.py)
  Fa un inventario rapido del contenuto di BioCube.

- [locate_minimum_indicator_sources.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/locate_minimum_indicator_sources.py)
  Cerca i file candidati per i tre indicatori minimi.

- [species_indicator_preview.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/species_indicator_preview.py)
  Primo script reale per l'indicatore specie. Legge `europe_species.parquet` e crea un preview di `species richness`.

- [climate_indicator_preview.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/climate_indicator_preview.py)
  Preview di temperatura e precipitazione. Usa `t2m` e `tp` dai file `Copernicus`.

### Cartella `notebooks/`

- [README.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/README.md)
  Spiega a cosa serviranno i notebook.

- [01_setup_check.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/01_setup_check.md)
  Nota iniziale sul controllo del setup.

### Cartelle `data/`, `models/`, `outputs/`

- [data/README.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/data/README.md)
  Spiega che il dataset vero e proprio non va dentro il repository.

- [models/README.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/models/README.md)
  Nota sui modelli e sui pesi.

- [outputs/README.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/README.md)
  Spiega dove finiscono i risultati.

## 4. Decisione metodologica da capire bene

Questa e la decisione che ti avevo anticipato.

### Caso A: Europa intera per mese

Vuol dire:

- prendi un mese, per esempio `gennaio 2000`;
- calcoli un solo valore medio per tutta l'Europa;
- ripeti per tutti i mesi.

Esempio:

- `2000-01 -> temperatura media europea`
- `2000-01 -> precipitazione media europea`
- `2000-01 -> indicatore specie europeo`

Questa strada e utile per:

- verificare che i dati siano corretti;
- produrre una baseline semplice;
- testare gli script.

### Caso B: Cella spaziale + mese

Vuol dire:

- il territorio e diviso in tante celle geografiche;
- per ogni cella e per ogni mese calcoli il valore;
- ottieni un dataset molto piu ricco, utile per fare mappe.

Esempio:

- `lat, lon, 2000-01, temperatura`
- `lat, lon, 2000-01, precipitazione`
- `lat, lon, 2000-01, species richness`

Questa strada e utile per:

- mappe;
- analisi spaziali;
- hotspot;
- damage/restoration.

### Qual e la scelta giusta adesso

Per questa fase la scelta consigliata e:

1. fare prima `Europa intera per mese`
2. poi passare a `cella + mese`

Motivo:

- ti permette di chiudere una pipeline funzionante in modo rapido;
- rende molto piu facile il debug;
- ti lascia una base solida prima della parte spaziale piu pesante.

## 5. Comandi da eseguire in VS Code

### Aprire il progetto

1. apri `Visual Studio Code`
2. fai `File -> Open Folder`
3. seleziona:

- [tesi_bioanalyst_repo](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo)

4. apri il terminale integrato

### Attivare l'ambiente

Comando consigliato:

```bash
source scripts/activate_project.sh
```

Questo comando:

- attiva `.venv`
- carica le variabili del file `.env`
- prepara i path di dataset, modelli e output

### Verificare il setup

```bash
python scripts/check_project_setup.py
```

### Verificare che BioCube sia presente

```bash
python scripts/inventory_biocube.py
```

### Testare il primo indicatore: species

```bash
python scripts/species_indicator_preview.py
```

### Visualizzare le sorgenti minime dal terminale

```bash
python scripts/view_minimum_sources.py --source species --rows 5
python scripts/view_minimum_sources.py --source temperature
python scripts/view_minimum_sources.py --source precipitation
python scripts/view_minimum_sources.py --source all --rows 3
```

### Testare i due indicatori climatici in modalita veloce

```bash
python scripts/climate_indicator_preview.py --max-steps 12
```

### Eseguire il preview climatico completo

```bash
python scripts/climate_indicator_preview.py
```

### Costruire la tabella Europa intera per mese

Test veloce:

```bash
python scripts/europe_month_indicators.py --max-steps 12
```

Run completo:

```bash
python scripts/europe_month_indicators.py
```

Questo script esporta tre formati:

- `europe_month_indicators.csv`
  CSV standard, utile per script e pandas.

- `europe_month_indicators_excel.csv`
  CSV con separatore `;`, pensato per Excel in ambiente italiano.

- `europe_month_indicators.xlsx`
  File Excel vero e proprio, il piu sicuro da aprire direttamente.

### Aprire il notebook di visualizzazione

Apri in `VS Code` questo file:

- [02_europe_month_exploration.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/02_europe_month_exploration.ipynb)

Poi esegui le celle una per una.

## 6. Dove guardare i risultati

Nel mio ambiente di test i risultati di preview sono finiti qui:

- [outputs/local_preview](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview)

In locale sul tuo Mac, quando il path esterno e scrivibile, gli output finali dovrebbero andare in:

- [output esterni](/Volumes/Archivio/biomap_thesis/outputs)

Se vuoi aprire il file con `Excel`, usa preferibilmente:

- `europe_month_indicators.xlsx`
  oppure
- `europe_month_indicators_excel.csv`

## 7. Sequenza consigliata per lavorare da sola

Quando riapri il progetto, la sequenza migliore e:

1. `source scripts/activate_project.sh`
2. `python scripts/check_project_setup.py`
3. `python scripts/inventory_biocube.py`
4. `python scripts/view_minimum_sources.py --source all --rows 3`
5. `python scripts/species_indicator_preview.py`
6. `python scripts/climate_indicator_preview.py --max-steps 12`
7. `python scripts/europe_month_indicators.py --max-steps 12`
8. apri `02_europe_month_exploration.ipynb` in VS Code

Se questi passaggi funzionano, il setup del progetto e corretto e la pipeline `Europa intera per mese` e pronta.
