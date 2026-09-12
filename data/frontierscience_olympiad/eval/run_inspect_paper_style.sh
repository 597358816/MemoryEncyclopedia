#!/usr/bin/env bash
set -euo pipefail

MODEL="${1:?usage: run_inspect_paper_style.sh SOLVER_MODEL [GRADER_MODEL] [EPOCHS]}"
GRADER="${2:-openai/gpt-5}"
EPOCHS="${3:-20}"

if [ -z "${OPENAI_API_KEY:-}" ] && [[ "$GRADER" == openai/* ]]; then
  echo "[error] OPENAI_API_KEY is not set for grader $GRADER" >&2
  exit 1
fi

echo "[info] solver: $MODEL"
echo "[info] grader: $GRADER"
echo "[info] epochs: $EPOCHS"
echo "[info] paper Olympiad protocol uses 20 independent trials and GPT-5 high-effort judge."

inspect eval inspect_evals/frontierscience \
  --model "$MODEL" \
  -T format=olympic \
  -T grader_model="$GRADER" \
  --epochs "$EPOCHS"
