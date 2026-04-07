# Perché Il Forecast Non È Ancora Validato

Questo documento spiega in modo tecnico ma chiaro perché, nonostante stiamo usando:

- un dataset ufficiale (`BioCube`);
- un repository ufficiale (`bfm-model`);
- pesi ufficiali (`bfm-pretrained-small.safetensors`);

il forecast locale di `temperatura` e `precipitazione` non è ancora scientificamente validato.

## Conclusione Breve

Il problema non è che "il modello è rotto" oppure che "il dataset è sbagliato".

Il problema reale è che tra:

- `dati raw locali`,
- `adapter BIOMAP`,
- `formato batch atteso dal modello`,
- `scaling`,
- `semantica del target`,
- `scala spaziale del caso d'uso`

ci sono diversi punti in cui basta un disallineamento piccolo per ottenere forecast numericamente coerenti come tensor, ma non credibili dal punto di vista scientifico.

In altre parole:

- `il modello può girare correttamente`
- ma `il nostro uso del modello` può comunque restituire risultati sbagliati

## Cosa Abbiamo Già Corretto

Prima di arrivare a questa diagnosi, sono già stati corretti problemi reali:

1. `inversione scaling errata`
2. `media areale pesata con denominatore sbagliato`
3. `species occurrence records non allineati alla griglia ERA5 0.25°`
4. `supporto reale a --device cuda`

Quindi i valori assurdi iniziali non dipendevano solo dal modello.

Questo è importante, perché significa che oggi il forecast viene giudicato su una pipeline locale molto più pulita di prima.

## Perché Modello + Dataset Ufficiali Non Bastano

### 1. Il modello non legge direttamente i file raw che leggiamo noi

Il repository ufficiale `bfm-model` non è pensato per leggere direttamente:

- `parquet` specie raw
- `netCDF` ERA5 raw

nel modo in cui lo fa il nostro backend osservativo.

Il modello lavora su batch `.pt` già preparati con:

- shape precisa
- gruppi di variabili precisi
- due timestep
- pressure levels ordinati
- scaling coerente con le statistiche ufficiali

Quindi anche se i file sorgente sono ufficiali, il passaggio:

`raw BioCube -> batch compatibile con il modello`

resta una fase critica e non banale.

### 2. Il modello pubblico mensile usa finestre corte a 2 timestep

La pipeline mensile pubblica del modello usa finestre corte di `2` mesi.

Questo significa che in inferenza il modello non assorbe "tutta la storia 2000-2020 di una città" come sequenza lunga.

Fa invece:

- input di due mesi osservati
- forecast one-step
- eventuale rollout autoregressivo

Questa scelta è coerente con il modello ufficiale, ma rende la validazione più delicata perché:

- molta informazione storica locale non entra come input diretto
- l'accuratezza dipende molto da quanto bene il modello ha imparato dinamiche generali nel pretraining

### 3. Il nostro caso d'uso è più locale del target dichiarato nel paper

Il paper presenta BioAnalyst a scala europea, con risoluzione `0.25°` e target `regional to national-scale`.

Questo significa che il caso d'uso naturale è più vicino a:

- regioni
- macro-aree
- paesaggi ampi

che non a:

- quartieri
- città compatte
- micro-ambienti urbani

Una cella `0.25°` in Europa copre grossolanamente decine di chilometri.

Quindi una città come Milano, Madrid o Napoli viene osservata dal modello in un modo molto più grossolano rispetto a come la immaginiamo a livello umano.

Questo non rende il test impossibile, ma lo rende più fragile.

### 4. La semantica del nostro indicatore finale non coincide perfettamente con il target nativo del modello

Per `temperatura` e `precipitazione` il disallineamento è più piccolo, ma esiste comunque perché:

- il modello produce campi grigliati
- noi poi li aggreghiamo a livello area

Per `species`, il problema è ancora più forte:

- lo `species richness osservato` si misura direttamente dai `Species occurrence records`
- il `forecast species` invece non è un target diretto già pronto del modello nella forma che vogliamo noi

Quindi la forecast species oggi è ancora una `proxy`, non un indicatore diretto equivalente all'osservato.

## Problemi Tecnici Ancora Aperti

### 1. `missing_keys` nel checkpoint

Il caricamento del checkpoint `small` produce ancora `14 missing keys`.

Anche se il modello parte e il forward gira, questo è un segnale da non ignorare:

- può indicare mismatch architetturale o parametrico
- può essere tollerabile per smoke test
- non è ideale per una validazione scientifica finale

### 2. Non abbiamo ancora un benchmark ufficiale pronto all'uso

Oggi non abbiamo a disposizione:

- batch ufficiali di benchmark già pronti
- notebook ufficiali di evaluation completi
- config complete degli autori per il caso esatto che stiamo replicando

Quindi dobbiamo fare un lavoro di ricostruzione metodologica locale, che è molto più delicato di un semplice `run model.py`.

### 3. La precipitazione è intrinsecamente più instabile della temperatura

Nei test già fatti, la temperatura a volte si avvicina a una plausibilità parziale, mentre la precipitazione resta molto più rumorosa.

Questo è coerente con il fatto che:

- la pioggia ha distribuzioni molto asimmetriche
- molti mesi sono vicini a zero
- gli errori percentuali possono esplodere facilmente

Quindi la pioggia è il primo punto che tende a fallire anche quando la pipeline è tecnicamente corretta.

## Cosa Dicono I Risultati Attuali

I run già eseguiti dicono questo:

- la pipeline `observed` oggi è plausibile
- il forecast `small` gira
- il forecast `small` non passa ancora la validazione clima

Esempio concreto già prodotto:

- nel micro-run `Madrid -> forecast 2019-01`
- la temperatura ha errore percentuale in Kelvin accettabile
- ma errore assoluto troppo alto (`3.57 °C`)
- la precipitazione fallisce nettamente sia in termini assoluti sia percentuali

Questo vuol dire che il problema non è "il run non parte".

Il problema è:

`parte, ma non è ancora abbastanza accurato`

## Perché Non Basta Dire “Proviamo Il Large”

Passare subito al checkpoint `large` può aiutare, ma non è ancora la prima mossa giusta.

Perché:

1. se il problema è nel preprocessing, il `large` eredita lo stesso problema;
2. se il problema è nella semantica del target o nella scala spaziale, il `large` non lo risolve da solo;
3. il `large` è più costoso da testare, quindi rischia di rendere il debug più lento e meno trasparente.

Il `large` ha senso solo dopo una validazione chiara del flusso:

`raw -> batch -> forecast -> metriche`

## Cosa Farei Per Farlo Funzionare Davvero

### Step 1 - Chiudere la validazione clima su GPU

Prima di tutto serve una validazione seria su:

- set core di città
- aree non urbane
- 2019 mensile
- poi storico 2000-2020 con stride trimestrale

Questo separa subito:

- modello che non generalizza
- adapter locale che ancora disallinea qualcosa

### Step 2 - Capire se il problema è più forte in città che in aree naturali

Se il modello va peggio in città ma meglio in aree non urbane, allora abbiamo una conferma forte del limite di scala spaziale.

Questa è una diagnosi molto utile anche per la UI finale.

### Step 3 - Confrontare `small` e `large`

Solo se il blocco clima `small` resta debole anche su GPU, allora ha senso passare a:

- scaricare `large`
- parametrizzare correttamente la config locale
- ripetere la stessa validazione

### Step 4 - Separare definitivamente clima e specie

Se anche dopo la validazione il blocco clima diventa accettabile ma la specie no, la strategia metodologicamente più onesta sarà:

- `forecast modello` per temperatura e precipitazione
- `species richness osservato` per il passato
- `species outlook` come proxy o report interpretativo, non come forecast diretto forte

Questa non sarebbe una sconfitta.

Sarebbe una scelta scientificamente corretta.

## Decisione Operativa Oggi

Ad oggi, la posizione più solida è questa:

- gli indicatori osservati sono pronti
- il forecast è ancora in validazione
- il prossimo passo corretto è GPU validation, non UI
- se il GPU validation fallisce ancora, il passo successivo è `small vs large`

## Frase Finale Da Tenere Ferma

Il progetto oggi non è bloccato perché "il modello open source non funziona".

È bloccato perché:

- stiamo cercando di usare un modello scientifico complesso fuori da una pipeline benchmark completa già pronta;
- il nostro caso d'uso è più locale e più interpretativo del caso d'uso minimo mostrato pubblicamente;
- la validazione corretta richiede allineamento rigoroso tra dati, batch, scaling, target e scala spaziale.

Questa è una difficoltà reale, ma è anche esattamente il tipo di lavoro che rende la tesi forte se lo affrontiamo bene.
