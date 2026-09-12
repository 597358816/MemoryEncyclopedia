#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load(name):
    p = ROOT / name
    with p.open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]

def main():
    tasks = load("tasks.jsonl")
    gold = load("gold.jsonl")
    data = load("data.jsonl")
    meta = load("metadata.jsonl")
    prompts = load("prompts.jsonl")

    lens = {len(tasks), len(gold), len(data), len(meta), len(prompts)}
    if len(lens) != 1:
        raise RuntimeError(
            f"row-count mismatch: tasks={len(tasks)} gold={len(gold)} "
            f"data={len(data)} meta={len(meta)} prompts={len(prompts)}"
        )
    if len(tasks) != 89:
        raise RuntimeError(f"expected 89 tasks, got {len(tasks)}")

    task_ids = [x["task_id"] for x in tasks]
    if len(set(task_ids)) != len(task_ids):
        raise RuntimeError("duplicate task_id in tasks.jsonl")

    if task_ids != [x["task_id"] for x in gold]:
        raise RuntimeError("tasks/gold task_id order mismatch")
    if task_ids != [x["task_id"] for x in meta]:
        raise RuntimeError("tasks/metadata task_id order mismatch")
    if task_ids != [x["task_id"] for x in prompts]:
        raise RuntimeError("tasks/prompts task_id order mismatch")

    forbidden = {
        "answer", "solution", "oracle_solution", "tests", "test_entrypoint",
        "verifier", "gold", "expected_reward"
    }
    for i, row in enumerate(tasks):
        bad = forbidden & set(row)
        if bad:
            raise RuntimeError(f"tasks row {i} leaks evaluator fields: {sorted(bad)}")
        if not row.get("problem"):
            raise RuntimeError(f"tasks row {i} empty problem")

    for i, row in enumerate(gold):
        if row.get("ground_truth_type") != "programmatic_verifier":
            raise RuntimeError(f"gold row {i} wrong GT type")
        if not row.get("oracle_solution"):
            raise RuntimeError(f"gold row {i} empty oracle")

    print("[ok] Terminal-Bench 2.0 materialization valid")
    print("[ok] 89 model-safe tasks")
    print("[ok] public oracle solutions/tests kept out of tasks.jsonl")

if __name__ == "__main__":
    main()
