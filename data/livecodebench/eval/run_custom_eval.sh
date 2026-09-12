#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

INPUT="${1:?Usage: run_custom_eval.sh path/to/custom_outputs.json}"
INPUT="$(python -c 'import os,sys; print(os.path.abspath(sys.argv[1]))' "$INPUT")"

test -f "$INPUT" || { echo "[error] missing $INPUT" >&2; exit 2; }

cd "$LCB_EXTERNAL"

echo "[eval] release=$LCB_FORMAL_RELEASE"
echo "[eval] predictions=$INPUT"
echo "[eval] processes=$LCB_EVAL_PROCESSES timeout=$LCB_EVAL_TIMEOUT"

python -m lcb_runner.runner.custom_evaluator \
  --scenario codegeneration \
  --release_version "$LCB_FORMAL_RELEASE" \
  --n 1 \
  --num_process_evaluate "$LCB_EVAL_PROCESSES" \
  --timeout "$LCB_EVAL_TIMEOUT" \
  --custom_output_file "$INPUT"
