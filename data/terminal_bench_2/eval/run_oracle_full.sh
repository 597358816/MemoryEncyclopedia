#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT/data/terminal_bench_2/eval/env.sh"
N="${N_CONCURRENT:-4}"

echo "[run] Terminal-Bench 2.0 full 89-task oracle validation"
echo "[run] concurrency=$N"
harbor run -d terminal-bench/terminal-bench-2 -a oracle -n "$N" "$@"
