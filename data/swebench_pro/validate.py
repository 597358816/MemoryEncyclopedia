#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = 731


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    data = read_jsonl(HERE / "data.jsonl")
    tasks = read_jsonl(HERE / "tasks.jsonl")
    gold = read_jsonl(HERE / "gold.jsonl")
    meta = read_jsonl(HERE / "metadata.jsonl")
    raw = read_jsonl(HERE / "raw.jsonl")

    lengths = {len(data), len(tasks), len(gold), len(meta), len(raw)}
    if len(lengths) != 1:
        raise RuntimeError(
            f"row count mismatch: data={len(data)} tasks={len(tasks)} "
            f"gold={len(gold)} meta={len(meta)} raw={len(raw)}"
        )
    n = len(tasks)
    if n != EXPECTED:
        raise RuntimeError(f"expected pinned public count {EXPECTED}, got {n}")

    ids = [x["instance_id"] for x in tasks]
    if len(set(ids)) != n:
        raise RuntimeError("duplicate instance IDs")

    forbidden = {
        "patch", "test_patch", "fail_to_pass", "pass_to_pass",
        "selected_test_files_to_run", "before_repo_set_cmd"
    }
    for i, (d, t, g, m, r) in enumerate(zip(data, tasks, gold, meta, raw)):
        leaked = forbidden.intersection(t)
        if leaked:
            raise RuntimeError(f"task row {i}: evaluator-secret fields leaked: {sorted(leaked)}")
        if not (t["instance_id"] == g["instance_id"] == m["instance_id"] == r["instance_id"]):
            raise RuntimeError(f"row {i}: ID mismatch")
        if d["problem"] != t["problem_statement"]:
            raise RuntimeError(f"row {i}: problem mismatch")
        if d["answer"] != g["patch"]:
            raise RuntimeError(f"row {i}: gold patch mismatch")
        if not g["fail_to_pass"]:
            raise RuntimeError(f"row {i}: empty fail_to_pass")
        if not isinstance(g["pass_to_pass"], list):
            raise RuntimeError(f"row {i}: pass_to_pass must normalize to a list")

    print("[ok] SWE-bench Pro public deployment validated")
    print(f"[ok] tasks: {n}")
    print("[ok] no patch/test GT leaked into tasks.jsonl")
    print("[ok] official evaluator raw fields preserved")


if __name__ == "__main__":
    main()
