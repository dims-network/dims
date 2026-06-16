#!/usr/bin/env bash
# macOS double-click launcher: installs dependencies, then starts the builder.
# (Finder runs .command files in Terminal; double-click this one.)
set -e
cd "$(dirname "$0")"

# Find a Python 3 interpreter.
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo
  echo "Python 3 is not installed."
  echo "Install it (free) from https://www.python.org/downloads/ then run this again."
  read -r -p "Press Enter to close..." _ || true
  exit 1
fi

echo "Installing builder dependencies (first run only)..."
"$PY" -m pip install -r requirements.txt

echo "Starting DIMS Dashboard Builder..."
"$PY" builder.py
