# Modello BioAnalyst

Stato documento: 2026-04-02

## Stato Reale Del Lavoro

Questo e il punto di arresto sicuro del progetto al momento.

### Completato

- checkpoint ufficiale `small` scaricato in locale su `Archivio`;
- path dei pesi mantenuto fuori da GitHub;
- repository ufficiale `bfm-model` collegato localmente;
- ambiente dedicato `.venv-bioanalyst` creato;
- script di supporto modello creati;
- adapter BIOMAP `forecast_area_indicators.py` impostato.
- `pyarrow` installato nel venv modello;
- primo smoke test locale completato con output salvati;
- primo run one-step completo con `era5_pressure.nc` completato;
- rollout completo a `+2 mesi` completato;
- rollout completo a `+6 mesi` completato.

### Preparato Ma Non Ancora Validato Scientificamente

- interpretazione scientifica dei valori forecast;
- validazione storica `forecast vs observed`;
- verifica del motivo per cui alcuni output restano numericamente implausibili;
- eventuale confronto `small vs large` dopo la validazione del flusso.

### Ultimo Punto Di Arresto

Prima di fermare il lavoro e stato corretto un bug reale del forecast:

- il resolver citta del modulo modello usava la chiave sbagliata del catalogo europeo;
- ora il codice legge correttamente `label` e `value`;
- sono supportati anche alias CLI comuni come `milano -> milan`.

Quindi il prossimo step non e piu "fix del catalogo citta" o "chiusura del blocco atmosferico", ma la validazione degli output.

Aggiornamento ulteriore:

- il primo test di inferenza e stato completato in modalita `--fast-smoke-test`;
- il modello carica, esegue il forward e salva output;
- il run one-step completo con blocco atmosferico reale e stato chiuso;
- il rollout multi-step completo a `+2 mesi` e `+6 mesi` e stato chiuso.

### Regola Di Lettura

Questo README non dice che il forecast e gia concluso.

Dice invece che:

- la parte infrastrutturale e pronta;
- il codice per il forecast esiste;
- la prova controllata di inferenza esiste gia;
- il prossimo passo giusto e validare e spiegare i risultati.

## Obiettivo di questo documento

Questo README definisce la roadmap del modulo `forecast` basato su `BioAnalyst`, chiarisce dove devono stare i pesi del modello e spiega perche, in questa fase, e meglio partire dal checkpoint `small`.

## Dove devono stare i pesi

I pesi non devono stare nel repository GitHub.

Il path locale configurato oggi e:

- `BIOANALYST_MODEL_DIR=/Volumes/Archivio/biomap_thesis/models/bioanalyst_pretrained`

Al suo interno oggi e presente:

- `bfm-pretrained-small.safetensors`

Questa variabile e definita nel file `.env` locale del progetto.

## Fonti ufficiali

- [BioAnalyst model card su Hugging Face](https://huggingface.co/BioDT/bfm-pretrained)
- [BioAnalyst codebase su GitHub](https://github.com/BioDT/bfm-model)
- [BioCube su Hugging Face](https://huggingface.co/datasets/BioDT/BioCube)

## Checkpoint disponibili

Dalla repository ufficiale dei pesi risultano oggi disponibili:

- `bfm-pretrained-small.safetensors` circa `781 MB`
- `bfm-pretrain-large.safetensors` circa `2.84 GB`

Verifica locale corrente:

- checkpoint `small` presente in locale, circa `745 MB` scaricati

## Perche partire dal modello `small`

Anche se lo spazio su `Archivio` e disponibile, lo storage non e l'unico vincolo.

Per l'uso locale sul Mac, il checkpoint `small` e preferibile per questi motivi:

1. `Caricamento piu leggero`
   Richiede meno memoria durante il load del modello e durante l'inferenza.

2. `Tempi di test molto piu brevi`
   Se stiamo ancora costruendo la pipeline, conviene validare prima l'integrazione con un modello piu leggero.

3. `Debug piu semplice`
   Se qualcosa non funziona, e molto meglio scoprirlo con il checkpoint piu piccolo.

4. `Migliore per la fase prototipale`
   In questa fase il nostro obiettivo non e spremere il massimo dell'accuratezza, ma dimostrare che:
   - il modello si carica,
   - riceve input coerenti,
   - produce forecast utilizzabili,
   - si integra con l'interfaccia BIOMAP.

5. `Riduce il rischio metodologico`
   Se il `small` non e ancora integrato bene, non ha senso passare subito al `large`.

## Quando usare il modello `large`

Il checkpoint `large` ha senso in una fase successiva, quando:

- il flusso `input -> inferenza -> output forecast` e gia stabile;
- abbiamo gia fatto test con il `small`;
- vogliamo confrontare `small vs large`;
- oppure vogliamo spostare il carico su macchine universitarie.

In breve:

- `small` = checkpoint da usare adesso;
- `large` = checkpoint da testare dopo, come upgrade.

## Setup Locale Creato

Il progetto contiene ora questi pezzi dedicati al modello:

- [activate_bioanalyst_model.sh](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_bioanalyst_model.sh)
- [download_bioanalyst_weights.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/download_bioanalyst_weights.py)
- [bioanalyst_model_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/bioanalyst_model_utils.py)
- [forecast_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py)
- [forecast_rollout_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_rollout_area_indicators.py)
- [forecast_backtest_one_step.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_backtest_one_step.py)
- repo ufficiale: [external/bfm-model](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/external/bfm-model)

Questa struttura e gia sufficiente per ripartire dal test di inferenza senza dover ricostruire il setup.

## Stato reale dei dati: 2020 o 2025?

Qui bisogna distinguere tra `range per singola sorgente` e `range comune usabile dalla pipeline`.

### Range verificati localmente

Controllo locale sui file realmente scaricati:

- `Species/europe_species.parquet` -> `2000-01-01` fino a `2025-05-01`
- `ERA5 temperature` -> `2000-01-01` fino a `2020-12-01`
- `ERA5 precipitation` -> `2000-01-01` fino a `2020-12-01`

### Conclusione corretta

`Si`, e vero che una parte del dataset locale arriva fino al `2025`, ma non tutte le sorgenti arrivano a quella data.

In particolare:

- il layer `species` arriva fino a `2025-05`;
- i layer climatici che stiamo usando per i tre indicatori minimi si fermano a `2020-12`.

Per questo motivo la UI e la pipeline mostrano oggi come periodo comune:

- `2000-01 -> 2020-12`

### Perche succede

La spiegazione piu probabile e questa:

1. la release o il paper originale del dataset e costruita sul periodo storico `2000-2020`;
2. il layer `species` sul repository attuale e stato aggiornato con osservazioni piu recenti;
3. i layer climatici e quelli che stiamo usando per la pipeline minima non sono ancora stati estesi oltre il 2020 nella stessa release locale.

Quindi non e una contraddizione vera e propria: e una `asimmetria tra sorgenti`.

## Regola metodologica per BIOMAP

Per gli indicatori minimi osservati attuali, la regola corretta e:

- usare il `range comune` delle sorgenti coinvolte;
- quindi `2000-01 -> 2020-12`.

Se in futuro vorremo usare anche `2021-2025`, dovremo:

1. aggiungere dati climatici compatibili fino al 2025;
2. oppure usare una release piu aggiornata e omogenea di BioCube;
3. oppure limitare certe analisi solo al layer `species`, dichiarandolo esplicitamente.

## Come usare il modello nel progetto BIOMAP

La cosa piu importante e questa:

il modello non deve sostituire la pipeline osservativa, ma deve diventare un `modulo di forecast`.

### Struttura consigliata

`BioCube osservato -> indicatori storici -> modello BioAnalyst -> forecast 6/12 mesi -> report`

### Cosa fa la pipeline osservativa

La pipeline attuale ci da:

- area selezionata;
- periodo scelto;
- `species_count_observed_area`;
- `temperature_mean_area_c`;
- `precipitation_mean_area_mm`.

### Cosa dovrebbe fare il modello

Il modello dovrebbe aggiungere:

- forecast a `+6 mesi`;
- forecast a `+12 mesi`;
- eventualmente piu step intermedi mensili;
- output strutturati e confrontabili con gli indicatori osservati.

## Cosa NON deve fare il modello

Non va usato, almeno all'inizio, per generare direttamente frasi causalmente forti come:

- `le temperature alte causano la diminuzione delle specie`

Questa conclusione sarebbe troppo forte senza una validazione seria.

Il modello va usato per produrre:

- previsioni numeriche;
- scenari;
- anomalie;
- confronti con lo storico.

Il report finale poi deve tradurre questi risultati in linguaggio chiaro ma prudente.

## Roadmap completa del modulo forecast

### Fase 1 - Setup pesi e codice

Obiettivo:

- avere pesi e codice ufficiali pronti in locale.

Step:

1. completare il download del checkpoint `small` in `Archivio`;
2. tenere il path dei pesi fuori da GitHub;
3. scaricare o collegare il repository ufficiale `bfm-model`;
4. verificare i requisiti Python del modello.

Output atteso:

- checkpoint disponibile in locale;
- codice ufficiale pronto per i test.

### Stato fase 1

`Chiusa`

Motivo:

- pesi `small` presenti;
- repo ufficiale presente;
- ambiente dedicato presente;
- requisiti principali modello installati in un ambiente separato;
- smoke test partito e andato oltre il caricamento dei dati.

### Fase 2 - Primo test di inferenza

Obiettivo:

- dimostrare che il modello si carica e gira.

Step:

1. trovare l'esempio minimo ufficiale di prediction o rollout;
2. eseguire un test di inferenza su un singolo caso;
3. salvare log, config e output.

Output atteso:

- primo run documentato del modello in locale.

### Stato fase 2

`Chiusa`

Motivo:

- il modello viene caricato;
- il forward one-step viene eseguito;
- gli output vengono salvati su disco;
- esiste un `forecast_summary.json` documentato;
- esiste un run completo con blocco atmosferico reale.

### Fase 3 - Adattatore BIOMAP

Obiettivo:

- collegare il modello alla selezione `area + periodo` della nostra interfaccia.

Step:

1. definire il formato input richiesto dal modello;
2. costruire un adapter che parta dall'area selezionata in UI;
3. generare il batch o tensore corretto per l'inferenza;
4. ottenere un output forecast leggibile.

Output atteso:

- uno script intermedio tipo `forecast_area_indicators.py`.

### Stato fase 3

`Chiusa a livello tecnico`

Motivo:

- l'adapter esiste gia come [forecast_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py);
- il formato input parte gia da `city / bbox / periodo`;
- il run effettivo del modello sopra questi input e stato eseguito con successo sia in modalita `--fast-smoke-test` sia in modalita completa;
- restano aperti solo i perfezionamenti scientifici e non piu quelli architetturali di base.

## Run Tecnici Completati

Smoke test eseguito:

```bash
source /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_bioanalyst_model.sh
python /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --fast-smoke-test
```

Output principali salvati in:

- [forecast_area_indicators.csv](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12/forecast_area_indicators.csv)
- [forecast_area_indicators.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12/forecast_area_indicators.xlsx)
- [forecast_summary.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12/forecast_summary.json)
- [forecast_config.yaml](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12/forecast_config.yaml)

Run completo one-step eseguito:

```bash
source /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_bioanalyst_model.sh
python /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Output principali:

- [forecast_summary.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12/forecast_summary.json)
- [forecast_area_indicators.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12/forecast_area_indicators.xlsx)

Run completo rollout `+6 mesi` eseguito:

```bash
source /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_bioanalyst_model.sh
python /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_rollout_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --steps 6
```

Output principali:

- [forecast_rollout_summary.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12_rollout_6m/forecast_rollout_summary.json)
- [forecast_rollout_6m.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/milan_2019_12_rollout_6m/forecast_rollout_6m.xlsx)

## Come Leggere Questi Risultati

I run completati significano:

- il setup modello e funzionante;
- il caricamento checkpoint e funzionante;
- l'adapter BIOMAP produce batch leggibili da `bfm-model`;
- il modello esegue inferenza e salva output finali;
- il rollout multi-step completo parte e termina senza crash.

I run tecnici NON significano ancora:

- che il forecast sia scientificamente affidabile;
- che i valori numerici attuali siano gia interpretabili come risultato finale di tesi;
- che il forecast sia gia pronto per essere esposto come conclusione automatica nell'interfaccia finale.

In particolare, i valori attuali vanno considerati `solo di validazione tecnica`, perche:

- anche i run completi mostrano ancora `missing_keys`;
- il rollout `+6 mesi` restituisce valori non plausibili, per esempio temperatura costante intorno a `-109 °C` e precipitazione costante intorno a `48493 mm`;
- quindi la pipeline e corretta come integrazione tecnica, ma non ancora come strumento scientifico pronto all'uso.

### Fase 4 - Forecast 6 e 12 mesi

Obiettivo:

- produrre previsioni realmente utili per BIOMAP.

Step:

1. forecast a `+6 mesi`;
2. forecast a `+12 mesi`;
3. salvataggio dei risultati in formati coerenti con la UI;
4. confronto con gli indicatori storici osservati.

Output atteso:

- tabella forecast scaricabile;
- confronto `osservato vs previsto`.

### Stato fase 4

`Chiusa a livello tecnico per +2 e +6 mesi`

Motivo:

- esiste lo script [forecast_rollout_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_rollout_area_indicators.py);
- il rollout completo con `era5_pressure.nc` e stato eseguito su `+2 mesi`;
- il rollout completo con `era5_pressure.nc` e stato eseguito su `+6 mesi`;
- gli output vengono salvati in formati coerenti con la UI.

### Come ripartire dalla fase 4

La parte tecnica della fase 4 e partita e si e chiusa.

Il prossimo avanzamento utile della fase 4 e:

1. produrre rollout a `+12 mesi`;
2. confrontare `small` e `large` solo dopo la validazione del `small`;
3. decidere se esporre in UI il forecast come modalita `beta` o tenerlo nascosto fino alla validazione scientifica.

### Fase 5 - Validazione storica

Obiettivo:

- rendere il forecast scientificamente difendibile.

Step:

1. scegliere finestre storiche di test;
2. far prevedere al modello periodi per cui abbiamo gia il dato reale;
3. confrontare forecast e osservato;
4. misurare errore e stabilita.

Metriche minime da salvare:

- `MAE` temperatura;
- `MAE` precipitazione;
- errore o scostamento sulle specie, se il task/model output lo permette;
- analisi qualitativa dei casi in cui il modello sbaglia di piu.

Output atteso:

- una sezione di validazione nella tesi;
- soglie di affidabilita per il report finale.

## Problemi Trovati Fin Qui

Questi sono i problemi reali emersi durante il setup:

1. `dipendenze ufficiali pesanti`
   Il repo ufficiale porta con se dipendenze non banali; per questo e stato creato un ambiente dedicato separato.

2. `integrazione locale delicata`
   Il codice ufficiale e pensato per un contesto di training/inferenza piu ampio del nostro, quindi serve una config locale adattata.

3. `range dati non uniforme`
   Il layer `species` arriva oltre il `2020`, ma i layer climatici minimi usati dal progetto attuale si fermano a `2020-12`.

4. `forecast specie da interpretare con prudenza`
   L'output specie del modello va trattato come proxy o segnale modellistico, non come misura osservata diretta.

5. `pressione atmosferica ancora lenta`
   Il file `era5_pressure.nc` e il collo di bottiglia principale del run completo. Per questo il primo test chiuso oggi usa la modalita `--fast-smoke-test`.

## Prossimo Step Sicuro

Quando vorrai riprendere, il primo comando sicuro da rieseguire e:

```bash
source /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/activate_bioanalyst_model.sh
```

Subito dopo:

```bash
python -m py_compile /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/bioanalyst_model_utils.py /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/download_bioanalyst_weights.py /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py
```

Poi, come primo vero test controllato:

```bash
python /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu
```

Per un test rapido e stabile gia validato:

```bash
python /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/forecast_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01 --checkpoint small --device cpu --fast-smoke-test
```

## Conclusione Operativa

Il progetto modello non e fermo a zero.

La parte giusta da dire oggi e:

- `setup completato`;
- `one-step completo chiuso`;
- `rollout +2 mesi e +6 mesi chiusi a livello tecnico`;
- `fase 5 diagnostica avviata con fix locali gia applicati`;
- `resta aperta la validazione scientifica, non piu il setup tecnico`.

## Aggiornamento Fase 5

La fase 5 ha gia chiarito tre punti molto importanti:

1. il dataset osservato non e il problema principale;
2. esistevano due bug locali reali:
   - inversione errata dello scaling
   - media areale pesata con denominatore sbagliato
3. dopo questi fix, il forecast e molto piu leggibile, ma resta ancora impreciso soprattutto sulla parte specie.

Risultati salvati:

- [forecast_backtest_one_step.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/phase5_backtest_milano_madrid/forecast_backtest_one_step.xlsx)
- [forecast_backtest_details.json](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/model_forecast/phase5_backtest_milano_madrid/forecast_backtest_details.json)
- [PHASE_5_FINDINGS.md](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/docs/PHASE_5_FINDINGS.md)

### Fase 6 - Integrazione in UI

Obiettivo:

- aggiungere il bottone forecast nell'interfaccia.

Step:

1. aggiungere pulsante `Previsione 6 mesi`;
2. aggiungere pulsante `Previsione 12 mesi`;
3. generare file scaricabili `CSV/XLSX`;
4. mostrare un report sintetico leggibile.

Output atteso:

- nuova sezione UI con forecast e download.

## Come dovrebbe essere il report finale

Il report finale dovrebbe contenere:

1. area selezionata;
2. periodo osservato;
3. periodo previsto;
4. andamento osservato degli indicatori;
5. forecast del modello;
6. confronto con baseline storica;
7. nota metodologica sui limiti.

## Linguaggio corretto del report

Le conclusioni dovrebbero essere formulate cosi:

- `Nel periodo storico osservato, condizioni di temperatura sopra la media e precipitazioni sotto la media risultano associate a una riduzione delle specie osservate nell'area selezionata.`
- `Il forecast a 6 mesi mostra condizioni coerenti con questo pattern storico.`

Questo e molto meglio di affermazioni troppo forti di tipo causale.

## Raccomandazione finale

La strategia migliore per BIOMAP e:

1. finire la pipeline osservativa;
2. usare `BioAnalyst small` per il primo modulo forecast;
3. validare il forecast su finestre storiche;
4. solo dopo aggiungere il bottone in UI;
5. testare il `large` in un secondo momento.

## Stato consigliato del lavoro

Ordine consigliato dei prossimi passi:

1. estendere il backtesting one-step ad altre città europee;
2. testare più finestre temporali, non solo `2019 -> 2020-01`;
3. chiarire il ruolo dei `missing_keys` residui;
4. valutare se il checkpoint `large` migliora davvero il backtest;
5. portare il forecast in UI solo dopo una baseline convincente.
