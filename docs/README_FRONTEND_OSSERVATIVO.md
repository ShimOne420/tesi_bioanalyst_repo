# README Frontend Osservativo

## Cosa e stato modificato

La schermata principale del frontend e tornata osservativa: mostra solo valori reali calcolati dai dataset BioCube per l'area e il periodo selezionati.

La tabella ha una riga per mese e queste colonne:

- `Mese`
- `Temperatura media (°C)`
- `Precipitazione mensile (mm/mese)`
- `NDVI`
- `SWVL1`
- `SWVL2`
- `Cropland`
- `Celle valide`

I pulsanti `Esporta CSV` e `Esporta Excel` scaricano esattamente la tabella visibile. Quando il backend locale e attivo restano disponibili anche i download prodotti dalla pipeline Python: `Scarica CSV`, `Scarica CSV per Excel`, `Scarica XLSX`.

## Perche non ci sono predicted e metriche forecast

La tabella con `Predicted Mean`, `Observed Mean`, `MAE`, `RMSE`, `Bias`, `WAPE`, `SMAPE` e `SMAAPE` appartiene alla logica forecast/backtest, non alla pipeline osservativa.

Per evitare confusione nella UI principale:

- `predicted` non viene mostrato nella vista osservativa;
- `features` non viene restituito da `/api/indicators`;
- il frontend usa solo il backend reale configurato con `PYTHON_API_BASE_URL`;
- i tipi forecast restano separati per una futura sezione dedicata.

Nota sulle metriche future: nello stato precedente `SMAPE` e `SMAAPE` erano duplicati nella UI. Quando la sezione forecast verra ripresa, dovra avere una spiegazione separata e metriche adatte alle singole variabili, evitando percentuali fuorvianti sulla temperatura in gradi Celsius.

## Sorgenti e significato delle variabili

| Colonna UI | Sorgente BioCube | Significato |
|---|---|---|
| Temperatura media | `Copernicus/ERA5-monthly/era5-single/era5_single.nc`, variabile `t2m` | media area in gradi Celsius |
| Precipitazione mensile | `era5-climate-energy-moisture-0.nc`, preferenza `avg_tprate`, fallback `tp` | accumulo mensile in millimetri |
| NDVI | `Land/Europe_ndvi_monthly_un_025.csv` | indice vegetazionale osservato |
| SWVL1 | `Copernicus/ERA5-monthly/era5-edaphic/era5-edaphic-0.nc`, variabile `swvl1` | acqua nel suolo superficiale |
| SWVL2 | stesso file edaphic, variabile `swvl2` | acqua nel suolo piu profondo |
| Cropland | `Agriculture/Europe_combined_agriculture_data.csv`, variabile `Cropland` | copertura agricola/cropland |
| Celle valide | griglia area selezionata | celle usate nell'aggregazione mensile |

Se una sorgente tabellare non esiste o non copre un mese, la UI deve mostrare `n.d.`. Non vengono generati valori finti per riempire la tabella.

## Come testare

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

Apri:

```text
http://localhost:3000
```

Per controlli tecnici:

```bash
python -m py_compile scripts/selected_area_indicators.py backend_api/main.py
cd web-ui
npx tsc --noEmit
npm run build
```

## Test manuale atteso

1. Seleziona una citta e calcola gli indicatori.
2. Verifica che la tabella abbia le variabili in colonne, non in righe.
3. Disegna un bounding box sulla mappa e ripeti il calcolo.
4. Verifica `Esporta CSV`.
5. Verifica `Esporta Excel`.
6. Se il backend locale e attivo, verifica anche `Scarica CSV`, `Scarica CSV per Excel` e `Scarica XLSX`.
