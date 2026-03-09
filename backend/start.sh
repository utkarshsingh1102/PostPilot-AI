#!/bin/bash
set -e

# Render injects $PORT; fall back to 8000 locally.
PORT="${PORT:-8000}"

echo "Starting PostPilot-AI on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
