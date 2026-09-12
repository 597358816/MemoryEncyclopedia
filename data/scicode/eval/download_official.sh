#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/env.sh"

command -v hf >/dev/null 2>&1 || {
  python -m pip install -U "huggingface_hub[cli]"
}

mkdir -p "$SCICODE_DATA_ROOT/cache/official_hf"
mkdir -p "$SCICODE_EXTERNAL/eval/data"

echo "[1/3] official problem JSONL"
hf download SciCode1/SciCode \
  problems_dev.jsonl problems_test.jsonl \
  --repo-type dataset \
  --local-dir "$SCICODE_DATA_ROOT/cache/official_hf"

echo "[2/3] original numeric target HDF5 from public reproducibility mirror"
# Upstream distributes test_data.h5 through a Google Drive link. The HF file below
# is documented as the original SciCode numeric artifact and has a known SHA256.
hf download akshathmangudi/SciCode \
  raw/raw_ground.h5 \
  --repo-type dataset \
  --local-dir "$SCICODE_DATA_ROOT/cache/numeric_mirror"

SRC="$SCICODE_DATA_ROOT/cache/numeric_mirror/raw/raw_ground.h5"
DST="$SCICODE_EXTERNAL/eval/data/test_data.h5"
cp -f "$SRC" "$DST"

echo "[3/3] checksum"
python - "$DST" <<'PY'
import hashlib, pathlib, sys
p = pathlib.Path(sys.argv[1])
h = hashlib.sha256()
with p.open("rb") as f:
    for chunk in iter(lambda: f.read(8 << 20), b""):
        h.update(chunk)
got = h.hexdigest()
expect = "48b0272a88b17dbd29777c217e1b4fb2b019b92e11cc2add847409db9541b890"
print("file:", p)
print("size:", p.stat().st_size)
print("sha256:", got)
if got != expect:
    raise SystemExit(
        "SHA256 mismatch. Do not evaluate until the numeric GT artifact is verified."
    )
print("[ok] numeric GT checksum matches expected original artifact")
PY

echo "[ok] downloads complete"
