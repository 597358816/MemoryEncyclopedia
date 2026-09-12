#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

OUT="$LCB_DATA_ROOT/predictions/dummy_${LCB_SMOKE_RELEASE}.json"

python "$HERE/make_dummy_outputs.py" \
  --config "$LCB_SMOKE_RELEASE" \
  --output "$OUT"

echo "[smoke] official custom evaluator on fine-grained $LCB_SMOKE_RELEASE"
echo "[note] expected score is near/at zero; success criterion is evaluator completion."

cd "$LCB_EXTERNAL"
python -m lcb_runner.runner.custom_evaluator \
  --scenario codegeneration \
  --release_version "$LCB_SMOKE_RELEASE" \
  --n 1 \
  --num_process_evaluate "$LCB_EVAL_PROCESSES" \
  --timeout "$LCB_EVAL_TIMEOUT" \
  --custom_output_file "$OUT"
