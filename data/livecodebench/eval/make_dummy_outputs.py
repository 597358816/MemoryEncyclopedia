#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os
from pathlib import Path
from datasets import load_dataset

ap = argparse.ArgumentParser()
ap.add_argument("--config", default=os.environ.get("LCB_SMOKE_RELEASE", "v6"))
ap.add_argument("--output", required=True)
args = ap.parse_args()

ds = load_dataset(
    "livecodebench/code_generation_lite",
    args.config,
    split="test",
    cache_dir=os.environ.get("HF_DATASETS_CACHE"),
)

# Deliberately wrong but syntactically valid code; this tests the official execution
# and scoring pipeline without requiring a model.
rows = [
    {"question_id": r["question_id"], "code_list": ["pass\n"]}
    for r in ds
]
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
print(f"[ok] wrote {len(rows)} dummy outputs for {args.config}: {args.output}")
