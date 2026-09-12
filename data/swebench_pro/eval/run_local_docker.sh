#!/usr/bin/env bash
set -euo pipefail

PATCHES="${1:?usage: run_local_docker.sh PATCHES.json OUTPUT_DIR [WORKERS]}"
OUTPUT="${2:?usage: run_local_docker.sh PATCHES.json OUTPUT_DIR [WORKERS]}"
WORKERS="${3:-4}"

# 假设你从 Memory_encyclopedia 仓库根目录执行这个脚本
PROJECT_ROOT="$(pwd)"

OFFICIAL="${SWEBENCH_PRO_OFFICIAL_DIR:-$PROJECT_ROOT/external/SWE-bench_Pro-os}"
RAW="${SWEBENCH_PRO_RAW:-$PROJECT_ROOT/data/swebench_pro/raw.jsonl}"

abs_path () {
  python - "$1" <<'PY'
import os
import sys
print(os.path.abspath(sys.argv[1]))
PY
}

# 在 cd 到官方 repo 之前，全部转成绝对路径
OFFICIAL="$(abs_path "$OFFICIAL")"
RAW="$(abs_path "$RAW")"
PATCHES="$(abs_path "$PATCHES")"
OUTPUT="$(abs_path "$OUTPUT")"

if [ ! -f "$OFFICIAL/swe_bench_pro_eval.py" ]; then
  echo "[error] missing evaluator: $OFFICIAL/swe_bench_pro_eval.py" >&2
  exit 1
fi

if [ ! -d "$OFFICIAL/dockerfiles/base_dockerfile" ]; then
  echo "[error] missing dockerfiles: $OFFICIAL/dockerfiles/base_dockerfile" >&2
  exit 1
fi

if [ ! -d "$OFFICIAL/run_scripts" ]; then
  echo "[error] missing run_scripts: $OFFICIAL/run_scripts" >&2
  exit 1
fi

if [ ! -f "$RAW" ]; then
  echo "[error] missing raw benchmark file: $RAW" >&2
  exit 1
fi

if [ ! -f "$PATCHES" ]; then
  echo "[error] missing patch file: $PATCHES" >&2
  exit 1
fi

mkdir -p "$OUTPUT"

docker info >/dev/null

# 关键：
# 官方 evaluator 内部使用 dockerfiles/... 的相对路径，
# 所以必须在 SWE-bench_Pro-os 目录下执行。
cd "$OFFICIAL"

python swe_bench_pro_eval.py \
  --raw_sample_path="$RAW" \
  --patch_path="$PATCHES" \
  --output_dir="$OUTPUT" \
  --scripts_dir="$OFFICIAL/run_scripts" \
  --num_workers="$WORKERS" \
  --dockerhub_username=jefzda \
  --use_local_docker \
  --block_network \
  --redo