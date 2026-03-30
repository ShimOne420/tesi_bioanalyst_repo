# Step 02 - Setup dataset e primi controlli

## Obiettivo

Il prossimo obiettivo non e ancora calcolare gli indicatori.

Prima dobbiamo:

1. verificare i percorsi locali;
2. controllare che `Archivio` sia montato;
3. preparare la cartella `BioCube`;
4. verificare come scaricare dataset e modello;
5. creare un primo notebook o script di test.

## Cosa significa chiudere bene questo step

Questo step e concluso bene se ottieni:

- `BIOCUBE_DIR` corretto
- cartella dataset esistente
- cartella modello esistente
- conferma del metodo di download
- un controllo automatico che dica se i path sono pronti

## Percorsi attesi

- `BIOCUBE_DIR=/Volumes/Archivio/biomap_thesis/data/biocube`
- `BIOANALYST_MODEL_DIR=/Volumes/Archivio/biomap_thesis/models/bioanalyst_pretrained`
- `PROJECT_OUTPUT_DIR=/Volumes/Archivio/biomap_thesis/outputs`

## Ordine dei task

1. attivare il progetto:

```bash
source scripts/activate_project.sh
```

2. controllare che `Archivio` sia montato
3. controllare che i path di `.env` esistano
4. verificare i file locali gia presenti nel repository generale della tesi
5. decidere come scaricare `BioCube`
6. decidere come scaricare i pesi del modello

## Comando consigliato per il dry run

Con ambiente attivo:

```bash
python scripts/biocube_download.py
```

Questo comando:

- legge `BIOCUBE_DIR` da `.env`
- usa lo script ufficiale gia presente nel progetto
- evita errori di path nel terminale

## Comando consigliato per il download reale

```bash
python scripts/biocube_download.py --download
```

Se in futuro vuoi scaricare solo una parte del dataset:

```bash
python scripts/biocube_download.py --download --include "Species/*" --include "Copernicus/*"
```

## Nota importante

Per questo step non dobbiamo ancora:

- fare training
- fare fine-tuning
- scrivere pipeline complesse
- scaricare tutti i dataset aggiuntivi

## Output atteso

Alla fine di questo step dobbiamo avere:

- `script` di controllo dei path
- `notebook` iniziale per ispezione
- piano chiaro di download di `BioCube`
- piano chiaro di download del modello
