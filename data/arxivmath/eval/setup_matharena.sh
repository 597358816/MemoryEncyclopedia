#!/usr/bin/env bash
set -euo pipefail

# Run this inside a Python >=3.12 environment.
# Recommended:
#   conda create -n matharena python=3.12 -y
#   conda activate matharena
#
# Usage:
#   bash data/arxivmath/eval/setup_matharena.sh [target_dir]

TARGET="${1:-external/matharena}"

if [ -e "$TARGET" ]; then
  echo "[error] target already exists: $TARGET" >&2
  exit 1
fi

git clone https://github.com/eth-sri/matharena.git "$TARGET"
python -m pip install -e "$TARGET"

COMMIT="$(git -C "$TARGET" rev-parse HEAD)"
mkdir -p data/arxivmath/eval
printf '%s\n' "$COMMIT" > data/arxivmath/eval/MATHARENA_COMMIT.txt

echo "[ok] installed MathArena from commit: $COMMIT"
echo "[ok] recorded commit in data/arxivmath/eval/MATHARENA_COMMIT.txt"
