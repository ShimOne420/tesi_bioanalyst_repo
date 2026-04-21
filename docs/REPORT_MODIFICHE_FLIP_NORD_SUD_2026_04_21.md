# Report modifiche codice: riallineamento nord-sud prediction BioAnalyst

Data: 2026-04-21

Branch/progetto: `forecast-bioanalyst-native` / BioAnalyst Native First

## Obiettivo della modifica

Correggere in modo tracciabile il problema diagnosticato sul checkpoint `small` per la variabile `t2m`:

```text
prediction originale:
correlazione = -0.590
MAE          = 9.50 °C
RMSE         = 11.67 °C

prediction ribaltata nord-sud:
correlazione = 0.958
MAE          = 1.49 °C
RMSE         = 1.93 °C
```

La diagnosi indica che la prediction del modello e' plausibilmente orientata al contrario sull'asse latitudinale rispetto alle coordinate usate per observed, Excel e PNG.

La correzione implementata:

- applica il flip solo alla `prediction`;
- non applica nessun flip alla longitudine;
- non modifica i file `.pt` nativi originali;
- agisce solo sugli output leggibili, sulle mappe e sulle metriche di validazione;
- salva nel manifest che la correzione e' stata applicata.

## Principio metodologico

La modifica non "trucca" il risultato: corregge l'associazione tra valori predetti e coordinate geografiche.

Il file nativo:

```text
native_prediction_original.pt
```

rimane invariato.

Gli output umani:

```text
PNG
t2m_cell_matrix.xlsx
t2m_area_summary.xlsx
native full Excel/CSV
history workbook
```

usano invece la prediction riallineata alla griglia geografica.

## File modificati

### 1. `scripts/spatial_alignment.py`

Nuovo file.

Contiene le funzioni centralizzate per:

- dichiarare nel manifest la correzione applicata;
- leggere dal manifest se il flip nord-sud e' attivo;
- ribaltare la prediction sull'asse latitudinale;
- scegliere l'origine corretta dei PNG in base all'ordine delle latitudini;
- creare la tabella diagnostica `original / flip_north_south / flip_east_west / flip_both`.

Funzioni principali:

```python
build_spatial_alignment_metadata()
prediction_latitude_flip_enabled(manifest)
prediction_longitude_flip_enabled(manifest)
align_prediction_map(...)
plot_origin_for_latitudes(...)
build_alignment_diagnostic_frame(...)
```

### 2. `scripts/run.py`

Modifiche principali:

- importa le utility da `spatial_alignment.py`;
- salva nel `forecast_native_manifest.json` una sezione `spatial_alignment`;
- applica il flip nord-sud alla prediction prima di:
  - PNG prediction;
  - PNG difference;
  - Excel cella-per-cella;
  - summary metriche;
  - history workbook;
- non modifica l'observed;
- non modifica `native_prediction_original.pt`;
- aggiunge nel workbook `t2m_cell_matrix.xlsx` un nuovo foglio:

```text
alignment_diagnostic
```

Questo foglio contiene:

```text
original
flip_north_south
flip_east_west
flip_north_south_east_west
```

con metriche:

```text
correlation
MAE
RMSE
bias
predicted_mean
observed_mean
```

Inoltre `summary` e `area_summary` includono:

```text
prediction_latitude_flip_applied
prediction_longitude_flip_applied
```

### 3. `scripts/export_native_output.py`

Modifiche principali:

- legge il manifest e applica il flip nord-sud quando `batch-kind=prediction`;
- consente override manuale:

```powershell
--align-prediction-latitude
--no-align-prediction-latitude
```

- applica la correzione anche ai CSV completi di gruppo quando si usa:

```powershell
--export-group-csvs
```

- aggiunge in `run_info`:

```text
prediction_latitude_flip_applied
prediction_longitude_flip_applied
native_pt_preserved
```

### 4. `scripts/plot_native_maps.py`

Modifiche principali:

- applica il flip nord-sud alla prediction quando il manifest lo dichiara;
- non applica il flip all'observed;
- consente override manuale:

```powershell
--align-prediction-latitude
--no-align-prediction-latitude
```

- usa automaticamente `origin="upper"` quando le latitudini sono ordinate da nord a sud.

Questo evita PNG visivamente capovolti quando `latitudes[0] > latitudes[-1]`.

## Sezione aggiunta al manifest

I nuovi run prodotti da `scripts/run.py` includono:

```json
{
  "spatial_alignment": {
    "prediction_latitude_flip_applied": true,
    "prediction_longitude_flip_applied": false,
    "applies_to": "human-readable exports, plots and validation metrics",
    "native_pt_preserved": true,
    "reason": "Diagnostic on t2m small showed a north-south inversion of the predicted map against the observed target; east-west flip was worse and is not applied."
  }
}
```

## Cosa non e' stato modificato

Non sono stati modificati:

- il modello BioAnalyst;
- i pesi `small` o `large`;
- il checkpoint loading;
- il preprocessing dei dataset;
- i `.pt` nativi salvati dal modello;
- l'observed target;
- l'asse longitudinale.

La correzione e' limitata alla fase di:

```text
export
plot
validation metrics
```

## Test eseguiti

### 1. Verifica sintattica

Comando eseguito:

```bash
python3 -m py_compile scripts/spatial_alignment.py scripts/run.py scripts/export_native_output.py scripts/plot_native_maps.py
```

Risultato:

```text
OK
```

### 2. Test diagnostico su Excel small gia' prodotto

E' stato usato il file:

```text
/Users/simonemercolino/Desktop/t2m_cell_matrix_small.xlsx
```

Il test ha ricostruito le mappe `predicted` e `observed` dal foglio `full_grid` e ha verificato la funzione `build_alignment_diagnostic_frame`.

Risultato:

```text
original:
correlation = -0.589830
MAE         = 9.500521
RMSE        = 11.666782

flip_north_south:
correlation = 0.958497
MAE         = 1.491905
RMSE        = 1.934147

flip_east_west:
correlation = -0.852151
MAE         = 10.425187
RMSE        = 12.591295

flip_north_south_east_west:
correlation = 0.584704
MAE         = 5.031900
RMSE        = 5.974786
```

La funzione `align_prediction_map(...)` produce lo stesso MAE del test manuale:

```text
aligned_mae = 1.491905
```

### 3. Limite dei test locali

Non e' stato rilanciato il modello sul Mac.

Motivo:

- l'ambiente Mac locale non contiene tutto l'ambiente BioAnalyst/CUDA della macchina universitaria;
- i comandi `--help` dei runner si fermano all'import di dipendenze assenti sul Mac, come `hydra`;
- la verifica eseguita localmente e' quindi limitata a sintassi e logica di allineamento su Excel gia' generato.

Il test reale va fatto sulla macchina universitaria.

## Comando consigliato per test su macchina universitaria

Da PowerShell, dentro il repository:

```powershell
python scripts\run.py --label Europe_native_small_all_2019_06_aligned --min-lat 32.0 --max-lat 72.0 --min-lon -25.0 --max-lon 45.0 --start 2019-04-01 --end 2019-05-01 --checkpoint small --device cuda --input-mode all --group climate --variable t2m --export-native-full --export-native-group-csvs --history-xlsx outputs\model_forecast\native_lab_europe_t2m_small_2019_06_aligned.xlsx
```

Output da controllare:

```text
outputs\model_forecast\...\exports\t2m_cell_matrix.xlsx
outputs\model_forecast\...\exports\t2m_area_summary.xlsx
outputs\model_forecast\...\exports\bioanalyst_native_full_output.xlsx
outputs\model_forecast\...\forecast_native_manifest.json
```

Nel file `t2m_cell_matrix.xlsx` controllare:

```text
summary
alignment_diagnostic
full_grid
```

Il foglio `summary` dovrebbe mostrare metriche vicine al vecchio test manuale con flip:

```text
MAE circa 1.5 °C
RMSE circa 1.9 °C
correlazione positiva nel foglio alignment_diagnostic
```

## Criteri di accettazione

La modifica e' considerata corretta se:

1. `forecast_native_manifest.json` contiene `spatial_alignment`;
2. `prediction_latitude_flip_applied` e' `true`;
3. `prediction_longitude_flip_applied` e' `false`;
4. `native_prediction_original.pt` viene comunque salvato;
5. il nuovo Excel non richiede piu' flip manuale;
6. il foglio `alignment_diagnostic` conferma che il solo flip nord-sud e' lo scenario migliore;
7. il MAE nel summary e' vicino a quello del test manuale.

## Prossimi step dopo il primo test

Se il test su giugno 2019 conferma il risultato:

1. ripetere su `2019-03`, `2019-09`, `2019-12`;
2. ripetere su aree regionali: Alpi, Europa centrale, Scandinavia, Mediterraneo;
3. validare anche `tp`;
4. solo dopo passare a species/proxy biodiversita';
5. aggiornare il README operativo con la correzione stabilizzata.

## Nota importante per GitHub

Questa modifica e' codice, quindi puo' essere versionata su GitHub.

Non devono invece essere versionati:

```text
data/
outputs/
external/bioanalyst_pretrained/
.venv-bioanalyst/
```

Il repository deve contenere il codice e la documentazione; dataset, modelli, ambiente e output devono restare locali e configurabili tramite `.env`.

