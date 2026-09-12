#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT/data/terminal_bench_2/eval/env.sh"

: "${AGENT_IMPORT_PATH:?Set AGENT_IMPORT_PATH, e.g. mypkg.myagent:MyAgent}"
: "${MODEL:?Set MODEL}"
N="${N_CONCURRENT:-4}"

harbor run \
  -d terminal-bench/terminal-bench-2 \
  --agent-import-path "$AGENT_IMPORT_PATH" \
  -m "$MODEL" \
  -n "$N" \
  "$@"
