#!/usr/bin/env bash
# Install the pre-commit hook for unix-like environments
set -euo pipefail
SRC="$(dirname "$0")/../.githooks/pre-commit"
DST="$(dirname "$0")/../.git/hooks/pre-commit"
echo "Installing pre-commit hook to $DST"
cp "$SRC" "$DST"
chmod +x "$DST"
echo "Installed. To configure git to use .githooks as hooks path instead, run:"
echo "  git config core.hooksPath .githooks"
