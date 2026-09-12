#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-external/Physics}"

if [ -e "$TARGET" ]; then
  echo "[error] target already exists: $TARGET" >&2
  exit 1
fi

git clone https://github.com/yale-nlp/Physics.git "$TARGET"
COMMIT="$(git -C "$TARGET" rev-parse HEAD)"

mkdir -p data/physics/eval
printf '%s\n' "$COMMIT" > data/physics/eval/OFFICIAL_COMMIT.txt

echo "[ok] cloned official PHYSICS repo -> $TARGET"
echo "[ok] commit -> $COMMIT"
echo "[next] python data/physics/build.py"
