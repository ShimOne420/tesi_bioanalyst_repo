# Collaborazione GitHub

Questo progetto e pensato per essere usato da piu persone.

## Regole base

- il codice va versionato con `git`
- il repository va pubblicato su `GitHub`
- ogni collaboratore deve poter fare:
  - `pull`
  - `commit`
  - `push`

## Cosa va su GitHub

- codice Python
- notebook
- README
- documentazione
- file di configurazione
- piccoli output utili

## Cosa non va su GitHub

- dataset pesanti
- pesi del modello
- `.venv`
- output grandi o temporanei

## Flusso consigliato

1. `git pull`
2. creare o aggiornare il proprio branch
3. fare modifiche piccole e chiare
4. fare `commit`
5. fare `push`
6. aprire `pull request` oppure integrare nel branch condiviso, a seconda della scelta del team

## Struttura minima del lavoro condiviso

- il repository GitHub contiene il progetto
- ciascuno ha il proprio dataset in locale o su storage dedicato
- i percorsi locali dei dati vengono gestiti con `.env`

## Regola importante

Gli script devono funzionare anche se il dataset si trova in percorsi diversi su computer diversi.

Per questo:

- mai scrivere path assoluti hardcoded dentro il codice
- usare variabili tipo:
  - `BIOCUBE_DIR`
  - `BIOANALYST_MODEL_DIR`
  - `PROJECT_OUTPUT_DIR`
