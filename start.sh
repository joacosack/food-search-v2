#!/bin/sh

set -e

PORT_VALUE=${PORT:-8000}

exec uvicorn server.main:app --host 0.0.0.0 --port "$PORT_VALUE"
