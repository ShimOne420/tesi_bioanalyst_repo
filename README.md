# Tesi BioAnalyst

Questo repository contiene il workspace operativo della tesi.

Per una guida operativa piu dettagliata, con spiegazione di file, cartelle e comandi da usare in `Visual Studio Code`, vedi anche:

- [docs/README_OPERATIVO.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/README_OPERATIVO.md)

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

## Decisione metodologica da prendere

Prima di costruire la pipeline finale bisogna decidere la `unita di analisi`.

### Opzione A: Europa intera per mese

Significa questo:

- prendi ogni mese del dataset;
- per quel mese calcoli `un solo valore finale` per tutta l'Europa;
- quindi ottieni una tabella temporale del tipo:
  - `2000-01 -> temperatura media Europa`
  - `2000-01 -> precipitazione media Europa`
  - `2000-01 -> indicatore specie Europa`

Vantaggi:

- e la versione piu semplice da implementare e verificare;
- e ottima per testare che i dati siano giusti;
- permette di costruire subito una baseline metodologica.

Limiti:

- non produce mappe;
- non dice dove, nello spazio, avvengono i cambiamenti.

### Opzione B: Cella spaziale + mese

Significa questo:

- il territorio europeo viene trattato come insieme di celle geografiche;
- per ogni `cella` e per ogni `mese` calcoli il valore dell'indicatore;
- quindi ottieni una tabella molto piu ricca del tipo:
  - `latitudine, longitudine, mese, species_richness`
  - `latitudine, longitudine, mese, temperatura_media`
  - `latitudine, longitudine, mese, precipitazione_media`

Vantaggi:

- e la struttura giusta se in futuro vuoi fare mappe;
- e la base corretta per analisi spaziali, hotspot, danno/restoration.

Limiti:

- e piu pesante da gestire;
- richiede piu attenzione nel far combaciare le griglie spaziali dei dati.

### Scelta consigliata adesso

La scelta piu intelligente per questa fase e:

1. partire con `Europa intera per mese` per validare il workflow;
2. solo dopo passare a `cella + mese`, almeno su un sottoinsieme o su un'area di interesse.

Questa scelta ti evita di complicare troppo la pipeline all'inizio, ma non ti chiude la strada alle mappe in seguito.
