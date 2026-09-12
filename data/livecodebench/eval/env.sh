#!/usr/bin/env bash
# Source this file from the Memory_encyclopedia repository root.
LCB_REPO_ROOT="${LCB_REPO_ROOT:-$(pwd)}"
export LCB_REPO_ROOT

export LCB_EXTERNAL="${LCB_EXTERNAL:-$LCB_REPO_ROOT/external/LiveCodeBench}"
export LCB_DATA_ROOT="${LCB_DATA_ROOT:-$LCB_REPO_ROOT/data/livecodebench}"
export LCB_CACHE_ROOT="${LCB_CACHE_ROOT:-/vepfs-mlp2/c20250203/250602012/cache/livecodebench}"

export HF_HOME="${HF_HOME:-$LCB_CACHE_ROOT/huggingface}"
export HF_DATASETS_CACHE="${HF_DATASETS_CACHE:-$HF_HOME/datasets}"
export HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-$HF_HOME/hub}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$LCB_CACHE_ROOT/pip}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$LCB_CACHE_ROOT/xdg}"
export TMPDIR="${TMPDIR:-$LCB_CACHE_ROOT/tmp}"

export LCB_FORMAL_RELEASE="${LCB_FORMAL_RELEASE:-release_v6}"
export LCB_SMOKE_RELEASE="${LCB_SMOKE_RELEASE:-v6}"
export LCB_EVAL_PROCESSES="${LCB_EVAL_PROCESSES:-4}"
export LCB_EVAL_TIMEOUT="${LCB_EVAL_TIMEOUT:-6}"

# Narrow compatibility shim for the upstream version_tag dataset call.
LCB_COMPAT_DIR="$LCB_DATA_ROOT/eval/compat"
export LCB_COMPAT_DIR
export PYTHONPATH="$LCB_COMPAT_DIR:$LCB_EXTERNAL${PYTHONPATH:+:$PYTHONPATH}"

mkdir -p \
  "$LCB_CACHE_ROOT" "$HF_HOME" "$HF_DATASETS_CACHE" \
  "$PIP_CACHE_DIR" "$XDG_CACHE_HOME" "$TMPDIR" \
  "$LCB_DATA_ROOT/cache" "$LCB_DATA_ROOT/predictions"
