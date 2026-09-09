#!/usr/bin/env bash
# One-click launcher (Linux / macOS CLI): installs dependencies, then starts
# the builder. On macOS, double-click run.command instead.
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

# Create an isolated virtual environment so we don't fight the system Python
# (modern macOS/Homebrew block system-wide pip installs — PEP 668).
VENV=".venv"
if [ ! -d "$VENV" ]; then
  echo "Creating virtual environment (first run only)..."
  "$PY" -m venv "$VENV"
fi
# Use the venv's interpreter from here on.
PY="$VENV/bin/python"

echo "Installing builder dependencies (first run only)..."
"$PY" -m pip install --upgrade pip >/dev/null
# The `builder` extra, not a second requirements list: the one that used to
# live here had drifted to no version floors at all. This also puts
# dims_builder, dims_case and dims_analysis on the path properly.
"$PY" -m pip install -e "../..[builder]"

echo "Starting DIMS Dashboard Builder..."
"$PY" -m dims_builder
