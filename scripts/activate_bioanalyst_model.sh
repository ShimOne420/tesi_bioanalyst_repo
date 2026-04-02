#!/usr/bin/env zsh

# Risolviamo la root del progetto anche se lo script viene lanciato da un'altra cartella.
SCRIPT_DIR="$(cd "$(dirname "${(%):-%N}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Attiviamo l'ambiente Python dedicato al modello BioAnalyst.
if [[ ! -f "${PROJECT_ROOT}/.venv-bioanalyst/bin/activate" ]]; then
  echo "Ambiente modello non trovato: ${PROJECT_ROOT}/.venv-bioanalyst"
  echo "Crea prima l'ambiente dedicato del modello."
  return 1
fi
source "${PROJECT_ROOT}/.venv-bioanalyst/bin/activate"

# Carichiamo le variabili da .env senza stampare informazioni sensibili.
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -a
  source "${PROJECT_ROOT}/.env"
  set +a
fi

# Esportiamo il path del repo ufficiale clonato localmente.
export BFM_MODEL_REPO="${PROJECT_ROOT}/external/bfm-model"

# Aggiungiamo il repo ufficiale al PYTHONPATH come fallback, utile nei test locali.
if [[ -z "${PYTHONPATH}" ]]; then
  export PYTHONPATH="${BFM_MODEL_REPO}"
else
  export PYTHONPATH="${BFM_MODEL_REPO}:${PYTHONPATH}"
fi

# Mostriamo un riepilogo rapido del setup modello attivo.
echo "Ambiente BioAnalyst attivo"
echo "PROJECT_ROOT=${PROJECT_ROOT}"
echo "BFM_MODEL_REPO=${BFM_MODEL_REPO}"
echo "BIOANALYST_MODEL_DIR=${BIOANALYST_MODEL_DIR:-non impostato}"
