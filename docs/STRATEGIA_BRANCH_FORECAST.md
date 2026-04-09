# Strategia Branch Forecast

Questa guida definisce come tenere separati:

- il progetto `stabile` da mostrare alla prof;
- la pipeline forecast attuale `CPU/CUDA`;
- il nuovo forecast `BioAnalyst-native first`.

## Rami ufficiali

- `main`
  ramo stabile del progetto.
  Deve contenere:
  - osservazione;
  - backend API;
  - UI funzionante;
  - documentazione operativa stabile.

- `forecast-current-cpu`
  ramo storico e tecnico del forecast attuale.
  Serve per:
  - benchmark;
  - confronto con CUDA;
  - baseline metodologica.

- `forecast-bioanalyst-native`
  ramo di sviluppo del nuovo forecast.
  Qui il lavoro va organizzato come:
  - input nativi o quasi nativi del modello;
  - runner BioAnalyst;
  - aggregazione finale in indicatori BIOMAP.

## Stato MPS locale

Le modifiche MPS locali non definiscono la struttura ufficiale dei rami forecast.

Per questo motivo sono state salvate come stato temporaneo locale tramite stash:

- `mps-temp-local-backup-2026-04-09`

Questo backup serve solo come riferimento tecnico e non va trattato come ramo ufficiale del progetto.

## Worktree consigliate

Per evitare errori, il lavoro quotidiano va fatto con cartelle separate:

- `tesi_bioanalyst_repo`
  lavora su `main`

- `tesi_bioanalyst_repo_cpu`
  lavora su `forecast-current-cpu`

- `tesi_bioanalyst_repo_native`
  lavora su `forecast-bioanalyst-native`

Comandi tipici:

```bash
git worktree add ../tesi_bioanalyst_repo_cpu forecast-current-cpu
git worktree add ../tesi_bioanalyst_repo_native forecast-bioanalyst-native
```

## Regole GitHub

- `main` resta il branch di default.
- Su `main` non si fa push diretto.
- I fix stabili di observed/UI/backend vanno in PR verso `main`.
- I test e benchmark della pipeline attuale vanno in `forecast-current-cpu`.
- Il nuovo sviluppo forecast va in `forecast-bioanalyst-native`.
- Non si fanno merge automatici tra i due rami forecast.
- Solo `forecast-bioanalyst-native`, se validato, potra essere integrato in `main`.

## Regole per il collega

Prima di iniziare il lavoro bisogna sempre decidere in quale ramo si lavora:

- `main` per demo stabile e progetto osservativo;
- `forecast-current-cpu` per forecast attuale;
- `forecast-bioanalyst-native` per nuova architettura forecast.

Ogni PR deve avere come target solo il ramo corretto per quel tipo di lavoro.
