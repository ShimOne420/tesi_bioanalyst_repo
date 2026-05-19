# Backend API

Questa cartella contiene il backend locale `FastAPI` del progetto.

## Ruolo

Il backend:

- riceve richieste dalla UI `Next.js`
- richiama [selected_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/selected_area_indicators.py)
- legge gli output generati
- restituisce JSON pronto per il frontend
- espone anche il catalogo completo delle città europee a partire da [european_cities.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/data/european_cities.json)

## Endpoint

- `GET /api/health`
- `GET /api/cities`
- `GET /api/metadata`
- `POST /api/indicators`
- `GET /api/cells/{label}?month=YYYY-MM`
- `GET /api/download/{label}/{file_format}`

`/api/metadata` restituisce il periodo realmente disponibile dei tre layer minimi usati dalla UI.

`/api/download/{label}/{file_format}` espone i file prodotti dallo script Python nei formati:

- `csv`
- `excel_csv`
- `xlsx`

`/api/cells/{label}` legge il parquet cella-per-mese dell'ultimo calcolo con quella label e restituisce le celle usate dalla mappa tematica osservativa.

## Avvio locale

Dalla root del repo:

```bash
source scripts/activate_project.sh
uvicorn backend_api.main:app --reload --port 8000
```

Il backend legge prima `.env` e poi `.env.local`. Il file `.env.local` serve per i path specifici della macchina e sovrascrive `.env`.

Sulla macchina universitaria Windows, se hai spostato BioCube sul disco SSD `F:`, crea nella root del repo un file `.env.local` partendo da `.env.local.example`:

```powershell
Copy-Item .env.local.example .env.local
notepad .env.local
```

Dentro `.env.local` imposta `BIOCUBE_DIR` sulla cartella reale `biocube`, ad esempio:

```env
BIOCUBE_DIR=F:/biomap_thesis/data/biocube
PROJECT_OUTPUT_DIR=outputs/local_preview
BIOANALYST_MODEL_DIR=models
```

Usa slash `/` anche su Windows, cosi eviti problemi di escape con `\`.

## Nota pratica

Se modifichi il backend o gli script dati e nella UI continui a vedere solo il primo anno o route mancanti, riavvia il processo `uvicorn`. Una sessione vecchia puo continuare a servire codice non aggiornato.
