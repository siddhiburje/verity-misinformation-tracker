#!/usr/bin/env bash
# Verity — start the server (run ./setup.sh first if you haven't).
set -e
cd "$(dirname "$0")/backend"
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi
echo "Starting Verity on http://localhost:5000 ..."
python3 app.py
