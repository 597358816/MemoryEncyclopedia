#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT/data/terminal_bench_2/eval/env.sh"

SOURCE="${TB2_SOURCE:-$ROOT/external/terminal-bench-2}"
SLUG="${1:-make-mips-interpreter}"

TASK_TOML="$(find "$SOURCE" -type f -path "*/${SLUG}/task.toml" | head -n 1 || true)"
if [ -z "$TASK_TOML" ]; then
  echo "[error] task not found: $SLUG under $SOURCE" >&2
  exit 1
fi
TASK_DIR="$(dirname "$TASK_TOML")"

echo "[smoke] task=$SLUG"
echo "[path]  $TASK_DIR"
echo "[note]  oracle runs public solution/solve.sh, then the official verifier"
harbor run -p "$TASK_DIR" -a oracle
