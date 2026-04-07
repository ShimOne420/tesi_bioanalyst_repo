# Validazione Forecast Clima

Questo documento descrive come validare il forecast di `temperatura` e `precipitazione` di BioAnalyst prima di reintegrarlo nella UI.

## Perché separare clima e specie

In questo momento:

- la pipeline `observed` del progetto è plausibile per temperatura, precipitazione e species richness osservato;
- la pipeline `forecast` del modello è ancora incerta soprattutto sulla parte specie;
- quindi il modo più rigoroso di procedere è validare prima il blocco clima.

Questo ci permette di capire se:

- il checkpoint `small` è già utilizzabile per temperatura e pioggia;
- il problema è soprattutto nella parte specie;
- oppure c'è ancora un disallineamento più profondo tra adapter locale e pipeline ufficiale.

## Cosa convalida questo blocco

Lo script dedicato è:

- [forecast_validate_climate.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_validate_climate.py)

Lo script:

- esegue backtest `one-step` su molte città e molti mesi;
- supporta anche aree custom non urbane via file JSON;
- usa sempre i `2` mesi precedenti come input, coerentemente con la pipeline mensile pubblica di BioAnalyst;
- confronta il forecast con il mese osservato reale;
- salva una tabella caso-per-caso e una tabella riassuntiva per città.

## Set iniziale consigliato

Per partire, il set core è:

- Barcelona
- Berlin
- London
- Madrid
- Milano
- Napoli
- Paris
- Lisbon
- Stockholm
- Athens
- Vienna
- Warsaw

Questo set copre:

- Europa mediterranea
- Europa occidentale
- Europa centrale
- Europa nordica
- grandi contesti urbani climaticamente diversi

## Interpretazione delle metriche

### Temperatura

Per la temperatura non è ideale usare una percentuale direttamente in `°C`, perché:

- i valori possono essere vicini a `0`;
- i segni cambiano tra inverno ed estate;
- la percentuale in Celsius può diventare instabile o poco interpretabile.

Per questo lo script usa:

- `temperature_abs_error_c`
- `temperature_pct_error_kelvin`

La percentuale in Kelvin è più stabile, ma da sola può essere troppo permissiva.

Per questo il `pass/fail` finale della temperatura usa entrambi:

- soglia percentuale in Kelvin
- soglia assoluta in `°C`

### Precipitazione

Per la precipitazione lo script usa:

- `precipitation_abs_error_mm`
- `precipitation_pct_error`
- `precipitation_smape_pct`

La `sMAPE` è preferibile quando ci sono mesi molto secchi o vicini a zero.

Anche qui il `pass/fail` finale usa sia:

- soglia percentuale `sMAPE`
- soglia assoluta in `mm`

## Nota sulle soglie 1–2%

Una soglia `1–2%` è molto severa.

Va letta così:

- per la temperatura può avere senso solo se la misuriamo come percentuale in Kelvin;
- per la precipitazione, anche con `sMAPE`, resta una soglia molto ambiziosa per serie mensili reali.

Quindi queste soglie possono essere usate come:

- `target desiderato`
- non ancora come aspettativa realistica del checkpoint `small` senza ulteriore calibrazione

Nella versione attuale dello script, le soglie di default sono:

- temperatura: `2%` in Kelvin e `2 °C` di MAE
- precipitazione: `2%` di sMAPE e `2 mm` di MAE

## Comando consigliato per un test rapido

```bash
cd /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_validate_climate.py --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cpu
```

## Comando più ampio sul periodo 2000–2020

```bash
cd /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_validate_climate.py --forecast-start 2000-03-01 --forecast-end 2020-12-01 --month-stride 3 --checkpoint small --device cpu
```

Il parametro `--month-stride 3` serve per ridurre il costo computazionale.

## Test su aree non urbane

E' disponibile anche un set iniziale di aree naturali qui:

- [validation_non_urban_areas.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/data/validation_non_urban_areas.json)

Comando:

```bash
cd /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_validate_climate.py --areas-json data/validation_non_urban_areas.json --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cuda
```

Per una validazione completa mensile:

```bash
python scripts/forecast_validate_climate.py --forecast-start 2000-03-01 --forecast-end 2020-12-01 --month-stride 1 --checkpoint small --device cpu
```

## Dove finiscono i risultati

Gli output vengono salvati nella cartella configurata da:

- `PROJECT_OUTPUT_DIR`

Nel setup corrente, di solito:

- `/Volumes/Archivio/biomap_thesis/outputs`

I file più importanti sono:

- `forecast_validation_climate_cases.xlsx`
- `forecast_validation_climate_city_summary.xlsx`
- `forecast_validation_climate_summary.json`

Per leggere rapidamente un run gia concluso puoi usare anche:

- [inspect_forecast_validation_report.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/inspect_forecast_validation_report.py)

Comando:

```bash
cd /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo
source scripts/activate_bioanalyst_model.sh
python scripts/inspect_forecast_validation_report.py
```

Questo script:

- trova l'ultimo run disponibile
- stampa le metriche globali
- mostra migliori e peggiori citta per temperatura e precipitazione
- salva un file `forecast_validation_climate_report.md` nella cartella del run

## Decisione successiva

Se il clima passa una validazione credibile:

- si può passare alla validazione forecast della parte specie
- oppure costruire una strategia ibrida: forecast modello per clima + species derivata/calibrata

Se il clima non passa:

- prima si corregge la pipeline locale
- solo dopo si valuta il passaggio da `small` a `large`
