# Setup Windows Con GPU NVIDIA

Questa guida serve per portare il ramo `forecast-bioanalyst-native` su una macchina Windows con GPU NVIDIA.

L'obiettivo e semplice:

1. preparare l'ambiente
2. clonare il repository
3. collegare `bfm-model`
4. configurare i path locali
5. lanciare il primo run nativo
6. leggere e visualizzare gli output del modello
7. lanciare il benchmark nativo multi-caso

## 1. Cosa installare prima

Sul computer Windows servono:

- `Git`
- `Python 3.11`
- `Visual Studio Code`
- driver NVIDIA funzionanti
- una build `PyTorch` con supporto `CUDA`

## 2. Clonare il repository

Apri `PowerShell` nella cartella dove vuoi tenere il progetto e lancia:

```powershell
git clone <URL_DEL_TUO_REPO> tesi_bioanalyst_repo
cd tesi_bioanalyst_repo
git checkout forecast-bioanalyst-native
```

## 3. Clonare il repository ufficiale del modello

Dentro il progetto crea la cartella `external` e clona `bfm-model`:

```powershell
mkdir external
git clone https://github.com/BioDT/bfm-model.git external/bfm-model
```

Il ramo native si aspetta proprio questa struttura:

```text
tesi_bioanalyst_repo/
  external/
    bfm-model/
```

## 4. Creare l'ambiente Python

Sempre nella root del progetto:

```powershell
py -3.11 -m venv .venv-bioanalyst
.\.venv-bioanalyst\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

## 5. Installare PyTorch con CUDA

Qui devi usare una build compatibile con la macchina.

Esempio tipico:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

Se sulla macchina universitaria e disponibile un'altra versione CUDA, usa il comando coerente con quella versione.

## 6. Installare le dipendenze del progetto

```powershell
pip install -r requirements.txt
pip install -e external/bfm-model
```

## 7. Creare il file `.env`

Parti dal template:

```powershell
Copy-Item .env.example .env
```

Poi modifica `.env` con i path reali della macchina Windows.

Esempio:

```text
BIOCUBE_DIR=D:\biomap_thesis\data\biocube
BIOANALYST_MODEL_DIR=D:\biomap_thesis\models\bioanalyst_pretrained
PROJECT_OUTPUT_DIR=D:\biomap_thesis\outputs
```

La regola pratica e questa:

- `BIOCUBE_DIR` = cartella del dataset
- `BIOANALYST_MODEL_DIR` = cartella dei checkpoint
- `PROJECT_OUTPUT_DIR` = cartella dove salvare output e grafici

## 8. Attivare l'ambiente di lavoro

Nel ramo native c'e anche uno script PowerShell dedicato:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\activate_bioanalyst_model.ps1
```

Questo script:

- attiva `.venv-bioanalyst`
- carica `.env`
- espone `external/bfm-model` al `PYTHONPATH`

## 9. Verifica iniziale

```powershell
python scripts/check_project_setup.py
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA non disponibile')"
```

Se `torch.cuda.is_available()` restituisce `True`, la macchina e pronta.

## 10. Primo run nativo

### One-step

```powershell
python scripts/forecast_native_one_step.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cuda
```

### Rollout

```powershell
python scripts/forecast_native_rollout.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cuda --steps 6
```

## 11. Come leggere gli output

### Summary del run

```powershell
python scripts/inspect_native_outputs.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\milan_2019_12_native_one_step"
```

### Mappa della temperatura

```powershell
python scripts/plot_native_maps.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\milan_2019_12_native_one_step" --group climate --variable t2m
```

### Mappa della differenza prediction - observed

```powershell
python scripts/plot_native_maps.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\milan_2019_12_native_one_step" --group climate --variable t2m --difference
```

## 12. Cosa deve risultare alla fine

Dopo il primo run devi trovare:

- `forecast_native_manifest.json`
- `forecast_native_config.yaml`
- `native_prediction_original.pt`
- `native_target_original.pt` se il target esiste
- cartella `plots` se hai creato le mappe
- `native_inspection_summary.json` se lanci `inspect_native_outputs.py`

## 13. Benchmark nativo su CUDA

Quando il primo run e leggibile, puoi lanciare direttamente il benchmark standard del ramo native:

```powershell
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_cuda_15cities_template.json --checkpoint small --device cuda
```

Questo comando esegue:

- 15 citta europee
- 4 finestre stagionali per ogni citta
- confronto `predicted vs observed` nello spazio nativo del modello

Alla fine salva:

- `native_prediction_validation.xlsx`
- `native_prediction_validation_summary.json`
- `native_prediction_validation_species_top.csv`

Solo dopo questo benchmark ha senso produrre anche l'export BIOMAP minimo:

```powershell
python scripts/native_to_biomap.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\milan_2019_12_native_one_step"
```

## 14. Errori comuni

### `CUDA non disponibile`

Cause probabili:

- driver NVIDIA non attivi
- PyTorch installato senza CUDA
- sessione non aperta sulla GPU giusta

### `bfm_model` non trovato

Controlla:

- che `external/bfm-model` esista davvero
- che `pip install -e external/bfm-model` sia stato eseguito

### `.env` non corretto

Controlla che i path in `.env` puntino davvero alle cartelle Windows corrette.

## 15. Ordine di lavoro consigliato

1. setup ambiente
2. check CUDA
3. one-step nativo
4. inspect output
5. plot delle mappe
6. benchmark nativo multi-caso
7. rollout nativo su pochi casi campione
8. solo dopo adapter BIOMAP
