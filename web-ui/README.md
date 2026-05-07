# Web UI

Questa cartella contiene l'interfaccia web pensata per `Vercel`.

## Cosa fa

L'app permette di:

- selezionare una citta europea da una barra di scelta
- filtrare rapidamente migliaia di citta europee per nome o paese
- definire un periodo mensile
- disegnare manualmente un rettangolo sulla mappa d'Europa
- inviare la selezione a un backend
- visualizzare in output gli indicatori osservativi BIOMAP per mese
- esportare la tabella visualizzata in `CSV` o `Excel`
- scaricare l'output mensile in `CSV`, `CSV per Excel` o `XLSX`

La vista principale e descritta nel dettaglio in:

- [`docs/README_FRONTEND_OSSERVATIVO.md`](../docs/README_FRONTEND_OSSERVATIVO.md)

## Architettura

La UI usa `Next.js`, mentre le route API interne inoltrano le richieste al backend Python/FastAPI configurato con `PYTHON_API_BASE_URL`.

Non esiste piu un fallback demo: senza backend configurato la UI restituisce errore, cosi i risultati visualizzati sono sempre dati reali calcolati dalla pipeline Python.

Le route principali usate dalla UI sono:

- `GET /api/metadata` per leggere l'intervallo reale disponibile del dataset
- `POST /api/indicators` per calcolare gli indicatori sull'area selezionata
- `GET /api/download/:label/:format` per scaricare i file generati

## Sviluppo locale

Da questa cartella:

```bash
npm install
npm run dev
```

Per usare i dati reali in locale crea `web-ui/.env.local` con:

```bash
PYTHON_API_BASE_URL=http://127.0.0.1:8000
```

In questo modo la route API inoltra la richiesta al backend `FastAPI` locale. Se questa variabile manca, `/api/metadata`, `/api/indicators` e i download non usano dati finti: rispondono con errore di configurazione.

## Stack locale consigliato

Terminale 1, dalla root del repo:

```bash
source scripts/activate_project.sh
uvicorn backend_api.main:app --reload --port 8000
```

Terminale 2, dalla cartella `web-ui`:

```bash
npm install
npm run dev
```

Poi apri:

- [http://localhost:3000](http://localhost:3000)

## Comportamento atteso

Quando backend e frontend sono entrambi aggiornati:

- il selettore periodo usa automaticamente il range reale del dataset: `2000-01 -> 2020-12`
- puoi scegliere qualunque intervallo mensile dentro quel range
- la tabella mostra una riga per mese con temperatura, precipitazione, NDVI, SWVL1, SWVL2, Cropland e celle valide
- dopo il calcolo compaiono i pulsanti di esportazione della tabella e, se il backend locale e attivo, tre pulsanti download:
  - `Esporta CSV`
  - `Esporta Excel`
  - `Scarica CSV`
  - `Scarica CSV per Excel`
  - `Scarica XLSX`

## Se vedi ancora solo il 2000

Di solito significa che hai ancora aperta una sessione locale vecchia del backend o del frontend.

Chiudi i due processi con `Ctrl + C` e rilanciali:

```bash
source scripts/activate_project.sh
uvicorn backend_api.main:app --reload --port 8000
```

```bash
cd web-ui
npm run dev
```

## Deploy su Vercel

Questa app e pronta per essere deployata come progetto separato puntando la root della build a `web-ui`.

Nota importante:

- il deploy su Vercel, da solo, non puo leggere il dataset locale che sta su `Archivio`
- per avere output reali online serve un backend dati esterno oppure un endpoint proxy configurato con `PYTHON_API_BASE_URL`
- senza backend configurato l'app non calcola indicatori e non mostra risultati demo
