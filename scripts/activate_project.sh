#!/usr/bin/env bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
  set +a
fi

# shellcheck disable=SC1091
source "$PROJECT_ROOT/.venv/bin/activate"

echo "Ambiente attivo."
echo "PROJECT_ROOT=$PROJECT_ROOT"
echo "BIOCUBE_DIR=${BIOCUBE_DIR:-non impostato}"
echo "BIOANALYST_MODEL_DIR=${BIOANALYST_MODEL_DIR:-non impostato}"
echo "PROJECT_OUTPUT_DIR=${PROJECT_OUTPUT_DIR:-non impostato}"
