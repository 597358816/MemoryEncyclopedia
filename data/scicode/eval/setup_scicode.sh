#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

mkdir -p "$(dirname "$SCICODE_EXTERNAL")"

if [[ ! -d "$SCICODE_EXTERNAL/.git" ]]; then
  echo "[clone] official SciCode"
  git clone https://github.com/scicode-bench/SciCode.git "$SCICODE_EXTERNAL"
else
  echo "[skip] repo already exists: $SCICODE_EXTERNAL"
fi

REV="$(git -C "$SCICODE_EXTERNAL" rev-parse HEAD)"
echo "$REV" > "$SCICODE_DATA_ROOT/upstream_revision.txt"
echo "[revision] $REV"

python -m pip install -U pip
python -m pip install -e "$SCICODE_EXTERNAL"

# The official integration requires inspect_ai; installing the project may already
# provide it, but keep this check explicit.
python - <<'PY'
import importlib.util, subprocess, sys
if importlib.util.find_spec("inspect_ai") is None:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "inspect-ai"])
print("[ok] inspect_ai importable")
PY

echo "[ok] SciCode setup complete"
