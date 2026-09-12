#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source "$ROOT/data/terminal_bench_2/eval/env.sh"

echo "[cache] TB2_CACHE_ROOT=$TB2_CACHE_ROOT"
echo "[cache] HOME=$HOME"
echo "[cache] Harbor cache will be: $HOME/.cache/harbor"
echo

if command -v harbor >/dev/null 2>&1; then
  echo "[ok] harbor already installed: $(command -v harbor)"
  harbor --version || true
else
  echo "[install] Harbor from official PyPI"
  python -m pip install -i https://pypi.org/simple --upgrade harbor
fi

echo
echo "[check] Docker"
docker version >/dev/null
echo "[ok] docker client/daemon reachable"

echo
echo "[check] Harbor"
harbor --version || harbor --help >/dev/null
echo "[ok] Harbor ready"
