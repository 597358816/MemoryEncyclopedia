#!/usr/bin/env python3
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent

def load_jsonl(p):
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]

tasks = load_jsonl(BASE / "tasks.jsonl")
gold = load_jsonl(BASE / "gold.jsonl")
meta = load_jsonl(BASE / "metadata.jsonl")
manifest = json.loads((BASE / "MANIFEST.json").read_text())

errors = []
if manifest.get("release") == "release_v6" and len(tasks) != 1055:
    errors.append(f"release_v6 task count={len(tasks)}, expected 1055")
if len(gold) != len(tasks) or len(meta) != len(tasks):
    errors.append("tasks/gold/metadata row count mismatch")

ids = [x["question_id"] for x in tasks]
if len(ids) != len(set(ids)):
    errors.append("duplicate question_id")

# Strong leak guard: model-safe task rows must not expose tests.
for i, row in enumerate(tasks):
    s = json.dumps(row, ensure_ascii=False)
    for banned in ["public_test_cases", "private_test_cases"]:
        if banned in s:
            errors.append(f"tasks row {i} leaks {banned}")

if errors:
    print("[FAIL]")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print(f"[ok] {len(tasks)} model-safe LiveCodeBench tasks")
print("[ok] no public/private test cases in tasks.jsonl")
print("[note] data.jsonl and gold.jsonl are NOT model input")
