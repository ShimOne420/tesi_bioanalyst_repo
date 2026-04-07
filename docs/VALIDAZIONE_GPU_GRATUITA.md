# Validazione GPU Gratuita

Questo documento spiega come usare una GPU gratuita per validare il forecast di `temperatura` e `precipitazione` con il codice gia presente nel progetto.

Per chi preferisce una procedura guidata a celle, e disponibile anche il notebook:

- [02_colab_gpu_validation.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/02_colab_gpu_validation.ipynb)

## Raccomandazione principale

La scelta migliore oggi è:

- `Google Colab` come ambiente GPU gratuito principale

Perché:

- è nativamente notebook-based;
- si integra bene con Python e con il progetto attuale;
- il repo ufficiale di BioAnalyst è già pensato per `cuda` come setup principale;
- noi abbiamo già corretto il progetto per supportare `--device cuda`.

## Cosa dice la documentazione ufficiale

Dal lato `BioAnalyst`:

- training ed evaluation ufficiali sono orientati a `cuda`
- il file `train_config.yaml` usa `accelerator: cuda`
- l'evaluation usa `test_device: "cuda:0"`

Dal lato `Colab`:

- la FAQ ufficiale dice che nella versione gratuita l'accesso a risorse costose come le GPU è `estremamente limitato`
- quindi la GPU gratuita esiste, ma non è garantita né illimitata

Fonte:

- [FAQ Google Colab](https://research.google.com/colaboratory/faq.html)

## Perché non CPU come strada principale

Su CPU:

- il modello gira;
- i test piccoli si possono fare;
- ma la validazione seria su molte città e molti mesi è troppo lenta.

Quindi la CPU va bene per:

- smoke test
- debug
- controlli veloci

La GPU va usata per:

- validazione clima
- rollout multi-step
- confronto sistematico tra città e periodi

## Bug corretto nel progetto

Il progetto adesso supporta davvero CUDA.

Prima:

- `--device auto` sceglieva solo `mps` o `cpu`
- quindi su una GPU NVIDIA non avrebbe usato `cuda`

Ora:

- `--device cuda` è supportato
- `--device auto` preferisce `cuda`, poi `mps`, poi `cpu`

## Come preparare il subset minimo da portare su Colab

Per non spostare tutto BioCube, usa questo script:

- [prepare_colab_validation_subset.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/prepare_colab_validation_subset.py)

Comando locale:

```bash
cd /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo
source scripts/activate_bioanalyst_model.sh
python scripts/prepare_colab_validation_subset.py --target-dir /percorso/del/tuo/staging_colab --clean
```

Questo copia:

- i file minimi BioCube richiesti dal forecast
- il checkpoint `small`
- una cartella `outputs`
- un `manifest.json`

## Setup consigliato su Colab

### 1. Clona il repository e il repo ufficiale del modello

```bash
!git clone https://github.com/ShimOne420/tesi_bioanalyst_repo.git /content/tesi_bioanalyst_repo
%cd tesi_bioanalyst_repo
!mkdir -p /content/tesi_bioanalyst_repo/external
!git clone https://github.com/BioDT/bfm-model.git /content/tesi_bioanalyst_repo/external/bfm-model
```

### 2. Installa le dipendenze

```bash
!pip install -r requirements.txt
!cd external/bfm-model && pip install -e .
```

### 3. Monta Google Drive

```python
from google.colab import drive
drive.mount('/content/drive')
```

### 4. Imposta i path del subset esportato

```python
import os
os.environ["BIOCUBE_DIR"] = "/content/drive/MyDrive/biomap_validation_subset/biocube"
os.environ["BIOANALYST_MODEL_DIR"] = "/content/drive/MyDrive/biomap_validation_subset/models"
os.environ["PROJECT_OUTPUT_DIR"] = "/content/drive/MyDrive/biomap_validation_subset/outputs"
```

### 5. Esegui la validazione clima

Test rapido 2019:

```bash
!python scripts/forecast_validate_climate.py --forecast-start 2019-01-01 --forecast-end 2019-12-01 --month-stride 1 --checkpoint small --device cuda
```

Test più ampio 2000–2020, alleggerito:

```bash
!python scripts/forecast_validate_climate.py --forecast-start 2000-03-01 --forecast-end 2020-12-01 --month-stride 3 --checkpoint small --device cuda
```

## Strategia consigliata di validazione

Ordine suggerito:

1. test 2019 su set core di città
2. test 2000–2020 con `month-stride 3`
3. solo se il clima è ragionevole, passare a specie
4. solo dopo valutare `large`

## Dove leggere i risultati

I file principali saranno:

- `forecast_validation_climate_cases.xlsx`
- `forecast_validation_climate_city_summary.xlsx`
- `forecast_validation_climate_summary.json`

Dentro la cartella:

- `PROJECT_OUTPUT_DIR`

## Nota finale

Se su Colab non ottieni la GPU gratuita in quel momento:

- non è un problema del progetto;
- è un limite dinamico della piattaforma gratuita.

In quel caso:

- riprovi più tardi
- oppure usi CPU solo per test piccoli
- ma la validazione ufficiale del forecast clima conviene farla su GPU
