#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env.local"

# Cargar variables de entorno si existe .env.local (ignorado por git)
if [[ -f "${ENV_FILE}" ]]; then
  echo "Cargando configuración desde ${ENV_FILE}"
  set -o allexport
  source "${ENV_FILE}"
  set +o allexport
fi

if [[ "${LLM_PROVIDER:-}" == "groq" && -z "${GROQ_API_KEY:-}" ]]; then
  echo "Error: GROQ_API_KEY no está definido. Configurá app/.env.local con tus credenciales." >&2
  exit 1
fi

# Activar entorno virtual
if [[ -f "${SCRIPT_DIR}/venv/bin/activate" ]]; then
  source "${SCRIPT_DIR}/venv/bin/activate"
else
  echo "Error: no se encontró el entorno virtual en ${SCRIPT_DIR}/venv. Crealo con 'python -m venv venv'." >&2
  exit 1
fi

# Iniciar servidor
uvicorn server.main:app --host 0.0.0.0 --port 8000
