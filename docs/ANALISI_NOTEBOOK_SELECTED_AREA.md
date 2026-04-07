# Analisi del notebook `selected_area.ipynb`

## Esito rapido

Il notebook [selected_area.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/selected_area.ipynb) **non contiene codice nuovo** per la correzione del bug sul calcolo mensile degli indicatori.

In particolare:

- e stato aggiunto in un commit dedicato: `8965f35 Create selected_area.ipynb`
- non esistono commit del collega che modifichino direttamente:
  - [selected_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/selected_area_indicators.py)
  - [minimum_indicator_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/minimum_indicator_utils.py)
- il notebook e un duplicato byte-for-byte di [01_dataset_exploration.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/01_dataset_exploration.ipynb)
- gli output eseguiti dentro il notebook puntano al file [selected_milano_area_monthly.xlsx](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/outputs/local_preview/selected_milano_area_monthly.xlsx) e mostrano valori plausibili per Milano `2018-01 -> 2019-12`

Quindi, ad oggi, **non c'e codice da integrare negli script** a partire da quel notebook.

L'unica parte utile da recuperare e:

- usarlo come riferimento di validazione manuale
- usare i suoi output come sanity check per verificare che gli indicatori osservati abbiano ordini di grandezza plausibili

## Valutazione delle modifiche spiegate a voce dal collega

Dopo il confronto con il dettaglio che hai riportato, le modifiche del collega si dividono in tre gruppi.

### 1. Modifica utile e da integrare

La modifica davvero utile e questa:

- allineare `Species.latitude` e `Species.longitude` alla griglia ERA5 `0.25°` prima del merge cella-per-cella

Motivo:

- le osservazioni specie sono puntuali
- il clima ERA5 e su griglia
- senza snapping alla griglia, il merge tra specie e clima puo perdere record o creare mismatch spaziali

Questa parte e stata integrata nel progetto tramite una utility condivisa:

- [snap_coordinates_to_grid](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/minimum_indicator_utils.py)

e viene ora usata in:

- [compute_species_cell_month](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/selected_area_indicators.py)

### 2. Modifica non necessaria come fix

La riscrittura sequenziale di `load_climate_datasets(...)` **non cambia la logica** rispetto allo script originale.

Nel codice originale, infatti, questa pipeline era gia presente:

- `xr.open_dataset(...)`
- `subset_europe(...)`
- `filter_dataset_month_range(...)`
- `subset_bbox(...)`

La versione del collega la espande in piu righe, ma il comportamento e lo stesso perche:

- [subset_europe](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/minimum_indicator_utils.py) normalizza gia le longitudini da `0..360` a `-180..180`
- la composizione annidata e quella sequenziale sono equivalenti

Quindi:

- utile come chiarimento di lettura
- non e un fix sostanziale da mantenere come tale

### 3. Modifiche da Jupyter da non integrare

Queste modifiche non vanno portate nel codice di produzione:

- `PROJECT_ROOT = Path().resolve()`
- `parse_args(args=[...])`
- path hardcoded tipo `C:\\Users\\Onorato\\BioCube`
- print di debug temporanei

Sono modifiche di contesto utili solo per far girare il notebook locale del collega.

## Cosa fa davvero il notebook

Il notebook e un notebook generico di esplorazione dati. Serve a:

- aprire un file `csv`, `parquet` o `xlsx`
- mostrare shape, colonne e tipi
- mostrare missing values
- visualizzare statistiche descrittive
- disegnare grafici numerici semplici
- disegnare grafici temporali se trova la colonna `month`
- mostrare una scatter map se trova `latitude` e `longitude`

Questo lo rende:

- utile per ispezionare i dataset
- utile per controlli manuali
- utile per debugging visivo
- utile come baseline visuale su Milano 2018-2019

ma **non utile come fix implementativo** del bug mensile.

## Cosa c'e di utile negli output del notebook

Il notebook contiene output gia eseguiti che mostrano:

- `24` mesi di dati
- periodo `2018-01 -> 2019-12`
- temperatura media areale Milano plausibile per stagionalita
- precipitazioni mensili plausibili
- `species_count_observed_area` sempre valorizzato nel file mostrato

Esempi visibili nell'output:

- `2018-06`: temperatura area circa `22.51 °C`
- `2018-07`: temperatura area circa `24.94 °C`
- `2018-08`: temperatura area circa `24.96 °C`

Questo significa che il notebook e utile come **evidenza che almeno un output osservativo locale ha un comportamento plausibile**.

Questa parte si puo integrare nel progetto non come codice, ma come:

- caso di riferimento per i test manuali
- confronto rapido prima/dopo ogni fix sugli script
- baseline per capire se stiamo reintroducendo il bug mensile

## Perche non possiamo ancora integrare il suo lavoro

Dalla descrizione del collega, il fix atteso sembrava essere:

- filtrare il mese corretto prima dell'aggregazione
- evitare di mescolare tutti i mesi dell'anno
- evitare di dare un peso al mese scelto dopo avere gia mediato anche gli altri mesi

Questa logica, pero, non compare nel notebook pushato.

Quindi al momento manca almeno una di queste cose:

1. codice vero nel notebook che mostri la logica corretta
2. una patch direttamente negli script
3. una spiegazione riproducibile con input/output di esempio

## Stato degli script rispetto al problema

Gli script oggi in repo sono ancora quelli della nostra pipeline corrente:

- [selected_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/selected_area_indicators.py)
- [minimum_indicator_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/minimum_indicator_utils.py)

Questi script:

- filtrano per intervallo mensile
- costruiscono l'area selezionata
- ritagliano i dataset climatici
- aggregano i risultati per mese

Quindi la cosa corretta da fare adesso **non** e integrare un notebook vuoto/duplicato, ma:

1. far pushare al collega il codice reale del fix
2. confrontare il fix con la logica attuale
3. integrare solo la parte utile
4. rilanciare i test sugli indicatori osservati
5. solo dopo, riprendere il forecast

## Valutazione di utilita per il progetto

Il notebook [selected_area.ipynb](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/notebooks/selected_area.ipynb) e:

- utile come notebook esplorativo
- utile come sanity check visivo
- non utile come sorgente della correzione
- non sufficiente per modificare gli script di produzione

Quindi la risposta sintetica e:

- **utile per esplorare**
- **non utile da integrare negli script cosi com'e**

## Come integrare davvero il lavoro del collega

La forma migliore del prossimo contributo del collega e una di queste:

### Opzione A: patch diretta sugli script

Modifica direttamente:

- [selected_area_indicators.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/selected_area_indicators.py)
- [minimum_indicator_utils.py](/Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo/scripts/minimum_indicator_utils.py)

Questo e il caso migliore, perche il diff e subito integrabile.

### Opzione B: notebook con celle chiare e output dimostrativi

Se vuole usare un notebook, allora il notebook deve contenere:

- codice completo del fix
- commenti che spiegano il bug
- confronto prima/dopo
- una o due query di controllo, per esempio `Madrid 2000-06`

Solo in questo modo il notebook diventa davvero integrabile.

## Comandi da eseguire in VS Code per controllare la situazione

### 1. Verificare che il notebook del collega sia presente

```bash
cd /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo
find notebooks -maxdepth 1 -type f | sort
```

### 2. Vedere la storia Git del notebook

```bash
git log --oneline -- notebooks/selected_area.ipynb
```

### 3. Verificare che i due script non siano stati toccati dal collega

```bash
git log --oneline -- scripts/selected_area_indicators.py scripts/minimum_indicator_utils.py
```

### 4. Verificare se `selected_area.ipynb` e identico al notebook esplorativo base

```bash
python3 - <<'PY'
import json
from pathlib import Path

p1 = Path('notebooks/01_dataset_exploration.ipynb')
p2 = Path('notebooks/selected_area.ipynb')
print(p1.read_text() == p2.read_text())
PY
```

Se stampa `True`, vuol dire che il notebook del collega e un duplicato del notebook base.

### 5. Quando il collega avra pushato il fix vero, controllare il diff

```bash
git pull
git diff HEAD~1 HEAD -- scripts/selected_area_indicators.py scripts/minimum_indicator_utils.py
```

## Comandi per i prossimi test manuali, senza eseguirli ora

Questi sono i comandi da lanciare dopo che avremo integrato un fix reale.

### Attivare l'ambiente del progetto

```bash
cd /Users/simonemercolino/Desktop/Università/Tesi_BioMap/TCBiomap/tesi_bioanalyst_repo
source scripts/activate_project.sh
```

### Testare un mese singolo su Madrid

```bash
python scripts/selected_area_indicators.py --city madrid --start 2000-06-01 --end 2000-06-01
```

### Testare un range di tre mesi su Madrid

```bash
python scripts/selected_area_indicators.py --city madrid --start 2000-05-01 --end 2000-07-01
```

### Testare Milano su un anno intero

```bash
python scripts/selected_area_indicators.py --city milano --start 2019-01-01 --end 2019-12-01
```

### Aprire gli output prodotti nel notebook esplorativo

```bash
jupyter notebook notebooks/01_dataset_exploration.ipynb
```

## Conclusione operativa

Ad oggi la situazione corretta e questa:

- il collega ha pushato un notebook
- il notebook non contiene il fix come codice
- il notebook contiene pero un output osservativo utile come baseline qualitativa
- gli script di produzione non erano stati modificati dal collega
- abbiamo integrato solo la parte utile della sua spiegazione tecnica: lo snapping delle specie alla griglia ERA5
- il resto delle modifiche descritte va considerato contesto locale di Jupyter, non codice da tenere nel backend

La prossima mossa giusta e chiedergli un push con:

- patch diretta sugli script
- oppure notebook con codice del fix vero e confronto dimostrativo

Solo dopo avra senso fare la vera integrazione nel backend BIOMAP.
