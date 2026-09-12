#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

python - <<'PY'
import sys
print("[python]", sys.version)
if sys.version_info[:2] not in {(3, 11), (3, 12)}:
    print("[warning] Upstream recommends Python 3.11. Python 3.11/3.12 are the tested targets for this wrapper.")
PY

mkdir -p "$(dirname "$LCB_EXTERNAL")"

if [[ ! -d "$LCB_EXTERNAL/.git" ]]; then
  echo "[clone] https://github.com/LiveCodeBench/LiveCodeBench.git"
  git clone https://github.com/LiveCodeBench/LiveCodeBench.git "$LCB_EXTERNAL"
else
  echo "[skip] existing repo: $LCB_EXTERNAL"
fi

REV="$(git -C "$LCB_EXTERNAL" rev-parse HEAD)"
echo "$REV" > "$LCB_DATA_ROOT/upstream_revision.txt"
echo "[revision] $REV"

unset PIP_INDEX_URL PIP_EXTRA_INDEX_URL || true
python -m pip install -U pip setuptools wheel -i https://pypi.org/simple

# Current upstream has an open issue for non-editable installs; use editable.
python -m pip install -e "$LCB_EXTERNAL" -i https://pypi.org/simple

# A known working datasets generation for the historical version_tag loader.
python -m pip install "datasets==3.6.0" "huggingface_hub>=0.30,<1.0" \
  -i https://pypi.org/simple

python - <<'PY'
import datasets, lcb_runner
print("[ok] datasets", datasets.__version__)
print("[ok] lcb_runner", lcb_runner.__file__)
PY
