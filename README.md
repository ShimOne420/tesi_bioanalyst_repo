# Tesi BioAnalyst

Questo repository contiene il workspace operativo della tesi.

## Obiettivo della fase corrente

In questa prima fase il progetto serve a:

- organizzare il lavoro in modo pulito;
- usare `BioCube` e `BioAnalyst` in locale;
- calcolare tre indicatori minimi:
  - `Numero di specie`
  - `Temperatura media`
  - `Precipitazioni medie`

## Struttura del progetto

- `README.md`
  Documento principale del progetto. Spiega obiettivo, struttura e uso del workspace.

- `requirements.txt`
  Elenco minimo delle librerie Python da installare nel `venv`.

- `.gitignore`
  Dice a Git quali file non devono essere caricati su GitHub, per esempio `.venv`, dati pesanti, modelli e output.

- `.env.example`
  File esempio per definire i percorsi locali del dataset e dei modelli.

- `.vscode/`
  Configurazioni utili per lavorare in `Visual Studio Code`.

- `docs/`
  Documentazione di supporto. Qui finiscono note tecniche, struttura del progetto, decisioni metodologiche.

- `notebooks/`
  Notebook Jupyter esplorativi. Useremo questa cartella per leggere i dati e fare i primi test sugli indicatori.

- `scripts/`
  Script Python riusabili. Qui metteremo codice piu stabile del notebook.

- `data/`
  Cartella puntatore ai dati. Non ci metteremo tutto il dataset su Git, ma potra contenere piccoli file o note.

- `models/`
  Cartella per i pesi del modello o riferimenti ai modelli locali.

- `outputs/`
  Cartella per risultati, CSV finali, grafici, tabelle ed esportazioni.

## Come usare il progetto in VS Code

1. Apri `Visual Studio Code`
2. Fai `File -> Open Folder`
3. Seleziona la cartella principale del progetto
4. Apri il terminale integrato con `Terminal -> New Terminal`
5. Attiva l'ambiente Python

Su Mac:

```bash
source .venv/bin/activate
```

Quando l'ambiente e attivo vedrai `(.venv)` all'inizio del terminale.

Alternativa consigliata per questo progetto:

```bash
source scripts/activate_project.sh
```

Questo comando:

- attiva `.venv`
- carica le variabili da `.env`
- prepara i path di dataset, modelli e output

## Come installare le dipendenze

Con ambiente attivo:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

## Comando utile per BioCube

Per pianificare o scaricare `BioCube` usando automaticamente i path del progetto:

```bash
python scripts/biocube_download.py
```

Per il download reale:

```bash
python scripts/biocube_download.py --download
```

## Regola di collaborazione

Su `GitHub` vanno:

- codice
- notebook
- documentazione
- script
- file di configurazione
- output piccoli

Su `GitHub` non vanno:

- dataset pesanti
- pesi del modello
- cartella `.venv`
- output grandi

## Variabili locali

I percorsi locali vanno definiti in un file `.env` creato a partire da `.env.example`.

Esempio:

```bash
BIOCUBE_DIR=/Volumes/Archivio/biomap_thesis/data/biocube
BIOANALYST_MODEL_DIR=/Volumes/Archivio/biomap_thesis/models/bioanalyst_pretrained
PROJECT_OUTPUT_DIR=/Volumes/Archivio/biomap_thesis/outputs
```

## Primo obiettivo operativo

Il primo obiettivo pratico del progetto e:

1. creare l'ambiente;
2. verificare i percorsi;
3. scaricare dataset e modello;
4. leggere le variabili giuste;
5. calcolare i 3 indicatori minimi.
