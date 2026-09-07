#!/usr/bin/env bash
#
# Integrate the latest DIMS dashboard template into the builder's bundled copy.
#
# The builder ships a full copy of the dashboard template under `template/` so
# end users need neither git nor a network connection. That copy is tracked as a
# git *subtree* of the upstream template repo:
#
#     https://github.com/dims-network/DIMS_dashboard_template
#
# Workflow: a contributor adds a feature to the template repo and opens a PR;
# once it's merged to `main`, an admin runs this script to pull those changes
# into `template/`, then reviews and pushes the builder repo.
#
# Usage:
#     scripts/update-template.sh [remote-url] [branch]
#
# Defaults: the dims-network template repo, branch `main`.
set -euo pipefail

PREFIX="template"
REMOTE_URL="${1:-https://github.com/dims-network/DIMS_dashboard_template.git}"
BRANCH="${2:-main}"

# Run from the builder repo root regardless of where the script is invoked.
cd "$(dirname "$0")/.."

if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: working tree is not clean — commit or stash changes first." >&2
  exit 1
fi

echo "Pulling '$BRANCH' from $REMOTE_URL into '$PREFIX/' (squashed)..."
git subtree pull --prefix="$PREFIX" "$REMOTE_URL" "$BRANCH" --squash

echo
echo "Template updated. Review the changes, then push the builder repo:"
echo "    git log --stat -1"
echo "    git push"
