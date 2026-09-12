#!/usr/bin/env bash
# Cache routing for Terminal-Bench 2.0 / Harbor.
# Harbor currently uses ~/.cache/harbor, so we isolate HOME itself under VEPFS.
export TB2_CACHE_ROOT="${TB2_CACHE_ROOT:-/vepfs-mlp2/c20250203/250602012/cache/terminal_bench_2}"
export TB2_HARBOR_HOME="${TB2_HARBOR_HOME:-$TB2_CACHE_ROOT/home}"

mkdir -p \
  "$TB2_HARBOR_HOME" \
  "$TB2_CACHE_ROOT/uv" \
  "$TB2_CACHE_ROOT/pip" \
  "$TB2_CACHE_ROOT/tmp"

export HOME="$TB2_HARBOR_HOME"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$TB2_CACHE_ROOT/uv}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$TB2_CACHE_ROOT/pip}"
export TMPDIR="${TMPDIR:-$TB2_CACHE_ROOT/tmp}"
export TMP="${TMP:-$TMPDIR}"
export TEMP="${TEMP:-$TMPDIR}"
export PYTHONUNBUFFERED=1
