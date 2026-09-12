#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT/data/terminal_bench_2/eval/env.sh"

: "${AGENT:?Set AGENT, e.g. claude-code or terminus-2}"
: "${MODEL:?Set MODEL, e.g. provider/model-name}"
N="${N_CONCURRENT:-4}"

echo "[run] dataset=terminal-bench/terminal-bench-2"
echo "[run] agent=$AGENT"
echo "[run] model=$MODEL"
echo "[run] concurrency=$N"

harbor run \
  -d terminal-bench/terminal-bench-2 \
  -a "$AGENT" \
  -m "$MODEL" \
  -n "$N" \
  "$@"
