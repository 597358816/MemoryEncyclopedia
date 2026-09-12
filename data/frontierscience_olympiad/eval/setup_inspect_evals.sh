#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-external/inspect_evals}"

if [ -e "$TARGET" ]; then
  echo "[error] target already exists: $TARGET" >&2
  exit 1
fi

git clone https://github.com/UKGovernmentBEIS/inspect_evals.git "$TARGET"
python -m pip install -e "$TARGET"

COMMIT="$(git -C "$TARGET" rev-parse HEAD)"
mkdir -p data/frontierscience_olympiad/eval
printf '%s\n' "$COMMIT" > data/frontierscience_olympiad/eval/INSPECT_EVALS_COMMIT.txt

echo "[ok] Inspect Evals installed -> $TARGET"
echo "[ok] commit -> $COMMIT"
echo "[note] Its FrontierScience implementation uses the paper's Olympiad judge prompt."
