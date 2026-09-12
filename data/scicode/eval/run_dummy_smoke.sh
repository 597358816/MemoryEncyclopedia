#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

cd "$SCICODE_EXTERNAL/eval/inspect_ai"

H5="${SCICODE_H5:-$SCICODE_EXTERNAL/eval/data/test_data.h5}"
OUT="${SCICODE_OUTPUT_DIR:-$SCICODE_REPO_ROOT/jobs/scicode_dummy_smoke}"

mkdir -p "$OUT"

inspect eval scicode.py \
  --limit 1 \
  -T split=validation \
  -T "output_dir=$OUT" \
  -T "h5py_file=$H5" \
  -T with_background=False \
  -T mode=dummy
