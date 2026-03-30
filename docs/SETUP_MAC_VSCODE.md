# Setup Mac + VS Code + Archivio

## Architettura scelta

Per questo progetto usiamo una struttura stabile:

- `repo + codice + venv` sul Mac
- `dataset + modelli + output pesanti` su `Archivio`

## Percorsi scelti

### Repository locale

`/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo`

### Storage su disco esterno

`/Volumes/Archivio/biomap_thesis`

Con sottocartelle:

- `data/biocube`
- `models/bioanalyst_pretrained`
- `outputs`

## Perche questa scelta e corretta

- `VS Code` lavora meglio su disco locale
- il `venv` e piu stabile su disco locale
- `GitHub` funziona meglio su un repo locale
- i dati pesanti restano fuori dal Mac

## Come aprire il progetto in VS Code

1. apri `Visual Studio Code`
2. fai `File -> Open Folder`
3. seleziona:

`/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo`

4. apri il terminale integrato
5. attiva l'ambiente:

```bash
source .venv/bin/activate
```

Se tutto e corretto, vedrai `(.venv)` nel terminale.

## Come selezionare l'interprete Python

In VS Code:

1. `Cmd + Shift + P`
2. cerca `Python: Select Interpreter`
3. scegli:

`.../TCBiomap/tesi_bioanalyst_repo/.venv/bin/python`

## Come verificare che l'ambiente funziona

Nel terminale integrato:

```bash
python --version
python -c "import pandas, numpy, xarray, pyarrow, matplotlib, seaborn, openpyxl, dotenv; print('OK')"
```

## Come funzionano i file di configurazione

### `.env`

Contiene i percorsi locali dei dati e dei modelli.

Attualmente punta a:

- `BIOCUBE_DIR=/Volumes/Archivio/biomap_thesis/data/biocube`
- `BIOANALYST_MODEL_DIR=/Volumes/Archivio/biomap_thesis/models/bioanalyst_pretrained`
- `PROJECT_OUTPUT_DIR=/Volumes/Archivio/biomap_thesis/outputs`

### `.env.example`

E la versione condivisibile su GitHub.

Ogni collaboratore puo copiare `.env.example` in `.env` e cambiare i path sul proprio computer.

### `.gitignore`

Evita di caricare su GitHub:

- `.venv`
- `.env`
- dati pesanti
- modelli
- output grandi

## Come lavorare con altre persone

Il flusso corretto e:

1. il repo va su `GitHub`
2. ogni persona clona il repo
3. ogni persona crea il proprio `.env`
4. ogni persona punta il proprio `.env` ai propri dati locali

In questo modo:

- il codice e condiviso
- i dati non vengono duplicati su GitHub
- i path non sono hardcoded

## Cosa fare se Archivio non e montato

Se il disco esterno non e montato:

- il codice continua a esistere sul Mac
- il repo continua a funzionare
- ma gli script che leggono i dati non troveranno `BioCube`

Quindi, prima di lavorare sui dati, controlla sempre che:

`/Volumes/Archivio`

esista davvero.

## Nota pratica

Se in futuro vorrai aprire il progetto da terminale con `code .`, devi prima attivare il comando `code` da VS Code.

In VS Code:

1. `Cmd + Shift + P`
2. cerca `Shell Command: Install 'code' command in PATH`
