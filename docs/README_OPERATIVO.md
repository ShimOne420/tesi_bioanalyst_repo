# README Operativo

Questa guida serve per usare il progetto in `Visual Studio Code` con la struttura minima davvero utile.

## 1. Obiettivo reale del progetto

Il progetto adesso ha questo flusso:

1. capire i dati
2. selezionare una città o un'area europea
3. scegliere un periodo
4. far dialogare `frontend locale` e `backend locale`
5. ottenere gli indicatori mensili aggregati
6. avere anche il dettaglio `cella + mese` sulla stessa area

Questo e gia coerente con lo step futuro di una piccola interfaccia web con mappa, anche se l'interfaccia non va implementata ora.

## 2. Dove stanno i dati

### Codice del progetto

- [repo locale](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo)
- [strategia branch forecast](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/STRATEGIA_BRANCH_FORECAST.md)

### Dataset e output pesanti

- [BioCube](/Volumes/Archivio/biomap_thesis/data/biocube)
- [modelli](/Volumes/Archivio/biomap_thesis/models/bioanalyst_pretrained)
- [output esterni](/Volumes/Archivio/biomap_thesis/outputs)

## 3. File che servono davvero

### Root

- [README.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/README.md)
- [CONTRIBUTING.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/CONTRIBUTING.md)
- [requirements.txt](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/requirements.txt)
- [.env.example](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/.env.example)
- [.gitignore](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/.gitignore)

### Script essenziali

- [activate_project.sh](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_project.sh)
  attiva l'ambiente

- [check_project_setup.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/check_project_setup.py)
  controlla i path

- [biocube_download.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/biocube_download.py)
  gestisce il download di `BioCube`

- [inventory_biocube.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/inventory_biocube.py)
  ti dice cosa c'e nel dataset scaricato

- [view_minimum_sources.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/view_minimum_sources.py)
  mostra campioni e metadati delle sorgenti minime

- [minimum_indicator_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/minimum_indicator_utils.py)
  contiene la logica condivisa di ritaglio spaziale, filtri temporali, maschera terra ed export

- [selected_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/selected_area_indicators.py)
  script principale che accetta città, punto o bounding box e restituisce sia l'aggregato area/mese sia il dettaglio `cella + mese`

### Backend locale

- [backend_api/main.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/backend_api/main.py)
  backend FastAPI che espone `/api/health`, `/api/cities` e `/api/indicators`

- [backend_api/README.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/backend_api/README.md)
  guida rapida al backend locale

### Frontend locale

- [web-ui](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/web-ui)
  interfaccia locale Next.js con mappa, selezione città, selezione periodo e tabella risultati

### Notebook

- [01_dataset_exploration.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/01_dataset_exploration.ipynb)
  notebook generico per visualizzare dataset e output cambiando solo il path del file nella cella di configurazione

## 4. Semantica degli indicatori

### Cella + mese

Produce una riga per:

- `cella geografica`
- `mese`

con:

- `species_count_observed_cell`
- `temperature_mean_c`
- `precipitation_mean_mm`

Nota importante:

- `species_count_observed_cell` significa `numero di specie osservate in quella cella e in quel mese`
- se e `NaN`, non vuol dire automaticamente assenza reale di specie; vuol dire che non risultano osservazioni in quel dato supporto

### Area + mese

L'output aggregato sull'area selezionata usa:

- clima aggregato sull'area selezionata
- specie osservate nell'area selezionata

Quindi e gia il mattoncino giusto per una futura interfaccia con:

- selezione di citta da una barra
- selezione manuale di rettangoli sulla mappa
- scelta di un periodo
- restituzione degli indicatori in output

## 5. Comandi da usare in VS Code

### Setup iniziale

```bash
source scripts/activate_project.sh
python scripts/check_project_setup.py
python scripts/inventory_biocube.py
```

### Avvio backend locale

Nel primo terminale:

```bash
source scripts/activate_project.sh
uvicorn backend_api.main:app --reload --port 8000
```

### Avvio frontend locale

Nel secondo terminale:

```bash
cd web-ui
npm install
cp .env.local.example .env.local
npm run dev
```

Poi apri:

- [http://localhost:3000](http://localhost:3000)

### Capire i dati

```bash
python scripts/view_minimum_sources.py --source all --rows 3
```

### Città disponibili

```bash
python scripts/selected_area_indicators.py --list-cities
```

### Query su città

```bash
python scripts/selected_area_indicators.py --city milano --start 2000-01-01 --end 2000-12-01
```

Se vuoi allargare la finestra attorno alla città:

```bash
python scripts/selected_area_indicators.py --city milano --half-window-deg 1.0 --start 2000-01-01 --end 2000-12-01
```

### Query su bounding box

Questo è il caso che somiglia di più alla futura selezione rettangolare sulla mappa:

```bash
python scripts/selected_area_indicators.py --label nord_italia --min-lat 44 --max-lat 46 --min-lon 8 --max-lon 10 --start 2000-01-01 --end 2000-12-01
```

### Query su punto libero

```bash
python scripts/selected_area_indicators.py --label test_point --lat 45.4642 --lon 9.19 --half-window-deg 0.5 --start 2000-01-01 --end 2000-12-01
```

### Output prodotti

Per ogni selezione l'output tipico è:

- `selected_<label>_area_monthly.xlsx`
- `selected_<label>_area_monthly.csv`
- `selected_<label>_area_monthly_excel.csv`
- `selected_<label>_cells.parquet`

Questi file vengono prodotti dal backend Python locale e poi letti dalla UI tramite l'API FastAPI.

Nota importante:

- se `species_count_observed_area` e `NaN`, significa che in quell'area e in quel mese non risultano osservazioni specie nel dataset
- in quel caso conviene ampliare la finestra con `--half-window-deg` oppure selezionare un'area più grande

## 6. Sequenza consigliata

Quando riapri il progetto:

1. `source scripts/activate_project.sh`
2. `python scripts/check_project_setup.py`
3. `python scripts/view_minimum_sources.py --source all --rows 3`
4. `uvicorn backend_api.main:app --reload --port 8000`
5. `cd web-ui && npm install && cp .env.local.example .env.local && npm run dev`
6. apri [http://localhost:3000](http://localhost:3000)
7. seleziona una città o disegna un rettangolo sulla mappa

Se questi passaggi funzionano, la pipeline minima e pronta e puoi lavorare davvero su città, aree e periodi.
