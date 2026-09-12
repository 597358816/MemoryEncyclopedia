#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="${REPO_ROOT:-$(pwd)}"
cd "$REPO_ROOT"
JUDGE_MODEL="${JUDGE_MODEL:-/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-14B/}"
JUDGE_BACKEND="${JUDGE_BACKEND:-vllm}"
JUDGE_TP="${JUDGE_TP:-1}"
JUDGE_BATCH_SIZE="${JUDGE_BATCH_SIZE:-32}"
INPUT="${1:?Usage: run_judge.sh INPUT.jsonl OUTPUT.jsonl [BENCHMARK]}"
OUTPUT="${2:?Usage: run_judge.sh INPUT.jsonl OUTPUT.jsonl [BENCHMARK]}"
BENCHMARK="${3:-}"
ARGS=(python -m benchmark_runner.llm_judge.judge
  --input "$INPUT" --output "$OUTPUT"
  --model "$JUDGE_MODEL" --backend "$JUDGE_BACKEND"
  --tensor-parallel-size "$JUDGE_TP" --batch-size "$JUDGE_BATCH_SIZE"
  --id-key item_id --problem-key problem --candidate-key candidate
  --reference-key reference --rubric-key rubric --resume)
if [[ -n "$BENCHMARK" ]]; then ARGS+=(--benchmark "$BENCHMARK"); fi
printf '[run]'; printf ' %q' "${ARGS[@]}"; printf '\n'
"${ARGS[@]}"
