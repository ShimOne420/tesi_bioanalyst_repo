# Roadmap Operativa Tesi BioAnalyst

Stato documento: 2026-03-30

## Obiettivo reale della tesi

L'obiettivo della tesi non e piu addestrare un modello nuovo.

L'obiettivo adesso e:

1. prendere `BioAnalyst` cosi com'e;
2. scaricare e organizzare `dataset + codice + pesi modello`;
3. far girare il progetto in locale, preferibilmente su `hard disk esterno`;
4. senza training e senza fine-tuning, calcolare `3 indicatori diretti minimi`;
5. documentare il workflow in modo riproducibile.

I tre indicatori minimi da calcolare sono:

- `Numero di specie`
- `Temperatura media`
- `Precipitazioni medie`

## Decisione metodologica consigliata

La strada piu solida per questa tesi e:

`BioAnalyst/BioCube -> setup locale -> ispezione dati -> calcolo diretto dei 3 indicatori`

Non serve partire subito dal modello.

Per i tre indicatori minimi, in realta:

- il `dataset BioCube` e indispensabile;
- il `modello BioAnalyst` puo essere utile da installare e testare;
- ma il calcolo dei 3 indicatori non richiede per forza inferenza del modello.

Questa distinzione e importante:

- `dataset` = ti fornisce i dati da cui estrarre gli indicatori;
- `modello` = serve se vuoi fare predizione, forecasting, embedding o task downstream.

Per la tesi attuale, il cuore e il dataset.

## Risposta breve alla domanda di fattibilita

### E fattibile sul Mac locale senza training?

`Si`, per il workflow minimo.

Il workflow minimo comprende:

- scaricare il dataset;
- organizzarlo su disco esterno;
- installare il codice;
- eventualmente fare un test di esecuzione del modello o dell'esempio ufficiale;
- calcolare i 3 indicatori.

Questo non richiede per forza la macchina universitaria, a patto che tu abbia:

- spazio su disco sufficiente;
- un ambiente Python stabile;
- tempo per il preprocessing;
- pazienza nel gestire download e file grandi.

### Serve la macchina dell'universita per training o fine-tuning?

`Si, molto probabilmente si`.

Per training o fine-tuning servono quasi certamente:

- GPU dedicate;
- molta RAM;
- piu spazio disco;
- tempi di esecuzione piu lunghi;
- maggiore complessita di setup.

### Se in futuro vuoi aggiungere altri dataset per fare mappe, devi per forza trainare?

`Non sempre`.

Serve distinguere due casi:

1. `Vuoi solo creare mappe di indicatori`
   - non serve training;
   - basta allineare dataset spaziali e calcolare le variabili/indicatori.

2. `Vuoi che il modello impari da nuovi dataset e faccia nuove predizioni`
   - allora si, serve training o fine-tuning.

Quindi:

- `mappa di biodiversita da dati gia disponibili` -> puo essere fatta anche senza training;
- `modello che integra nuovi dataset e generalizza` -> richiede training.

## Fonti ufficiali da usare

### Dataset

- [BioCube su Hugging Face](https://huggingface.co/datasets/BioDT/BioCube)
- [Repository BioDT/bfm-data](https://github.com/BioDT/bfm-data)

### Modello

- [Repository BioDT/bfm-model](https://github.com/BioDT/bfm-model)
- [Pesi pre-addestrati su Hugging Face](https://huggingface.co/BioDT/bfm-pretrained)

Nota importante:

- il repository del modello mostra che il training completo e stato eseguito su cluster GPU;
- questo conferma che `training` e `inference/setup locale` non sono la stessa cosa.

## Cosa devi davvero fare adesso

La tesi va divisa in `2 livelli`.

### Livello 1 - obbligatorio

Quello che devi assolutamente chiudere:

1. setup del progetto in locale o su SSD;
2. download di dataset e codice;
3. verifica che il progetto si apra correttamente;
4. calcolo dei 3 indicatori minimi.

### Livello 2 - opzionale

Solo se il livello 1 funziona:

1. test di inferenza del modello ufficiale;
2. uso del modello per predizione o analisi aggiuntiva;
3. estensione con nuovi dataset;
4. eventuale training o fine-tuning su macchine universitarie.

## Indicatori minimi della tesi

## 1. Numero di specie

Che cosa misura:

- il numero di specie distinte osservate in una certa unita spaziale e temporale.

Dati necessari:

- `species occurrences`
- coordinate
- timestamp o periodo
- eventuale aggregazione per cella spaziale

Fonte attesa nel progetto:

- modalita `Species` di `BioCube`

## 2. Temperatura media

Che cosa misura:

- la temperatura media della cella o dell'area considerata in un certo intervallo temporale.

Dati necessari:

- variabili climatiche di temperatura
- in pratica, da verificare nel dataset scaricato:
  - `2m_temperature`
  - oppure `t2m`
  - oppure nome equivalente

Fonte attesa:

- componente climate / Copernicus / ERA5 di `BioCube`

## 3. Precipitazioni medie

Che cosa misura:

- la precipitazione media o totale media aggregata sull'intervallo scelto.

Dati necessari:

- variabile di precipitazione
- da verificare nel dataset scaricato:
  - `total_precipitation`
  - oppure `tp`
  - oppure nome equivalente

Fonte attesa:

- componente climate / Copernicus / ERA5 di `BioCube`

Nota pratica importante:

nel repository locale e gia presente un esempio di configurazione ERA5 che cita esplicitamente:

- `2m_temperature`
- `total_precipitation`

quindi la base per temperatura e pioggia e coerente con il progetto.

## Cosa NON devi fare ora

Per questa fase non devi:

- addestrare un foundation model nuovo;
- fare fine-tuning del modello;
- integrare subito molti dataset esterni;
- provare a produrre mappe complesse di classificazione del suolo;
- complicare il progetto con una pipeline troppo grande.

## Architettura di lavoro consigliata

La soluzione piu pulita e usare un `SSD esterno` o hard disk esterno.

### Perche conviene

- non saturi la memoria del Mac;
- mantieni dataset e output pesanti fuori dal computer;
- puoi spostare piu facilmente il progetto;
- separi codice e dati.

### Struttura consigliata sul disco esterno

Esempio:

```text
/Volumes/BIOMAP_SSD/
  biomap_thesis/
    code/
      bfm-model/
      bfm-data/
      tesi_biomap/
    data/
      biocube/
    models/
      bioanalyst_pretrained/
    outputs/
    notebooks/
```

### Nota sul filesystem

Se il disco esterno verra usato solo su Mac:

- preferibile `APFS`

Se vuoi compatibilita anche con Windows:

- `exFAT`

## Collaborazione

Per lavorare con un'altra persona:

- il codice va su `GitHub`;
- il dataset non va caricato su `GitHub`;
- ciascuno puo avere il dataset localmente;
- oppure una sola persona tiene il raw dataset e condivide solo output preprocessati piccoli.

Regola pratica:

- `GitHub` per codice, notebook, README, script, risultati leggeri;
- `SSD esterno` o storage dedicato per dataset e pesi modello.

## Tool gratuiti da usare

### Software base

- `Python 3.10` o `3.12` a seconda della compatibilita del repository
- `venv`, `conda` o `miniforge`
- `Git`
- `VS Code`
- `Jupyter Notebook` o `JupyterLab`

### Librerie base

- `pandas`
- `numpy`
- `xarray`
- `pyarrow`
- `matplotlib`
- `seaborn`
- `jupyter`
- `openpyxl`

### Librerie geospaziali opzionali

- `geopandas`
- `rasterio`
- `shapely`

### Tool da non considerare necessari in questa fase

- GPU cloud a pagamento
- VM cloud a pagamento
- training distribuito
- servizi enterprise

## Strategia operativa consigliata

La strategia migliore e in `3 blocchi`.

## Blocco A - Setup locale

Obiettivo:

- portare `BioAnalyst` in locale o su SSD;
- verificare che il codice si installi.

Passi:

1. scegliere il disco dove lavorare;
2. creare la struttura delle cartelle;
3. clonare i repository ufficiali;
4. creare ambiente Python;
5. installare le dipendenze;
6. scaricare i pesi del modello;
7. scaricare il dataset.

Output:

- ambiente pronto
- codice presente
- dataset presente
- pesi presenti

## Blocco B - Test minimo del progetto

Obiettivo:

- verificare che il progetto `BioAnalyst` o `bfm-model` si avvii correttamente.

Passi:

1. aprire la documentazione del repo del modello;
2. eseguire l'esempio minimo ufficiale, se disponibile;
3. verificare che almeno una predizione o un caricamento del modello funzioni.

Nota importante:

Questo blocco serve come `sanity check`.

Ma anche se l'inferenza fosse lenta o problematica, il calcolo dei 3 indicatori puo comunque procedere dal dataset.

## Blocco C - Calcolo dei 3 indicatori

Obiettivo:

- produrre davvero i risultati minimi della tesi.

Passi:

1. identificare i file corretti in `BioCube`;
2. capire il formato dei dati;
3. scegliere l'unita di analisi;
4. scrivere uno script o notebook per leggere:
   - species
   - temperature
   - precipitation
5. aggregare i dati;
6. salvare i risultati finali.

Output:

- tabella finale con 3 indicatori;
- eventualmente primi grafici o mappe semplici.

## Unita di analisi consigliata

Per non complicarti troppo la vita, la scelta migliore e:

`cella spaziale + periodo temporale`

Per esempio:

- una cella della griglia BioCube
- un anno

oppure:

- una cella
- un bimestre o trimestre

La scelta definitiva dipendera da come trovi organizzati i file.

## Roadmap dettagliata

## Fase 0 - Decisioni iniziali

Da chiudere subito:

1. usare `SSD esterno` come base di lavoro;
2. non fare training in questa fase;
3. obiettivo minimo = 3 indicatori;
4. usare il modello soprattutto come componente da installare e testare, non come parte obbligatoria del calcolo.

## Fase 1 - Preparazione dell'ambiente

Task:

1. creare la cartella progetto sul disco esterno;
2. clonare:
   - `bfm-model`
   - `bfm-data`
   - il repo della tesi
3. creare ambiente Python dedicato;
4. installare dipendenze.

Deliverable:

- ambiente pronto e documentato.

## Fase 2 - Download del dataset

Task:

1. fare prima un dry run del download;
2. verificare spazio disponibile;
3. scaricare `BioCube`;
4. verificare che siano presenti:
   - species
   - climate
   - temperature
   - precipitation

Deliverable:

- dataset scaricato e inventario delle cartelle.

## Fase 3 - Download dei pesi del modello

Task:

1. scaricare i pesi pre-addestrati ufficiali;
2. salvarli fuori dal repo, in una cartella `models/`;
3. annotare versione e nome del modello.

Deliverable:

- pesi disponibili localmente.

## Fase 4 - Test del modello

Task:

1. seguire l'esempio ufficiale del repository;
2. verificare se il modello si carica;
3. verificare se almeno una pipeline minima parte.

Esito atteso:

- `successo` -> il setup locale e completo
- `fallimento parziale` -> si prosegue comunque con il calcolo indicatori da dataset

## Fase 5 - Ispezione dati per i 3 indicatori

Task:

1. individuare i file species;
2. individuare la variabile temperatura;
3. individuare la variabile precipitazione;
4. capire forma, formato, granularita e time axis;
5. definire l'aggregazione minima.

Deliverable:

- nota tecnica con `quale file -> quale indicatore`.

## Fase 6 - Calcolo indicatori

Task:

1. `Numero di specie`
   - contare specie uniche per unita di analisi
2. `Temperatura media`
   - media temporale per cella o area
3. `Precipitazioni medie`
   - media o aggregazione coerente per cella o area

Deliverable:

- `csv` o `parquet` finale con i 3 indicatori.

## Fase 7 - Visualizzazione minima

Task:

1. grafico distribuzione species count;
2. grafico temperatura;
3. grafico precipitazione;
4. eventualmente prima mappa semplice, se i dati sono georeferenziati in modo diretto.

Deliverable:

- primi output da mostrare alla relatrice.

## Fase 8 - Estensione futura

Questa fase viene solo dopo.

Possibili sviluppi:

- integrare `ERA5`, `land cover`, `forest`, `urban`, `vegetation`;
- produrre mappe tematiche piu ricche;
- usare il modello per task predittivi;
- fare fine-tuning su macchine universitarie.

## La verita pratica sul modello

Se il tuo obiettivo immediato e solo calcolare i 3 indicatori, il percorso piu efficiente e:

1. installare anche il modello per completezza;
2. provarlo una volta;
3. non dipendere dal modello per il calcolo finale degli indicatori.

Questa e la soluzione migliore perche:

- riduce il rischio tecnico;
- mantiene la tesi fattibile;
- ti permette comunque di dire che hai lavorato su `BioAnalyst` come ecosistema complessivo;
- evita di bloccare tutto se l'inferenza locale fosse piu complessa del previsto.

## Quando serve davvero la macchina universitaria

La macchina universitaria diventa consigliata o necessaria se vuoi:

- fare training;
- fare fine-tuning;
- usare grandi volumi di dati aggiuntivi;
- produrre predizioni pesanti su molti batch;
- lanciare pipeline GPU-intensive.

Per:

- setup iniziale
- download
- ispezione dati
- calcolo dei 3 indicatori

la macchina universitaria non e il primo requisito.

## Piano operativo da seguire manualmente

Ordine consigliato:

1. preparare SSD esterno
2. creare cartelle di lavoro
3. clonare repo ufficiali
4. creare ambiente Python
5. scaricare dataset
6. scaricare pesi modello
7. provare esempio minimo del modello
8. leggere i file species/temperature/precipitation
9. calcolare i 3 indicatori
10. salvare output finali

## Checklist pratica

Prima di partire, verificare:

- spazio libero su disco `>= 60 GB` consigliati
- connessione internet stabile
- Git installato
- Python funzionante
- SSD montato correttamente

## Comandi minimi iniziali

Esempio locale:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pandas numpy xarray pyarrow matplotlib seaborn jupyter openpyxl
```

Dry run del dataset:

```bash
python3 Dataset/scripts/download_biocube.py
```

Download reale:

```bash
python3 Dataset/scripts/download_biocube.py --download
```

## Cosa significa successo in questa fase

La fase corrente e completata con successo se ottieni:

1. `BioAnalyst` presente in locale;
2. `BioCube` scaricato;
3. ambiente Python funzionante;
4. almeno una verifica minima del modello;
5. un file finale con:
   - numero di specie
   - temperatura media
   - precipitazioni medie

## Decisione finale consigliata

Per questa nuova versione della tesi:

- `SI` a BioAnalyst come ecosistema di riferimento
- `SI` a dataset + modello scaricati localmente
- `SI` a lavoro su SSD esterno
- `SI` al calcolo dei 3 indicatori minimi senza training
- `NO` al training come primo obiettivo
- `FORSE` al training in una seconda fase, su macchine universitarie
