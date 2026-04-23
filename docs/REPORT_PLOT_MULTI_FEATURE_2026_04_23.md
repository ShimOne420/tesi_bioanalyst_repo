# Report operativo - Plot multi-feature BioAnalyst

Data: 2026-04-23

## Obiettivo dello step

Questo step implementa solo la generazione automatica dei plot PNG per le feature BioAnalyst piu utili a BIOMAP.

Non sono stati implementati in questo step:

- aggiornamento del workbook finale `BIOMAP_FINAL_FEATURE_ANALYSIS_NATIVE_BIOANALYST.xlsx`;
- nuovi fogli Excel;
- export multi-feature CSV/XLSX;
- modifiche alla pipeline osservativa;
- modifiche al front-end.

L'obiettivo era aggiungere, per ogni run nativo, tre immagini per ogni variabile:

- prediction;
- observed;
- difference.

## Variabili plottate

Le feature aggiunte sono:

| Cartella output | Gruppo BioAnalyst | Variabile | Significato BIOMAP |
|---|---|---|---|
| `temperature` | `climate` | `t2m` | temperatura / stress termico |
| `ndvi` | `vegetation` | `NDVI` | condizione vegetazionale |
| `swvl1` | `edaphic` | `swvl1` | umidita del suolo superficiale |
| `swvl2` | `edaphic` | `swvl2` | umidita del suolo piu profonda |
| `cropland` | `agriculture` | `Cropland` | pressione agricola/cropland |
| `precipitation` | `climate` | `tp` | precipitazione / stress idrico |

Nota: `sxvl2` viene trattato come refuso di `swvl2`.

## Struttura degli output

Ogni nuovo run crea una cartella:

```text
run_dir/plots/reliable_features/
```

All'interno vengono create sottocartelle per indicatore.

### Temperatura

```text
run_dir/plots/reliable_features/temperature/t2m_prediction.png
run_dir/plots/reliable_features/temperature/t2m_observed.png
run_dir/plots/reliable_features/temperature/t2m_difference.png
```

### NDVI

```text
run_dir/plots/reliable_features/ndvi/ndvi_prediction.png
run_dir/plots/reliable_features/ndvi/ndvi_observed.png
run_dir/plots/reliable_features/ndvi/ndvi_difference.png
```

### Soil moisture swvl1

```text
run_dir/plots/reliable_features/swvl1/swvl1_prediction.png
run_dir/plots/reliable_features/swvl1/swvl1_observed.png
run_dir/plots/reliable_features/swvl1/swvl1_difference.png
```

### Soil moisture swvl2

```text
run_dir/plots/reliable_features/swvl2/swvl2_prediction.png
run_dir/plots/reliable_features/swvl2/swvl2_observed.png
run_dir/plots/reliable_features/swvl2/swvl2_difference.png
```

### Cropland

```text
run_dir/plots/reliable_features/cropland/cropland_prediction.png
run_dir/plots/reliable_features/cropland/cropland_observed.png
run_dir/plots/reliable_features/cropland/cropland_difference.png
```

### Precipitazione

```text
run_dir/plots/reliable_features/precipitation/tp_prediction.png
run_dir/plots/reliable_features/precipitation/tp_observed.png
run_dir/plots/reliable_features/precipitation/tp_difference.png
```

Totale atteso se il run contiene anche il target observed:

```text
6 variabili x 3 mappe = 18 PNG
```

Se il run viene lanciato con `--no-compare-observed`, saranno disponibili solo le mappe `prediction`.

## Modifiche tecniche effettuate

File modificato:

```text
scripts/run.py
```

Sono state aggiunte tre parti:

1. `RELIABLE_PLOT_FEATURES`

   Registry locale delle sei variabili da plottare automaticamente.

2. `plot_map(..., cmap=...)`

   La funzione di plot ora accetta una colormap opzionale. Il comportamento precedente resta compatibile perche il default e `coolwarm`.

3. `export_reliable_feature_plots(...)`

   Nuova funzione che:

   - legge le mappe dal batch predetto;
   - applica alla prediction l'allineamento spaziale dichiarato nel manifest;
   - legge le mappe observed se disponibili;
   - salva prediction, observed e difference per ogni feature;
   - registra eventuali feature mancanti in `missing_features`;
   - restituisce i path dei PNG dentro il JSON finale stampato da `run.py`.

La funzione viene chiamata nella fase `[4/4] Esporto PNG e matrice Excel`, subito dopo l'export storico della variabile selezionata con `--group` e `--variable`.

## Cosa non e stato toccato

Non sono stati toccati:

- workbook finale BIOMAP;
- script di analisi annuale;
- script di sintesi finale;
- front-end;
- backend API;
- pipeline osservativa;
- export CSV/XLSX multi-feature.

Quindi, per ora, questa modifica riguarda solo i plot PNG prodotti da un nuovo run.

## Chiarimento sui fogli Excel proposti in precedenza

I fogli nominati in precedenza non sono stati aggiunti ora.

Il loro significato era:

- `Latest_Run`: riepilogo solo dell'ultimo run eseguito.
- `Reliable_Feature_Runs`: tabella cumulativa con una riga per ogni run e ogni feature affidabile.
- `Reliable_Feature_Area`: metriche aggregate sull'area selezionata.
- `Reliable_Feature_Files`: indice dei file prodotti, inclusi i path ai PNG.
- `City_Area_Index`: indice delle aree/citta analizzate, utile per recuperare storico e confronti.

Questi fogli saranno utili quando verra implementato l'aggiornamento automatico del workbook finale, ma non fanno parte di questo primo step.

## Come verificare

Dopo la modifica e stata verificata la sintassi di `scripts/run.py` con:

```bash
/opt/anaconda3/bin/python -m py_compile scripts/run.py
```

La verifica completa con un nuovo forecast va fatta nell'ambiente BioAnalyst completo, perche l'ambiente macOS corrente non contiene tutti i pacchetti runtime del progetto (`omegaconf`, `hydra`, ecc.).

Dopo un nuovo run, controllare che esista:

```text
outputs/.../nome_run/plots/reliable_features/
```

E che contenga le sottocartelle:

```text
temperature/
ndvi/
swvl1/
swvl2/
cropland/
precipitation/
```

Comando PowerShell utile su Windows:

```powershell
Get-ChildItem outputs\model_forecast\<nome_run>\plots\reliable_features -Recurse -File
```

Comando macOS/Linux:

```bash
find outputs/local_preview/model_forecast/<nome_run>/plots/reliable_features -type f
```

## Prossimi step consigliati

1. Eseguire un run di test e verificare che siano creati tutti i 18 PNG.
2. Controllare visivamente che prediction, observed e difference siano orientate correttamente.
3. Verificare che `t2m`, `NDVI`, `swvl1`, `swvl2`, `Cropland` e `tp` abbiano scale cromatiche leggibili.
4. Solo dopo passare al secondo step: export multi-feature CSV/XLSX.
5. Solo dopo ancora passare al terzo step: aggiornamento automatico del workbook finale unico.
