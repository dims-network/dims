#!/usr/bin/env bash
# Double-click launcher (macOS / Linux): install deps then start the builder.
set -e
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
echo "Installing builder dependencies..."
"$PY" -m pip install -r requirements.txt
echo "Starting DIMS Dashboard Builder..."
"$PY" builder.py
