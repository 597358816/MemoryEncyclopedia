#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-external/SWE-bench_Pro-os}"

if [ -e "$TARGET" ]; then
  echo "[error] target already exists: $TARGET" >&2
  exit 1
fi

git clone --recurse-submodules https://github.com/scaleapi/SWE-bench_Pro-os.git "$TARGET"
COMMIT="$(git -C "$TARGET" rev-parse HEAD)"

mkdir -p data/swebench_pro/eval
printf '%s\n' "$COMMIT" > data/swebench_pro/eval/OFFICIAL_COMMIT.txt

echo "[ok] official evaluator -> $TARGET"
echo "[ok] commit -> $COMMIT"
echo
echo "Install evaluator dependencies in a dedicated environment:"
echo "  pip install -r $TARGET/requirements.txt"
echo
echo "Local Docker evaluation also requires:"
echo "  docker version"
echo "  docker info"
