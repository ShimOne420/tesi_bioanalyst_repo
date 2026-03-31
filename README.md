# Tesi BioAnalyst

Questo repository contiene il workspace operativo della tesi.

La fase attuale del progetto ha un blocco tecnico principale:

- selezione di `citta` o `area` europea
- filtro per `periodo`
- calcolo dei tre indicatori minimi
- output sia aggregato per area sia nel formato `cella + mese`

Lo stack locale consigliato ora e:

- `frontend locale`: Next.js su `localhost:3000`
- `backend locale`: FastAPI su `localhost:8000`
- `dataset`: BioCube su `Archivio`

Il range reale oggi esposto in UI e backend per i tre indicatori minimi e:

- `2000-01 -> 2020-12`

Per una guida pratica completa, con spiegazione di file, cartelle e comandi da usare in `Visual Studio Code`, vedi:

- [docs/README_OPERATIVO.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/README_OPERATIVO.md)

## Obiettivo

Usare `BioCube` in locale per calcolare tre indicatori minimi:

- `numero di specie osservate`
- `temperatura media`
- `precipitazioni medie`

L'architettura attuale e gia pensata per uno step successivo di servizio o interfaccia web, dove un utente non tecnico potra selezionare una localita e un periodo.

## Flusso di lavoro attuale

1. attivare il progetto
2. verificare il setup
3. ispezionare i dati minimi
4. avviare il backend locale FastAPI
5. avviare il frontend locale Next.js
6. selezionare una citta o un'area dalla UI

## Comandi principali

```bash
source scripts/activate_project.sh
python scripts/check_project_setup.py
python scripts/inventory_biocube.py
python scripts/view_minimum_sources.py --source all --rows 3
python scripts/selected_area_indicators.py --list-cities
python scripts/selected_area_indicators.py --city milano --start 2000-01-01 --end 2000-12-01
python scripts/selected_area_indicators.py --min-lat 44 --max-lat 46 --min-lon 8 --max-lon 10 --start 2000-01-01 --end 2000-12-01
uvicorn backend_api.main:app --reload --port 8000
```

Per la UI locale:

```bash
cd web-ui
npm install
npm run dev
```

## Note importanti

- i dataset pesanti e i modelli stanno fuori dal repo, su `Archivio`
- il repo GitHub contiene solo codice, notebook, documentazione e output piccoli
- il file `.env` definisce i path locali
- per `Excel`, usa preferibilmente i file `.xlsx` o i file `_excel.csv`
- se la UI mostra solo il `2000`, quasi sempre hai una sessione vecchia di frontend o backend: chiudi i processi con `Ctrl + C` e riavviali
