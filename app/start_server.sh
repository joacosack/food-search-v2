#!/bin/bash
# Script para iniciar el servidor con configuración de IA

# Configurar variables de entorno
export GROQ_API_KEY=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
export LLM_PROVIDER=groq
export LLM_MODEL=llama-3.3-70b-versatile

# Activar entorno virtual
source venv/bin/activate

# Iniciar servidor
uvicorn server.main:app --host 0.0.0.0 --port 8000
