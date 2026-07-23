# Report Tecnico e Metodologico

## Rollout multi-step della pipeline previsionale BioMap

### 1. Scopo del lavoro

Questo documento riassume in modo strutturato il lavoro svolto per estendere la pipeline previsionale di BioMap da una logica one-step a una logica multi-step. Il report e pensato per servire sia come documentazione tecnica del progetto sia come base per la stesura finale della sezione di tesi dedicata alla componente forecast.

L'obiettivo del rollout multi-step non e stato quello di confrontare il dato predetto con il dato osservato nella UI finale, ma di costruire una pipeline capace di produrre proiezioni su mesi futuri, mantenendo separata la logica osservativa da quella previsionale.

In termini applicativi, la pipeline doveva permettere:

- la previsione del solo mese successivo come caso one-step;
- l'estensione della previsione a piu mesi consecutivi come caso multi-step;
- l'integrazione di tali output in frontend senza eseguire un nuovo run del modello a ogni interazione dell'utente;
- la lettura di run gia calcolati e pubblicati in una cache forecast dedicata.

### 2. Contesto e motivazione

La dashboard BioMap e nata inizialmente come dashboard osservativa: l'utente seleziona un'area, definisce un periodo e ottiene indicatori osservati aggregati sul territorio. Successivamente e nata l'esigenza di aggiungere una modalita previsionale, in cui la stessa logica di selezione spaziale potesse essere riutilizzata per mostrare valori futuri.

Dal punto di vista metodologico, la previsione di aprile 2026 costituiva il primo caso semplice, perche puo essere trattata come forecast one-step a partire dagli ultimi due mesi osservati disponibili. Per i mesi successivi, da maggio a settembre 2026, non era invece sufficiente ripetere la stessa procedura: si rendeva necessario un rollout multi-step, cioe una previsione autoregressiva in cui ciascun mese stimato viene riutilizzato come input per il passo successivo.

La scelta progettuale principale e stata quindi la seguente:

- aprile 2026 come one-step;
- maggio-settembre 2026 come rollout multi-step;
- esecuzione dei run offline su macchina universitaria;
- sola lettura degli artefatti precomputati dal frontend.

Questa scelta riduce drasticamente il tempo di risposta della UI e rende la piattaforma utilizzabile anche quando la macchina che ospita i dati o la GPU non e disponibile in tempo reale.

### 3. Obiettivi specifici del rollout multi-step

Il lavoro sul rollout multi-step ha avuto cinque obiettivi concreti:

1. costruire una procedura ripetibile per generare forecast futuri a partire da due mesi osservati iniziali;
2. salvare ogni step del rollout in un formato nativo del modello, in modo da poterlo ispezionare e validare;
3. pubblicare ogni mese previsto in una struttura standardizzata leggibile dal backend e dal frontend;
4. introdurre una modalita forecast nella dashboard senza mischiare dati previsionali e osservativi;
5. mantenere esplicite le limitazioni scientifiche del metodo, soprattutto per gli orizzonti piu lunghi.

### 4. Architettura implementata

La pipeline previsionale e stata sviluppata come estensione modulare della pipeline nativa BioAnalyst.

I blocchi principali sono:

- costruzione dei batch di input con dati reali BioCube;
- esecuzione del modello in modalita one-step o rollout;
- salvataggio dei batch predetti in formato nativo `.pt`;
- esportazione dei risultati in workbook `cell_matrix`;
- pubblicazione dei workbook nella cache `previsioni/YYYY-MM/cell_matrix`;
- lettura della cache tramite backend FastAPI;
- visualizzazione nel frontend tramite toggle `Osservazione / Previsione`.

### 5. Script e componenti principali

I componenti tecnici principali introdotti o consolidati per questa fase sono:

- `scripts/forecast_native_one_step.py`
  - runner nativo per la previsione di un solo mese futuro;
- `scripts/forecast_native_rollout.py`
  - runner nativo per rollout multi-step;
- `scripts/run_rollout.py`
  - runner operativo che non si limita a generare il rollout, ma pubblica direttamente gli output nella cache forecast usata dal frontend;
- `scripts/publish_forecast_cache_from_existing_run.py`
  - utility per ripubblicare un run gia esistente nella struttura `previsioni/YYYY-MM/cell_matrix` senza rieseguire il modello;
- `scripts/bioanalyst_native_utils.py`
  - modulo centrale per:
    - contesto del run;
    - caricamento del modello;
    - esecuzione one-step;
    - esecuzione rollout;
    - salvataggio dei manifest;
- `backend_api/main.py`
  - estensione dell'API locale con:
    - `POST /api/forecast`
    - `GET /api/forecast/cells/{label}`;
- `web-ui/components/biomap-dashboard.tsx`
  - estensione della dashboard con modalita `forecast` e selezione del mese target.

### 6. Dati di input e gruppi usati dal modello

La pipeline forecast utilizza batch nativi costruiti a partire dai dataset BioCube e Copernicus locali. I gruppi mappati nella versione attuale sono:

- `surface`
  - `t2m`, `msl`, `slt`, `z`, `u10`, `v10`, `lsm`;
- `edaphic`
  - `swvl1`, `swvl2`, `stl1`, `stl2`;
- `atmospheric`
  - `z`, `t`, `u`, `v`, `q`;
- `climate`
  - `tp`, `avg_tprate`, `t2m`, `d2m` e altre variabili energetiche;
- `species`
  - osservazioni rasterizzate su griglia;
- `vegetation`
  - `NDVI` reale quando disponibile, altrimenti proxy da `lai_hv + lai_lv`;
- `agriculture`
  - `Agriculture`, `Arable`, `Cropland`;
- `forest`
  - `Forest`.

Per la previsione sono state mantenute due modalita di input:

- `--input-mode all`
  - usa vegetation, agriculture e forest quando presenti;
- `--input-mode clean`
  - lascia tali gruppi a zero e mantiene solo i gruppi core.

Questa distinzione e importante per la validazione, perche permette di capire se i layer aggiuntivi migliorano davvero la previsione o se introducono instabilita.

### 7. Logica del one-step

La logica one-step usa gli ultimi due mesi osservati disponibili come input del modello.

Per esempio:

- input: febbraio 2026 e marzo 2026;
- output: aprile 2026.

Questa modalita e stata trattata come il caso base della pipeline forecast. Dal punto di vista metodologico, il one-step costituisce il riferimento minimo necessario prima di passare a una catena autoregressiva multi-step.

### 8. Logica del rollout multi-step

Il rollout multi-step e stato implementato come forecast autoregressivo ricorsivo.

La sequenza operativa e la seguente:

1. si costruisce un batch iniziale con gli ultimi due mesi osservati reali;
2. il modello produce la previsione del mese successivo;
3. il mese appena previsto viene inserito nel nuovo batch, insieme all'ultimo mese precedente;
4. il nuovo batch diventa input per la previsione del passo successivo;
5. il processo continua fino al numero di step richiesto.

In forma concettuale:

- febbraio + marzo -> previsione aprile;
- marzo + aprile_predetto -> previsione maggio;
- aprile_predetto + maggio_predetto -> previsione giugno;
- e cosi via.

Questa e una vera pipeline autoregressiva. Di conseguenza, ogni errore commesso ai primi step puo propagarsi ai successivi. Il vantaggio e che il metodo consente di estendere l'orizzonte temporale oltre il solo mese successivo; il limite e che l'incertezza cresce con la lunghezza del rollout.

### 9. Implementazione del rollout nel codice

Il cuore dell'implementazione e stato centralizzato nel metodo `run_native_rollout` del modulo `bioanalyst_native_utils.py`.

La procedura svolge tre operazioni fondamentali:

- carica il batch iniziale scalato;
- esegue il forward del modello per ciascun `rollout_step`;
- costruisce un nuovo batch a partire dalla prediction appena prodotta.

Ogni output del rollout viene poi:

- riscalato nello spazio originale;
- timestampato correttamente;
- salvato come step autonomo del rollout.

Gli artefatti nativi principali del run sono:

- `forecast_native_manifest.json`
- `forecast_native_rollout_config.yaml`
- `native_rollout_batches/step_01.pt`
- `native_rollout_batches/step_02.pt`
- ...
- `native_rollout_batches/step_N.pt`

### 10. Pubblicazione del rollout nella cache forecast

Per l'integrazione col frontend non era pratico far leggere direttamente i file `.pt`. Per questo e stata introdotta una seconda fase: la pubblicazione del rollout nella cache forecast.

La cache ha struttura:

```text
previsioni/
  2026-04/
    cell_matrix/
  2026-05/
    cell_matrix/
  2026-06/
    cell_matrix/
  ...
```

Per ogni mese previsto vengono esportati workbook leggibili con la matrice cella-per-cella per ciascuna variabile curata.

In questo modo:

- il frontend non esegue il modello;
- il backend legge solo file gia pronti;
- la UI resta reattiva;
- il run pesante avviene offline una sola volta.

### 11. Motivazione della scelta "cache forecast"

La scelta di usare run precomputati e stata dettata da motivazioni sia tecniche sia operative.

#### 11.1 Motivazione tecnica

Un run multi-step richiede:

- caricamento del checkpoint;
- lettura del BioCube locale;
- costruzione dei batch;
- esecuzione GPU;
- esportazione degli output.

Fare tutto questo a ogni click dell'utente avrebbe reso la UI troppo lenta e fragile.

#### 11.2 Motivazione operativa

Il progetto dipende da una macchina universitaria con dati e GPU. In alcuni momenti il collegamento remoto non e disponibile o e instabile. La cache consente di continuare a sviluppare e testare il frontend anche in assenza della macchina universitaria, usando run gia prodotti.

### 12. Integrazione backend

Il backend forecast e stato progettato per leggere la cache e ricostruire una risposta coerente con la dashboard.

Le principali responsabilita del backend sono:

- verificare quali mesi target sono configurati e disponibili;
- leggere i workbook `cell_matrix` per ogni mese richiesto;
- ritagliare il `full_grid` sul bounding box selezionato dall'utente;
- aggregare le celle all'interno dell'area;
- restituire:
  - `monthly`
  - `forecastMonths`
  - `targetMonth`
  - `cellsUrl`
  - note descrittive del tipo di forecast.

La logica attuale segue questo principio:

- se il target e il primo mese disponibile, la modalita corrisponde al caso one-step;
- se il target e successivo, la risposta include tutti i mesi intermedi fino al target e viene trattata come rollout multi-step.

### 13. Integrazione frontend

La dashboard e stata estesa con un toggle iniziale:

- `Osservazione`
- `Previsione`

Quando l'utente seleziona `Previsione`:

- non imposta piu un periodo iniziale/finale;
- seleziona un solo mese target;
- il frontend chiama `/api/forecast`;
- i risultati vengono mostrati come:
  - tabella forecast mensile;
  - mappa forecast;
  - trend forecast;
  - export CSV/Excel.

Questa separazione e stata voluta per evitare di mischiare:

- logica osservativa;
- metriche di backtest;
- forecast futuro.

### 14. Scelta metodologica: niente osservati nella UI forecast

Una decisione importante e stata quella di non mostrare nella UI forecast colonne come:

- `Observed`
- `MAE`
- `RMSE`
- `Bias`
- `WAPE`
- `SMAPE`

Questa scelta e coerente con la natura del prodotto forecast finale: se il mese e futuro, l'osservato non esiste ancora. Di conseguenza la UI previsionale non deve essere trattata come un backtest, ma come una proiezione.

Gli osservati restano invece utili in fase di sviluppo e validazione tecnica, soprattutto per:

- benchmark storici;
- confronto one-step su periodi passati;
- controllo di plausibilita delle variabili.

### 15. Problemi incontrati durante il rollout multi-step

Durante lo sviluppo del rollout sono emerse diverse criticita.

#### 15.1 Accumulo di errore

Il problema strutturale piu importante del multi-step e l'accumulo di errore. Anche quando il one-step e plausibile, i mesi successivi possono peggiorare progressivamente perche il modello non riceve piu input completamente osservati, ma input parzialmente predetti.

Questo effetto e intrinseco all'approccio autoregressivo e non puo essere ignorato nella discussione di tesi.

#### 15.2 Deriva termica su mesi successivi

Sono emersi casi in cui la temperatura prevista in estate risultava non plausibile per aree come Madrid o Nuñez de Balboa. Questo suggerisce che:

- o il rollout ha accumulato troppo errore;
- o alcuni artefatti esportati non erano perfettamente riallineati alla geografia corretta.

#### 15.3 NDVI negativo o poco plausibile

Un secondo problema e stato osservato su NDVI. In teoria il canale osservativo costruito da LAI viene clampato in un range fisicamente prudente. Tuttavia il modello, una volta in rollout, puo produrre valori previsionali che escano da un range semanticamente plausibile.

Questo conferma che NDVI va trattato con cautela:

- molto utile come layer diagnostico e contestuale;
- non ancora robusto come forecast dinamico puro sul lungo orizzonte.

#### 15.4 Allineamento geografico della prediction

Un problema concreto individuato nel progetto e stato il disallineamento nord-sud della prediction rispetto alla geografia attesa. Nel caso one-step era gia stata introdotta una correzione di `spatial_alignment` per ribaltare la prediction sull'asse latitudinale negli output leggibili.

Nel lavoro piu recente e stato corretto anche il flusso dei manifest nativi, in modo che:

- sia i run one-step sia i run rollout salvino il metadata `spatial_alignment`;
- anche la lettura di run piu vecchi possa ricostruire in fallback questo metadata.

Questa correzione e importante perche un rollout pubblicato senza metadata di allineamento rischia di essere ritagliato sulla zona sbagliata della griglia europea, producendo valori apparentemente assurdi pur partendo da output numericamente coerenti.

#### 15.5 Differenza tra modalita `all` e `clean`

L'introduzione di `input-mode all` e `input-mode clean` ha messo in evidenza un'altra criticita metodologica: non tutti i layer aggiuntivi migliorano automaticamente il forecast. In alcuni casi, vegetation/agriculture/forest possono aggiungere informazione utile; in altri possono aumentare l'instabilita del rollout.

Questa distinzione e quindi parte integrante del lavoro svolto, non un dettaglio secondario.

### 16. Stato di maturita delle variabili nel forecast

Sulla base dei benchmark storici gia disponibili nel progetto, la variabile piu promettente come forecast climatico resta `t2m`, soprattutto nei mesi caldi.

Nei benchmark interni 2017-2020, la temperatura a 2 metri mostra infatti un comportamento nettamente migliore nei mesi caldi rispetto ai mesi freddi. In particolare:

- giugno:
  - MAE medio circa `1.47 C`
  - RMSE medio circa `1.98 C`
  - correlazione media circa `0.953`
- settembre:
  - MAE medio circa `2.88 C`
  - RMSE medio circa `3.74 C`
  - correlazione media circa `0.877`
- dicembre:
  - MAE medio circa `9.64 C`
  - RMSE medio circa `11.77 C`
  - correlazione media circa `0.486`

Questi risultati confermano che il one-step estivo rappresenta una baseline credibile, mentre il forecast invernale resta molto piu fragile. Il rollout multi-step deve quindi essere interpretato come estensione di una baseline che e relativamente solida soprattutto tra aprile e ottobre.

Anche NDVI mostra un segnale utile, ma con maggiore variabilita. Nei benchmark interni:

- giugno:
  - MAE medio circa `0.120`
  - RMSE medio circa `0.267`
  - correlazione media circa `0.746`
- dicembre:
  - MAE medio circa `0.155`
  - RMSE medio circa `0.304`
  - correlazione media circa `0.641`

Il fatto che NDVI mantenga una correlazione discreta ma errori relativi piu elevati supporta la scelta progettuale di trattarlo come variabile diagnostica o ecosistemica da interpretare con cautela, soprattutto quando entra in rollout.

Il quadro sintetico e il seguente:

- `t2m`
  - variabile forecast piu solida, soprattutto tra aprile e ottobre;
- `NDVI`
  - utile come indicatore ecosistemico e diagnostico, ma piu fragile nel rollout;
- `swvl1`, `swvl2`
  - utili come contesto idrologico e stress del suolo;
- `Forest`, `Arable`, `Cropland`
  - layer molto utili per lettura territoriale e indicatori compositi, ma non da interpretare come forecast dinamico con lo stesso livello di fiducia di `t2m`;
- `tp`
  - ancora instabile come indicatore principale.

### 17. Strategia di validazione adottata

Il lavoro sul rollout multi-step non e stato validato come prodotto finale attraverso metriche esposte in UI, ma attraverso controlli tecnici separati.

La strategia di validazione si articola su tre livelli.

#### 17.1 Validazione strutturale

Verifica che il run:

- parta senza errori;
- produca tutti i file attesi;
- contenga mesi forecast ordinati e corretti;
- abbia cache leggibile dal backend.

#### 17.2 Validazione geografica

Verifica che:

- il ritaglio del bounding box intersechi davvero celle valide;
- il forecast sia allineato correttamente alle coordinate;
- i valori letti dalla UI provengano dall'area selezionata e non da celle spostate.

#### 17.3 Validazione numerica

Verifica che:

- i valori non siano tutti nulli;
- i valori non siano costanti;
- le unita siano corrette;
- il range sia plausibile per le variabili principali;
- il comportamento del rollout non degeneri troppo rapidamente rispetto al one-step.

### 18. Limiti attuali

Il rollout multi-step e oggi tecnicamente funzionante, ma non puo ancora essere presentato come forecast certificato su tutte le variabili.

I limiti principali sono:

- accumulo di errore ai passi successivi;
- maggiore fragilita di NDVI nel rollout;
- possibile sensibilita agli input proxy;
- dipendenza dalla qualita della cache precomputata;
- bisogno di validazione aggiuntiva su aree campione e mesi estivi reali del 2026.

Per questo motivo il rollout a 6 mesi puo essere considerato un MVP sperimentale, mentre un rollout a 12 mesi deve restare esplicitamente classificato come fase esplorativa.

### 19. Contributi concreti del lavoro svolto

Dal punto di vista del progetto, il lavoro sul rollout multi-step ha prodotto contributi concreti e gia utilizzabili:

1. definizione di una pipeline nativa per forecast autoregressivo a piu mesi;
2. separazione rigorosa tra dashboard osservativa e dashboard forecast;
3. introduzione del concetto di `forecast cache` per run offline;
4. integrazione backend con endpoint forecast dedicati;
5. integrazione frontend con toggle osservazione/previsione;
6. salvataggio strutturato dei batch nativi di rollout;
7. introduzione di strumenti di ripubblicazione della cache a partire da run gia esistenti;
8. correzione della propagazione del metadata di allineamento geografico anche ai run rollout;
9. formalizzazione delle condizioni di validazione e dei limiti metodologici del forecast multi-step.

### 20. Interpretazione corretta del risultato nella tesi

Per la tesi, il rollout multi-step deve essere descritto come:

- estensione sperimentale della pipeline previsionale;
- procedura autoregressiva per generare scenari mensili futuri;
- strumento utile a costruire una dashboard forecast interattiva;
- metodologia promettente ma non ancora definitiva per tutte le variabili.

In particolare, conviene evitare formulazioni del tipo:

- "il modello prevede con accuratezza certificata fino a sei mesi";
- "tutte le variabili sono affidabili allo stesso modo";
- "i valori forecast sono equivalenti a osservazioni future".

Sono invece piu corrette formulazioni del tipo:

- "e stata implementata una pipeline forecast autoregressiva multi-step";
- "il forecast di temperatura mostra il comportamento piu solido nei mesi caldi";
- "alcune variabili, come NDVI, restano diagnostiche o esplorative";
- "il rollout e stato integrato nella piattaforma come proiezione futura e non come dato osservato".

### 21. Sviluppi successivi consigliati

I passi successivi piu importanti sono:

1. rifare i run multi-step dopo le correzioni recenti sull'allineamento geografico;
2. confrontare `input-mode all` e `input-mode clean` sui mesi 2026-04 -> 2026-09;
3. verificare mese per mese quando inizia l'eventuale deriva numerica;
4. introdurre controlli di plausibilita piu forti per NDVI e temperatura;
5. valutare se limitare la UI finale a un orizzonte considerato sufficientemente stabile;
6. mantenere 12 mesi come estensione sperimentale e non come default operativo.

### 22. Testo base riusabile per la tesi

Di seguito una proposta di testo gia abbastanza vicina a una scrittura da capitolo finale.

#### 22.1 Versione sintetica

Per estendere la pipeline previsionale oltre il semplice forecast del mese successivo e stata implementata una procedura di rollout multi-step basata sul modello nativo BioAnalyst. La logica adottata e autoregressiva: a partire dagli ultimi due mesi osservati disponibili, il modello produce la previsione del mese successivo; tale previsione viene poi reinserita come input per stimare il mese successivo ancora, iterando il processo fino all'orizzonte desiderato. In questo modo e stato possibile costruire una sequenza forecast da aprile a settembre 2026, mantenendo separata la componente osservativa da quella previsionale e integrando gli output in una dashboard dedicata.

#### 22.2 Versione estesa

La componente forecast del progetto e stata sviluppata in due fasi. In una prima fase e stata implementata la previsione one-step, cioe la stima del solo mese successivo a partire dagli ultimi due mesi osservati. In una seconda fase la pipeline e stata estesa a un rollout multi-step, necessario per generare scenari mensili futuri su piu mesi consecutivi. Dal punto di vista algoritmico, il rollout e stato costruito come procedura autoregressiva: il primo mese futuro viene stimato usando dati osservati reali, mentre i mesi successivi vengono previsti riutilizzando progressivamente gli output gia generati dal modello. Questa scelta ha reso possibile produrre sequenze forecast di sei mesi, ma ha anche introdotto il problema dell'accumulo di errore, che rappresenta il principale limite scientifico del metodo.

Per rendere la soluzione compatibile con l'uso in dashboard, il frontend non esegue direttamente il modello a ogni interazione dell'utente. I run multi-step vengono invece calcolati offline e pubblicati in una cache forecast strutturata per mese, dalla quale il backend legge i workbook cella-per-cella necessari a ricostruire tabella, mappa e grafici. Tale architettura ha permesso di mantenere una chiara separazione tra modalita osservativa e modalita previsionale e di trattare il forecast come proiezione futura, evitando di mostrare nella UI metriche di errore o confronti con osservati che non avrebbero significato nei mesi realmente futuri.

I test e le analisi svolte hanno mostrato che la temperatura a 2 metri (`t2m`) costituisce al momento la variabile previsionale piu solida, in particolare nei mesi caldi, mentre variabili come NDVI restano molto utili per l'interpretazione ecosistemica ma richiedono maggiore cautela quando vengono portate in rollout multi-step. Il lavoro svolto non porta quindi a un forecast certificato per tutte le variabili, ma definisce una pipeline previsionale operativa, integrata nella piattaforma e sufficientemente matura da costituire la base per ulteriori sviluppi, validazioni e raffinamenti metodologici.

#### 22.3 Frase finale consigliata

Nel complesso, il rollout multi-step rappresenta il passaggio dal forecast sperimentale del singolo mese a una pipeline previsionale strutturata, capace di generare scenari futuri territorializzati e di alimentare una dashboard interattiva, pur mantenendo esplicita la natura esplorativa e progressivamente validabile dei risultati.

### 23. Conclusione

Il lavoro sul rollout multi-step non e stato un'aggiunta marginale, ma il nucleo della trasformazione della pipeline forecast da semplice prova tecnica a componente strutturata della piattaforma BioMap. Il risultato raggiunto e una catena completa:

- selezione dell'area;
- definizione del mese target;
- lettura di forecast precomputati;
- ricostruzione mensile per area;
- visualizzazione in dashboard;
- esportazione dei risultati.

Resta necessario consolidare la validazione numerica e geografica dei mesi successivi al primo, ma la base infrastrutturale e metodologica della pipeline previsionale e oggi effettivamente presente.
