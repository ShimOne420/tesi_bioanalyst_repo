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
- `agriculture` viene valorizzato dai CSV europei `Agriculture`, `Arable`, `Cropland`
- `forest` viene valorizzato dal CSV europeo `Forest`
- `vegetation` viene valorizzato dal CSV BioCube `Land/Europe_ndvi_monthly_un_025.csv` se presente; se non presente, usa una proxy dichiarata da `lai_hv + lai_lv`
- `redlist`, `misc` restano ancora placeholder a zero

Se manca il CSV NDVI, il fallback su `data_stream-moda.nc` non va descritto come `NDVI` osservato puro: in quel caso e una proxy tecnica da validare.

Il runner supporta due modalita di input:

- `--input-mode clean`: lascia `vegetation`, `agriculture` e `forest` a zero. Serve per capire se gli input extra stanno peggiorando o migliorando il forecast.
- `--input-mode all`: usa tutti i gruppi disponibili e mappati. E la modalita predefinita dei comandi esistenti.

## 1. Cosa sono questi file

### Manifest JSON

Il manifest dice:

- area selezionata
- mesi usati in input
- mese forecastato
- checkpoint usato
- input mode usato (`clean` o `all`)
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

Per aprire il contenuto originale del `.pt` in Excel:

```bash
python scripts/export_native_output.py --run-dir outputs/model_forecast/NOME_RUN --batch-kind prediction --group climate --variable t2m
```

Se vuoi fare run + export completo con un solo comando, usa `run.py` con:

```bash
python scripts/run.py --label Europe_native_large_all_2019_06 --min-lat 32.0 --max-lat 72.0 --min-lon -25.0 --max-lon 45.0 --start 2019-04-01 --end 2019-05-01 --checkpoint large --device cuda --input-mode all --group climate --variable t2m --export-native-full --export-native-group-csvs --no-history
```

Il workbook creato contiene:

- `run_info`: file letto, timestamp, griglia, checkpoint e input mode
- `groups`: gruppi BioAnalyst e variabili disponibili
- `variables`: tutte le variabili native con shape, dtype e statistiche
- `selected_variable`: valori cella-per-cella della variabile scelta
- `coordinates`: coordinate complete della griglia europea
- `manifest`: manifest del run in formato tabellare

Se serve esportare anche un CSV per ogni gruppo:

```bash
python scripts/export_native_output.py --run-dir outputs/model_forecast/NOME_RUN --batch-kind prediction --group climate --variable t2m --export-group-csvs
```

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
