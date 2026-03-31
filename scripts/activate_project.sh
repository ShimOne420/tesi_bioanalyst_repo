#!/usr/bin/env bash

# Risolviamo il path dello script anche quando viene eseguito con `source` da zsh in VS Code.
if [ -n "${ZSH_VERSION:-}" ]; then
  SCRIPT_PATH="${(%):-%N}"
elif [ -n "${BASH_VERSION:-}" ]; then
  SCRIPT_PATH="${BASH_SOURCE[0]}"
else
  SCRIPT_PATH="$0"
fi

# Ricaviamo la root del progetto partendo dalla cartella `scripts`.
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"

# Carichiamo le variabili locali dal file `.env` se presente.
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

# Attiviamo il virtual environment del progetto.
# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"

# Stampiamo un riepilogo utile per capire subito se il setup locale e corretto.
echo "Ambiente attivo."
echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "BIOCUBE_DIR=${BIOCUBE_DIR:-non impostato}"
echo "BIOANALYST_MODEL_DIR=${BIOANALYST_MODEL_DIR:-non impostato}"
echo "PROJECT_OUTPUT_DIR=${PROJECT_OUTPUT_DIR:-non impostato}"
