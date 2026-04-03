# Fase 5 - Diagnostica Forecast

Stato aggiornato al `2026-04-02`.

## Obiettivo

Capire perche il forecast BioAnalyst produceva valori costanti o non plausibili e separare:

- problemi della pipeline osservativa;
- problemi della pipeline forecast;
- problemi del modello vero e proprio.

## Risultati principali

### 1. Il dataset osservato non e il problema principale

Controllo locale su `Madrid`, finestra `0.5°`, `2000-06`:

- temperatura media area circa `23.16 °C`
- precipitazione media area circa `0.397 mm`

Quindi il caso sospetto tipo "Madrid a giugno circa 8 gradi" non dipende in generale dal dataset osservato, almeno non nella pipeline corretta attuale.

### 2. Sono stati trovati due bug locali reali nella pipeline forecast

#### Bug A - Inversione scaling errata

Nel repo ufficiale `bfm-model`, la trasformazione `direction=\"original\"` del modulo scaler usa la formula sbagliata:

- divide per `(max - min)` invece di moltiplicare;
- lo stesso errore esiste anche per `standardize`, dove divide per `std` invece di moltiplicare.

Effetto pratico:

- i batch osservati già unscaled uscivano con valori fisicamente sbagliati;
- di conseguenza sembrava che il forecast fosse molto peggiore di quanto fosse davvero.

Correzione applicata nel progetto:

- helper locale `rescale_batch_correct(...)` in [bioanalyst_model_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/bioanalyst_model_utils.py)

#### Bug B - Media areale pesata calcolata con denominatore sbagliato

Nella funzione [summarize_batch_for_area](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/bioanalyst_model_utils.py) il numeratore usava tutte le celle dell'area, ma il denominatore sommava i pesi solo sulle righe di latitudine.

Effetto pratico:

- temperature e precipitazioni area-level risultavano gonfiate.

Correzione applicata:

- uso di `weights_2d` broadcastati sulla griglia intera.

### 3. Il roundtrip raw -> scaled -> original ora e corretto

Backtesting locale:

- `roundtrip_t2m_mae_kelvin = 0.0`
- `roundtrip_tp_mae_meters = 0.0`

Questo significa che il problema principale della ricostruzione dei dati e stato risolto.

## Backtesting one-step eseguito

Script:

- [forecast_backtest_one_step.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_backtest_one_step.py)

Comando eseguito:

```bash
source scripts/activate_bioanalyst_model.sh
python scripts/forecast_backtest_one_step.py --cities milano madrid --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Output:

- [forecast_backtest_one_step.csv](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/phase5_backtest_milano_madrid/forecast_backtest_one_step.csv)
- [forecast_backtest_one_step.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/phase5_backtest_milano_madrid/forecast_backtest_one_step.xlsx)
- [forecast_backtest_details.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/phase5_backtest_milano_madrid/forecast_backtest_details.json)

## Sintesi risultati

### Milano -> forecast `2020-01`

- osservato temperatura: `4.22 °C`
- predetto temperatura: `12.68 °C`
- errore assoluto temperatura: `8.45 °C`
- osservato precipitazione: `0.70 mm`
- predetto precipitazione: `3.86 mm`
- errore assoluto precipitazione: `3.16 mm`
- osservato specie proxy: `4`
- predetto specie proxy: `22`

### Madrid -> forecast `2020-01`

- osservato temperatura: `5.40 °C`
- predetto temperatura: `8.05 °C`
- errore assoluto temperatura: `2.65 °C`
- osservato precipitazione: `1.20 mm`
- predetto precipitazione: `4.33 mm`
- errore assoluto precipitazione: `3.13 mm`
- osservato specie proxy: `4`
- predetto specie proxy: `20`

## Interpretazione corretta

La situazione attuale e questa:

- la pipeline dati locale e molto piu affidabile di prima;
- il confronto forecast vs observed ora e finalmente leggibile;
- il modello `small` tende ancora a sovrastimare soprattutto la parte specie;
- anche il forecast climatico resta da validare meglio, ma non e piu corrotto dai bug locali piu gravi.

## Missing keys del checkpoint

Il caricamento del checkpoint produce ancora `14 missing keys`.

Questi includono:

- molte chiavi del tipo `encoder._latent_parameter_list.*`
- alcune chiavi del blocco `backbone.encoder_layers.0.downsample.*`

Questo significa che i missing keys non sono solo alias innocui della lista latente. Quindi il caricamento con `strict=False` e accettabile come test tecnico, ma resta un punto da approfondire se vogliamo massimizzare fedelta e performance.

## Conclusione operativa

Fase 5 ha chiarito tre cose:

1. i valori assurdi iniziali non erano dovuti solo al modello;
2. il grosso del problema veniva da bug locali di unscale e aggregazione;
3. una volta corretti questi bug, il modello resta ancora imperfetto e va validato seriamente prima di entrare nella UI come forecast utente.

## Prossimi step consigliati

1. estendere il backtesting ad almeno 5-10 città europee;
2. provare più finestre temporali, non solo `2019 -> 2020-01`;
3. capire l'impatto dei `missing_keys` residui;
4. confrontare `small` e `large` solo dopo una baseline solida del `small`;
5. tenere il forecast fuori dalla UI finale o marcarlo come `beta` finché la validazione non è convincente.
