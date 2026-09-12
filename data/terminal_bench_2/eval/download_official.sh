#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT/data/terminal_bench_2/eval/env.sh"

OUT="${1:-$ROOT/external/terminal-bench-2}"
mkdir -p "$ROOT/external"

echo "[download] official Harbor dataset: terminal-bench/terminal-bench-2"
echo "[output]   $OUT"

rm -rf "$OUT.tmp"
mkdir -p "$OUT.tmp"

if harbor download "terminal-bench/terminal-bench-2" --output-dir "$OUT.tmp"; then
  :
elif harbor datasets download "terminal-bench@2.0" -o "$OUT.tmp"; then
  :
else
  echo "[error] Harbor dataset download failed with both current and legacy CLI forms." >&2
  exit 1
fi

rm -rf "$OUT"
mv "$OUT.tmp" "$OUT"

N="$(find "$OUT" -type f -name task.toml | wc -l | tr -d ' ')"
echo "[done] task.toml count=$N"
if [ "$N" -ne 89 ]; then
  echo "[warning] expected Terminal-Bench 2.0 to contain 89 tasks, got $N" >&2
fi
