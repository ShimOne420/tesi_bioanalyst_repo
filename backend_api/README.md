# Backend API

Questa cartella contiene il backend locale `FastAPI` del progetto.

## Ruolo

Il backend:

- riceve richieste dalla UI `Next.js`
- richiama [selected_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/selected_area_indicators.py)
- legge gli output generati
- restituisce JSON pronto per il frontend

## Endpoint

- `GET /api/health`
- `GET /api/cities`
- `GET /api/metadata`
- `POST /api/indicators`
- `GET /api/download/{label}/{file_format}`

`/api/metadata` restituisce il periodo realmente disponibile dei tre layer minimi usati dalla UI.

`/api/download/{label}/{file_format}` espone i file prodotti dallo script Python nei formati:

- `csv`
- `excel_csv`
- `xlsx`

## Avvio locale

Dalla root del repo:

```bash
source scripts/activate_project.sh
uvicorn backend_api.main:app --reload --port 8000
```

Il dataset resta su `Archivio`, ma il backend gira in locale e quindi può leggerlo attraverso i path del file `.env`.

## Nota pratica

Se modifichi il backend o gli script dati e nella UI continui a vedere solo il primo anno o route mancanti, riavvia il processo `uvicorn`. Una sessione vecchia puo continuare a servire codice non aggiornato.
