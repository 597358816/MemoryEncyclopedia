#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = 100


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    data = read_jsonl(HERE / "data.jsonl")
    tasks = read_jsonl(HERE / "tasks.jsonl")
    gold = read_jsonl(HERE / "gold.jsonl")
    meta = read_jsonl(HERE / "metadata.jsonl")

    if not (len(data) == len(tasks) == len(gold) == len(meta) == EXPECTED):
        raise RuntimeError(
            f"expected {EXPECTED}: data={len(data)} tasks={len(tasks)} "
            f"gold={len(gold)} metadata={len(meta)}"
        )

    ids = [x["id"] for x in tasks]
    if len(set(ids)) != EXPECTED:
        raise RuntimeError("task IDs are not unique")

    for i, (d, t, g, m) in enumerate(zip(data, tasks, gold, meta)):
        if set(d) != {"problem", "answer"}:
            raise RuntimeError(f"row {i}: data schema must be exactly problem/answer")
        if d["problem"] != t["problem"]:
            raise RuntimeError(f"row {i}: data/tasks problem mismatch")
        if d["answer"] != g["answer"]:
            raise RuntimeError(f"row {i}: data/gold answer mismatch")
        if not (t["id"] == g["id"] == m["id"]):
            raise RuntimeError(f"row {i}: ID mismatch")
        if "FINAL ANSWER" not in t["problem"]:
            raise RuntimeError(
                f"row {i}: expected official FINAL ANSWER formatting instruction in problem"
            )
        if t["subject"] not in {"physics", "chemistry", "biology"}:
            raise RuntimeError(f"row {i}: bad subject")

    counts = Counter(x["subject"] for x in tasks)
    print("[ok] FrontierScience-Olympiad validated")
    print("[ok] total: 100")
    for subject, n in sorted(counts.items()):
        print(f"  {subject}: {n}")


if __name__ == "__main__":
    main()
