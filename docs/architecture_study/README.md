# BioMap architecture study deliverables

Questa cartella contiene i materiali di studio generati per ripassare l'architettura del progetto BioMap.

## FigJam

- Board unico con workflow osservativo e workflow previsionale:
  https://www.figma.com/board/2NUe3DSXLS7skDSzMaCnng

Il board e stato creato nel team Figma `simone's team` usando il plan key `team::1220365587835637773`.

## File locali

| File | Uso consigliato |
| --- | --- |
| `workflow_osservativo.mmd` | Sorgente Mermaid del workflow osservativo, modificabile e reimportabile in FigJam. |
| `workflow_previsionale.mmd` | Sorgente Mermaid del workflow previsionale, modificabile e reimportabile in FigJam. |
| `REPORT_PIPELINE_OSSERVATIVA.md` | Report tecnico dettagliato su dati reali, script osservativi, backend e frontend. |
| `REPORT_PIPELINE_PREVISIONALE.md` | Report tecnico dettagliato su BioAnalyst native, rollout, cache forecast, backend e frontend. |
| `dashboard_osservativa.html` | Dashboard tecnica standalone per ripassare velocemente la pipeline osservativa. |
| `dashboard_previsionale.html` | Dashboard tecnica standalone per ripassare velocemente la pipeline previsionale. |

## Ordine di studio

1. Apri il FigJam e guarda prima il workflow osservativo.
2. Leggi `dashboard_osservativa.html` per fissare i blocchi principali.
3. Leggi `REPORT_PIPELINE_OSSERVATIVA.md` per entrare nei dettagli di funzioni, endpoint e output.
4. Passa al workflow previsionale in FigJam.
5. Apri `dashboard_previsionale.html` per distinguere produzione offline e lettura online.
6. Leggi `REPORT_PIPELINE_PREVISIONALE.md`, soprattutto le sezioni su cache, rollout e limiti metodologici.

## Sorgente codice analizzata

- Worktree: `TCBiomap/tesi_bioanalyst_repo_native`
- Branch: `main`
- Ultimo commit rilevato: `4c25135`, `2026-06-22 17:07:44 +0200`
- Nota: la copia `native` e risultata la piu aggiornata rispetto alla copia Git base e alla copia CPU.
