# Output Nativi BioAnalyst

Questo ramo non produce ancora indicatori finali BIOMAP.

Per adesso gli output del modello sono artefatti nativi di BioAnalyst:

- `forecast_native_manifest.json`
- `forecast_native_config.yaml`
- `native_prediction_original.pt`
- `native_target_original.pt` se il mese osservato esiste
- `native_rollout_batches/step_XX.pt` nei run rollout

## 0. Quali gruppi sono davvero reali oggi

Nel ramo native attuale:

- `surface`, `edaphic`, `atmospheric`, `climate`, `species` sono alimentati da dati reali del BioCube locale
- `land` viene valorizzato dal canale reale `lsm`
- `vegetation`, `agriculture`, `forest`, `redlist`, `misc` restano ancora placeholder a zero

Nel BioCube locale e disponibile anche `era5-land-vegetation`, ma per ora non facciamo una mappatura forzata verso `NDVI`, `Forest` o `Agriculture`, per non introdurre canali semanticamente sbagliati nel batch.

## 1. Cosa sono questi file

### Manifest JSON

Il manifest dice:

- area selezionata
- mesi usati in input
- mese forecastato
- checkpoint usato
- device usato
- path dei file `.pt`

E il primo file da aprire per capire un run.

### Batch `.pt`

I file `.pt` non sono una tabella finale.

Contengono il batch del modello, cioe:

- coordinate della griglia
- timestamp
- lead time
- gruppi di variabili
- mappe 2D o stack temporali sulle celle del dominio

Nel nostro caso, i gruppi principali che interessano subito sono:

- `climate`
- `species`
- `surface`

Esempi utili:

- `climate.t2m`
- `climate.tp`
- variabili specie nel gruppo `species`

## 2. Dove si vedono

Ogni run viene salvato in una cartella sotto:

- `outputs/.../model_forecast/...`

Esempio reale:

- [run one-step Milano](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo_native/outputs/local_preview/model_forecast/milan_2019_12_native_one_step)

## 3. Come leggere un output nativo

Attiva prima l'ambiente:

```bash
source scripts/activate_bioanalyst_model.sh
```

Poi lancia:

```bash
python scripts/inspect_native_outputs.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step
```

Questo comando stampa:

- metadati del run
- shape della griglia
- timestamp del batch
- gruppi presenti
- quali gruppi sono reali e quali placeholder
- sanity checks su path, timestamp e lead time
- statistiche della variabile scelta
- confronto prediction vs observed per `t2m` e `tp` se il target esiste
- riepilogo di gruppo per il gruppo scelto

Salva anche:

- `native_inspection_summary.json`

## 4. Come vedere le mappe

### Temperatura predetta

```bash
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step --group climate --variable t2m
```

### Temperatura osservata

```bash
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step --batch-kind observed --group climate --variable t2m
```

### Differenza prediction - observed

```bash
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step --group climate --variable t2m --difference
```

### Pioggia

```bash
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step --group climate --variable tp
python scripts/plot_native_maps.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step --group climate --variable tp --difference
```

I file `.png` vengono salvati in:

- `run_dir/plots`

Se `prediction` e `observed` sembrano uguali:

- la differenza puo uscire quasi tutta grigia perche il delta e vicino a zero
- il rettangolo tratteggiato nero indica solo l'area selezionata dentro la mappa completa del dominio europeo
- questo da solo non basta per dire che il forecast e valido: per quello serve il benchmark multi-caso

## 5. Come capire se il forecast e plausibile

Per ora usiamo un controllo semplice in due livelli.

### Controllo tecnico

Il run deve:

- partire senza errori
- produrre manifest e `.pt`
- avere timestamp coerenti
- avere gruppi variabili coerenti con BioAnalyst

### Controllo numerico preliminare

Con `inspect_native_outputs.py` guardiamo:

- media predetta vs media osservata su `t2m`
- media predetta vs media osservata su `tp`
- `bias`
- `MAE`
- `RMSE`
- sanity checks prediction vs observed

Per un benchmark nativo su piu casi:

```bash
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_local.json --checkpoint small --device cpu
```

Questo salva:

- `native_prediction_validation.xlsx`
- `native_prediction_validation_cases.csv`
- `native_prediction_validation_species_top.csv`
- `native_prediction_validation_summary.json`

Questa non e ancora la validazione finale del progetto BIOMAP.

E la prima verifica che il modello nativo stia producendo output sensati prima di qualsiasi adapter successivo.

## 6. Cosa fare dopo

La sequenza corretta e:

1. far uscire output nativi corretti
2. ispezionarli e visualizzarli
3. validare prediction vs observed nello spazio nativo
4. solo dopo progettare l'adattamento agli indicatori BIOMAP

## 7. Adapter BIOMAP minimale

Nel ramo attuale esiste gia uno strato molto leggero per ottenere i tre indicatori area-level in formato leggibile.

Questo strato non sostituisce la validazione nativa del modello. Viene dopo.

```bash
python scripts/native_to_biomap.py --run-dir outputs/local_preview/model_forecast/milan_2019_12_native_one_step
```

Questo script legge i batch nativi e salva in `run_dir/biomap`:

- `biomap_area_summary.xlsx` nei run one-step
- `biomap_rollout_summary.xlsx` nei run rollout
- relativo `.csv`
- relativo `.json`

Per ora l'output BIOMAP minimo contiene:

- `temperature_mean_area_c`
- `precipitation_mean_area_mm`
- `species_count_area_proxy`

La parte species resta ancora una `proxy`, non una validazione finale scientifica del forecast specie.
