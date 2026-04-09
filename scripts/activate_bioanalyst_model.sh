#!/usr/bin/env zsh

# Risolviamo la root del progetto anche se lo script viene lanciato da un'altra cartella.
SCRIPT_DIR="$(cd "$(dirname "${(%):-%N}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SHARED_MAIN_ROOT="$(cd "${PROJECT_ROOT}/../tesi_bioanalyst_repo" 2>/dev/null && pwd)"

VENV_ROOT="${PROJECT_ROOT}"
if [[ ! -f "${VENV_ROOT}/.venv-bioanalyst/bin/activate" && -f "${SHARED_MAIN_ROOT}/.venv-bioanalyst/bin/activate" ]]; then
  VENV_ROOT="${SHARED_MAIN_ROOT}"
fi

ENV_ROOT="${PROJECT_ROOT}"
if [[ ! -f "${ENV_ROOT}/.env" && -f "${SHARED_MAIN_ROOT}/.env" ]]; then
  ENV_ROOT="${SHARED_MAIN_ROOT}"
fi

BFM_ROOT="${PROJECT_ROOT}/external/bfm-model"
if [[ ! -d "${BFM_ROOT}" && -d "${SHARED_MAIN_ROOT}/external/bfm-model" ]]; then
  BFM_ROOT="${SHARED_MAIN_ROOT}/external/bfm-model"
fi

# Attiviamo l'ambiente Python dedicato al modello BioAnalyst.
if [[ ! -f "${VENV_ROOT}/.venv-bioanalyst/bin/activate" ]]; then
  echo "Ambiente modello non trovato: ${PROJECT_ROOT}/.venv-bioanalyst"
  echo "Crea prima l'ambiente dedicato del modello."
  return 1
fi
source "${VENV_ROOT}/.venv-bioanalyst/bin/activate"

# Carichiamo le variabili da .env senza stampare informazioni sensibili.
if [[ -f "${ENV_ROOT}/.env" ]]; then
  set -a
  source "${ENV_ROOT}/.env"
  set +a
fi

# Esportiamo il path del repo ufficiale clonato localmente.
export BFM_MODEL_REPO="${BFM_ROOT}"

# Aggiungiamo il repo ufficiale al PYTHONPATH come fallback, utile nei test locali.
if [[ -z "${PYTHONPATH}" ]]; then
  export PYTHONPATH="${BFM_MODEL_REPO}"
else
  export PYTHONPATH="${BFM_MODEL_REPO}:${PYTHONPATH}"
fi

# Mostriamo un riepilogo rapido del setup modello attivo.
echo "Ambiente BioAnalyst attivo"
echo "PROJECT_ROOT=${PROJECT_ROOT}"
echo "VENV_ROOT=${VENV_ROOT}"
echo "ENV_ROOT=${ENV_ROOT}"
echo "BFM_MODEL_REPO=${BFM_MODEL_REPO}"
echo "BIOANALYST_MODEL_DIR=${BIOANALYST_MODEL_DIR:-non impostato}"
