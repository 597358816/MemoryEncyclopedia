#!/usr/bin/env python3
from __future__ import annotations
import importlib
import json
import os
from pathlib import Path
import sys

root = Path(os.environ.get("LCB_REPO_ROOT", Path.cwd()))
external = Path(os.environ.get("LCB_EXTERNAL", root / "external" / "LiveCodeBench"))
data_root = Path(os.environ.get("LCB_DATA_ROOT", root / "data" / "livecodebench"))
errors = []

def good(k, v):
    print(f"[ok] {k}: {v}")
def bad(k, v):
    print(f"[FAIL] {k}: {v}")
    errors.append(k)

if external.is_dir():
    good("upstream repo", external)
else:
    bad("upstream repo", external)

for mod in ["datasets", "huggingface_hub", "lcb_runner", "torch", "numpy"]:
    try:
        m = importlib.import_module(mod)
        good("module", f"{mod} {getattr(m, '__version__', '')}")
    except Exception as e:
        bad("module", f"{mod}: {e}")

mf = data_root / "MANIFEST.json"
if mf.exists():
    x = json.loads(mf.read_text())
    good("manifest", f"{x.get('release')} count={x.get('count')}")
    if x.get("release") == "release_v6" and x.get("count") != 1055:
        bad("release_v6 count", x.get("count"))
else:
    print("[note] formal MANIFEST.json not built yet")

ce = external / "lcb_runner" / "runner" / "custom_evaluator.py"
if ce.exists():
    good("custom evaluator", ce)
else:
    bad("custom evaluator", ce)

if errors:
    sys.exit(1)
print("[ok] LiveCodeBench environment looks ready")
