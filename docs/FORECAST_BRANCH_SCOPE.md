# Scope del branch `forecast-current-cpu`

Questo branch serve a conservare e validare la pipeline forecast attuale del progetto.

## Obiettivo del branch

- mantenere il forecast `adapter-first` attuale;
- fare benchmark e confronto su `CPU` e `CUDA`;
- usare questo ramo come baseline metodologica e tecnica.

## Cosa va qui

- backtest della pipeline attuale;
- report di validazione del forecast attuale;
- correzioni tecniche piccole che non cambiano la filosofia della pipeline;
- documentazione sui limiti e sui risultati della pipeline corrente.

## Cosa non va qui

- i workaround `MPS` non devono diventare la soluzione ufficiale di questo ramo;
- la riscrittura `BioAnalyst-native first` non va sviluppata qui;
- observed e UI non vanno modificati qui se non per bugfix strettamente necessari.

## Relazione con `main`

- `main` resta il progetto stabile da mostrare alla prof;
- questo branch non e il candidato finale da mergiare in `main`;
- serve soprattutto come termine di confronto contro il ramo `forecast-bioanalyst-native`.
