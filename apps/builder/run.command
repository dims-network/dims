#!/usr/bin/env bash
# macOS double-click launcher. Finder runs .command files in Terminal.
#
# It execs run.sh rather than repeating it: the two were byte-identical apart
# from this comment, including the PEP 668 venv handling, which is not a thing
# to maintain twice.
exec "$(dirname "$0")/run.sh" "$@"
