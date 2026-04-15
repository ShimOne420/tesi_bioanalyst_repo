# Workflow Universita Windows CUDA

Questa guida serve per usare il computer Windows dell'universita da remoto e lanciare BioAnalyst native-first con GPU NVIDIA/CUDA.

L'obiettivo e:

1. scaricare il progetto sulla macchina universitaria;
2. creare l'ambiente Python corretto;
3. scaricare BioCube e i pesi BioAnalyst direttamente sulla macchina;
4. verificare CUDA;
5. lanciare un primo run nativo;
6. lanciare il benchmark nativo multi-caso.

## 0. Prima Di Iniziare

Apri una sessione remota sul computer dell'universita e usa `PowerShell`.

Scegli una cartella dati con abbastanza spazio, per esempio:

```powershell
D:\biomap_thesis
```

Se `D:` non esiste o non ha spazio, usa un altro disco locale della macchina universitaria.

## 1. Crea Le Cartelle Di Lavoro

```powershell
mkdir D:\biomap_thesis
mkdir D:\biomap_thesis\data
mkdir D:\biomap_thesis\models
mkdir D:\biomap_thesis\models\bioanalyst_pretrained
mkdir D:\biomap_thesis\outputs
mkdir D:\biomap_thesis\code
cd D:\biomap_thesis\code
```

## 2. Clona Il Progetto

Sostituisci `<URL_DEL_REPO_GITHUB>` con l'URL reale del repository.

```powershell
git clone <URL_DEL_REPO_GITHUB> tesi_bioanalyst_repo
cd tesi_bioanalyst_repo
git checkout forecast-bioanalyst-native
```

Controlla il branch:

```powershell
git branch --show-current
```

Deve stampare:

```text
forecast-bioanalyst-native
```

## 3. Clona Il Repo Ufficiale BioAnalyst

```powershell
mkdir external
git clone https://github.com/BioDT/bfm-model.git external/bfm-model
```

La struttura deve essere:

```text
tesi_bioanalyst_repo
  external
    bfm-model
```

## 4. Crea L'Ambiente Python

Usiamo Python `3.11`.

```powershell
py -3.11 -m venv .venv-bioanalyst
.\.venv-bioanalyst\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
```

Se PowerShell blocca l'attivazione del virtualenv:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv-bioanalyst\Scripts\Activate.ps1
```

## 5. Installa PyTorch Con CUDA

Comando consigliato:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

Verifica CUDA:

```powershell
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA non disponibile')"
```

Se stampa `True` e il nome della GPU NVIDIA, va bene.

## 6. Installa Le Dipendenze Del Progetto

```powershell
pip install -r requirements.txt
pip install -e external/bfm-model
```

## 7. Crea Il File `.env`

Crea il file:

```powershell
Copy-Item .env.example .env
notepad .env
```

Sostituisci tutto con:

```text
BIOCUBE_DIR=D:\biomap_thesis\data\biocube
BIOANALYST_MODEL_DIR=D:\biomap_thesis\models\bioanalyst_pretrained
PROJECT_OUTPUT_DIR=D:\biomap_thesis\outputs
MPLCONFIGDIR=D:\biomap_thesis\outputs\matplotlib_cache
```

Salva e chiudi Notepad.

## 8. Scarica Il Dataset BioCube

Per iniziare non serve scaricare tutto BioCube. Scarichiamo il subset minimo usato dal ramo native:

```powershell
python scripts/download_biocube_minimal.py --dry-run
python scripts/download_biocube_minimal.py
```

Questo scarica:

- ERA5 surface;
- ERA5 edaphic;
- ERA5 pressure;
- ERA5 climate-energy-moisture;
- ERA5 land-vegetation, disponibile ma non ancora mappato nei canali `NDVI/Forest/Agriculture`;
- Species parquet.

Se vuoi scaricare anche modalita extra utili per il lavoro futuro su forest/restoration:

```powershell
python scripts/download_biocube_minimal.py --with-extra-modalities
```

Se invece vuoi scaricare tutto BioCube:

```powershell
python scripts/download_biocube_minimal.py --full
```

Il download completo richiede molto piu spazio e tempo.

## 9. Scarica I Pesi BioAnalyst

Per ora usa il checkpoint `small`:

```powershell
python scripts/download_bioanalyst_weights.py --checkpoint small
```

Alla fine deve comparire un file simile a:

```text
D:\biomap_thesis\models\bioanalyst_pretrained\bfm-pretrained-small.safetensors
```

## 10. Attiva L'Ambiente Del Progetto

Ogni volta che riapri PowerShell, entra nel progetto e attiva:

```powershell
cd D:\biomap_thesis\code\tesi_bioanalyst_repo
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\activate_bioanalyst_model.ps1
```

## 11. Controllo Setup

```powershell
python scripts/check_project_setup.py
python scripts/inventory_biocube.py
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CUDA non disponibile')"
```

Se `check_project_setup.py` passa e CUDA e `True`, possiamo lanciare BioAnalyst.

## 12. Primo Run Nativo Con CUDA

Parti con un solo caso:

```powershell
python scripts/forecast_native_one_step.py --city madrid --start 2019-11-01 --end 2019-12-01 --checkpoint small --device cuda
```

Output atteso:

```text
D:\biomap_thesis\outputs\model_forecast\madrid_2019_12_native_one_step
```

Dentro devi trovare:

- `forecast_native_manifest.json`;
- `forecast_native_config.yaml`;
- `native_prediction_original.pt`;
- `native_target_original.pt`, se il target osservato e disponibile.

## 13. Ispeziona Il Run

```powershell
python scripts/inspect_native_outputs.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\madrid_2019_12_native_one_step" --group climate --variable t2m
```

Questo crea:

```text
native_inspection_summary.json
```

Controlla in particolare:

- `checkpoint_diagnostics`;
- `group_source_status`;
- `native_sanity_checks`;
- `native_climate_comparison`.

## 14. Crea Le Mappe

Temperatura predetta:

```powershell
python scripts/plot_native_maps.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\madrid_2019_12_native_one_step" --group climate --variable t2m
```

Temperatura osservata:

```powershell
python scripts/plot_native_maps.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\madrid_2019_12_native_one_step" --batch-kind observed --group climate --variable t2m
```

Differenza prediction - observed:

```powershell
python scripts/plot_native_maps.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\madrid_2019_12_native_one_step" --group climate --variable t2m --difference
```

Le immagini sono in:

```text
D:\biomap_thesis\outputs\model_forecast\madrid_2019_12_native_one_step\plots
```

## 15. Benchmark Nativo Piccolo

Prima del benchmark grande, fai un test piccolo:

```powershell
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_local.json --checkpoint small --device cuda --output-label native_prediction_validation_cuda_smoke
```

Output:

```text
D:\biomap_thesis\outputs\model_forecast\native_prediction_validation_cuda_smoke
```

File principali:

- `native_prediction_validation.xlsx`;
- `native_prediction_validation_summary.json`;
- `native_prediction_validation_cases.csv`;
- `native_prediction_validation_species_top.csv`.

## 16. Benchmark Nativo Grande

Se il test piccolo funziona, lancia il benchmark da tesi:

```powershell
python scripts/validate_native_predictions.py --cases-json data/native_validation_cases_cuda_15cities_template.json --checkpoint small --device cuda --output-label native_prediction_validation_cuda_15cities_4seasons
```

Questo esegue:

- 15 citta europee;
- 4 finestre stagionali;
- confronto `predicted vs observed` nello spazio nativo BioAnalyst;
- metriche su temperatura, precipitazione e species native proxy;
- sanity checks per evitare falsi forecast perfetti.

## 17. Rollout Su Pochi Casi

Dopo il benchmark one-step, prova un rollout solo su pochi casi:

```powershell
python scripts/forecast_native_rollout.py --city madrid --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cuda --steps 6
```

Poi ispeziona:

```powershell
python scripts/inspect_native_outputs.py --run-dir "$env:PROJECT_OUTPUT_DIR\model_forecast\madrid_2019_12_native_rollout_6m" --batch-kind rollout --rollout-step 6 --group climate --variable t2m
```

## 18. Cosa Mandare Al Team

Dopo i test CUDA, condividi questi file:

- `native_prediction_validation.xlsx`;
- `native_prediction_validation_summary.json`;
- `native_prediction_validation_cases.csv`;
- qualche immagine da `plots`;
- `forecast_native_manifest.json` di almeno un run.

## 19. Errori Comuni

### CUDA non disponibile

Controlla:

```powershell
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"
```

Se `nvidia-smi` non funziona, il problema e driver/sessione GPU.

### Dataset non trovato

Controlla `.env`:

```powershell
type .env
```

Poi controlla:

```powershell
dir D:\biomap_thesis\data\biocube
```

### Checkpoint non trovato

Rilancia:

```powershell
python scripts/download_bioanalyst_weights.py --checkpoint small
```

### `bfm_model` non trovato

Rilancia:

```powershell
pip install -e external/bfm-model
```

## 20. Ordine Consigliato Finale

1. Setup ambiente.
2. Download subset BioCube.
3. Download checkpoint small.
4. `check_project_setup.py`.
5. Primo one-step CUDA.
6. Inspect + plot.
7. Benchmark piccolo.
8. Benchmark 15 citta x 4 stagioni.
9. Rollout su pochi casi.
10. Solo dopo, adapter BIOMAP.
