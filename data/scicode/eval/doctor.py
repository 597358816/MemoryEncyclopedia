#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

root = Path(os.environ.get("SCICODE_REPO_ROOT", Path.cwd()))
external = Path(os.environ.get("SCICODE_EXTERNAL", root / "external" / "SciCode"))
data_root = Path(os.environ.get("SCICODE_DATA_ROOT", root / "data" / "scicode"))

errors = []

def ok(name, value):
    print(f"[ok] {name}: {value}")

def bad(name, value):
    print(f"[FAIL] {name}: {value}")
    errors.append(name)

if external.is_dir():
    ok("external repo", external)
else:
    bad("external repo", external)

for mod in ["scicode", "inspect_ai", "h5py", "numpy"]:
    if importlib.util.find_spec(mod):
        ok("python module", mod)
    else:
        bad("python module", mod)

official = data_root / "cache" / "official_hf"
for fname, expected in [("problems_dev.jsonl", 15), ("problems_test.jsonl", 65)]:
    p = official / fname
    if not p.exists():
        bad(fname, "missing")
        continue
    n = sum(1 for line in p.open() if line.strip())
    if n == expected:
        ok(fname, f"{n} rows")
    else:
        bad(fname, f"{n} rows, expected {expected}")

h5 = external / "eval" / "data" / "test_data.h5"
if h5.exists():
    h = hashlib.sha256()
    with h5.open("rb") as f:
        for chunk in iter(lambda: f.read(8 << 20), b""):
            h.update(chunk)
    got = h.hexdigest()
    expect = "48b0272a88b17dbd29777c217e1b4fb2b019b92e11cc2add847409db9541b890"
    if got == expect:
        ok("test_data.h5", f"sha256={got}")
    else:
        bad("test_data.h5", f"sha256={got}, expected={expect}")
else:
    bad("test_data.h5", "missing")

inspect_task = external / "eval" / "inspect_ai" / "scicode.py"
if inspect_task.exists():
    ok("official Inspect task", inspect_task)
else:
    bad("official Inspect task", inspect_task)

if errors:
    print(f"\n[FAIL] doctor found {len(errors)} issue(s): {', '.join(errors)}")
    sys.exit(1)
print("\n[ok] SciCode environment looks ready")
