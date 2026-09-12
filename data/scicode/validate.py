#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent

def load(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

tasks = load(BASE / "tasks.jsonl")
gold = load(BASE / "gold.jsonl")
meta = load(BASE / "metadata.jsonl")

errors = []

if len(tasks) != 80:
    errors.append(f"tasks count={len(tasks)}, expected 80")
if len(gold) != 80:
    errors.append(f"gold count={len(gold)}, expected 80")

split_counts = {}
for r in tasks:
    split_counts[r["split"]] = split_counts.get(r["split"], 0) + 1
if split_counts != {"validation": 15, "test": 65}:
    errors.append(f"split counts={split_counts}, expected validation=15/test=65")

# Strong model-input leak checks.
for i, r in enumerate(tasks):
    blob = json.dumps(r, ensure_ascii=False)
    for banned in ['"ground_truth_code"', '"test_cases"', '"general_solution"', '"general_tests"']:
        if banned in blob:
            errors.append(f"tasks.jsonl row {i} leaks {banned}")

# IDs should be unique within the 80-problem collection.
ids = [(r["split"], r["problem_id"]) for r in tasks]
if len(ids) != len(set(ids)):
    errors.append("duplicate (split, problem_id) pairs")

if errors:
    print("[FAIL]")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print("[ok] SciCode local views validate")
print("[ok] model input is tasks.jsonl; do NOT feed data.jsonl or gold.jsonl to the model")
