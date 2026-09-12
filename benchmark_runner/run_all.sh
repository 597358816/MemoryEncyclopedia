#!/usr/bin/env bash
set -euo pipefail

REPO="${REPO:-$(pwd)}"
RUN_DIR="${RUN_DIR:-runs/qwen3_4b_baseline}"
SOLVER_MODEL="${SOLVER_MODEL:-/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-4B/}"
JUDGE_MODEL="${JUDGE_MODEL:-/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-14B/}"
SOLVER_TP="${SOLVER_TP:-1}"
JUDGE_TP="${JUDGE_TP:-1}"

exec python -m benchmark_runner.router \
  --repo "$REPO" \
  --run-dir "$RUN_DIR" \
  --solver-model "$SOLVER_MODEL" \
  --judge-model "$JUDGE_MODEL" \
  --solver-tp "$SOLVER_TP" \
  --judge-tp "$JUDGE_TP" \
  --resume \
  "$@"
