#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

MODEL="${SCICODE_MODEL:?Set SCICODE_MODEL, e.g. openai/gpt-4o}"
SPLIT="${SCICODE_SPLIT:-test}"
WITH_BG="${SCICODE_WITH_BACKGROUND:-False}"
MAX_CONN="${SCICODE_MAX_CONNECTIONS:-2}"
TEMP="${SCICODE_TEMPERATURE:-0}"
OUT="${SCICODE_OUTPUT_DIR:-$SCICODE_REPO_ROOT/jobs/scicode_${SPLIT}}"
H5="${SCICODE_H5:-$SCICODE_EXTERNAL/eval/data/test_data.h5}"

cd "$SCICODE_EXTERNAL/eval/inspect_ai"
mkdir -p "$OUT"

ARGS=(
  inspect eval scicode.py
  --model "$MODEL"
  --temperature "$TEMP"
  --max-connections "$MAX_CONN"
  -T "split=$SPLIT"
  -T "output_dir=$OUT"
  -T "h5py_file=$H5"
  -T "with_background=$WITH_BG"
  -T mode=normal
)

if [[ -n "${SCICODE_LIMIT:-}" ]]; then
  ARGS+=(--limit "$SCICODE_LIMIT")
fi
if [[ -n "${SCICODE_MAX_TOKENS:-}" ]]; then
  ARGS+=(--max-tokens "$SCICODE_MAX_TOKENS")
fi

printf '[run]'
printf ' %q' "${ARGS[@]}"
printf '\n'
"${ARGS[@]}"
