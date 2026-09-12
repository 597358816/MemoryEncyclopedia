#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:?usage: run_official_vllm.sh MODEL_PATH OUTPUT_DIR [MAX_LINES]}"
OUTPUT="${2:?usage: run_official_vllm.sh MODEL_PATH OUTPUT_DIR [MAX_LINES]}"
MAX_LINES="${3:-1000000}"
OFFICIAL="${PHYSICS_OFFICIAL_DIR:-external/Physics}"

if [ ! -f "$OFFICIAL/offline_evaluation/get_answer.py" ]; then
  echo "[error] missing official repo; run setup_official.sh first" >&2
  exit 1
fi

DATASETS=(
  "$OFFICIAL/PHYSICS/PHYSICS-test/atomic_dataset_test.jsonl"
  "$OFFICIAL/PHYSICS/PHYSICS-test/electro_dataset_test.jsonl"
  "$OFFICIAL/PHYSICS/PHYSICS-test/mechanics_dataset_test.jsonl"
  "$OFFICIAL/PHYSICS/PHYSICS-test/optics_dataset_test.jsonl"
  "$OFFICIAL/PHYSICS/PHYSICS-test/quantum_dataset_test.jsonl"
  "$OFFICIAL/PHYSICS/PHYSICS-test/statistics_dataset_test.jsonl"
)

python "$OFFICIAL/offline_evaluation/get_answer.py" \
  --model_name "$MODEL" \
  --download_dir "${HF_HOME:-.cache/huggingface}" \
  --output_dir "$OUTPUT" \
  --max_lines "$MAX_LINES" \
  --dataset_list "${DATASETS[@]}"
