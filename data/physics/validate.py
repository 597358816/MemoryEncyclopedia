#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    data = read_jsonl(HERE / "data.jsonl")
    tasks = read_jsonl(HERE / "tasks.jsonl")
    gold = read_jsonl(HERE / "gold.jsonl")
    meta = read_jsonl(HERE / "metadata.jsonl")

    if not (len(data) == len(tasks) == len(gold) == len(meta) == 1000):
        raise RuntimeError(
            f"canonical test expected 1000: "
            f"data={len(data)} tasks={len(tasks)} gold={len(gold)} meta={len(meta)}"
        )

    ids = [x["id"] for x in tasks]
    if len(set(ids)) != 1000:
        raise RuntimeError("duplicate canonical test IDs")

    for i, (d, t, g, m) in enumerate(zip(data, tasks, gold, meta)):
        if set(d) != {"problem", "answer"}:
            raise RuntimeError(f"row {i}: data schema must be exactly problem/answer")
        if not isinstance(d["answer"], list) or not d["answer"]:
            raise RuntimeError(f"row {i}: PHYSICS answer must be a non-empty list")
        if d["problem"] != t["problem"]:
            raise RuntimeError(f"row {i}: data/tasks problem mismatch")
        if d["answer"] != g["answer"]:
            raise RuntimeError(f"row {i}: data/gold answer mismatch")
        if not (t["id"] == g["id"] == m["id"]):
            raise RuntimeError(f"row {i}: id mismatch")

    manifest = json.loads((HERE / "MANIFEST.json").read_text(encoding="utf-8"))
    if manifest["splits"]["validation"]["count"] != 297:
        raise RuntimeError("validation count is not 297")
    if manifest["splits"]["all"]["count"] != 1297:
        raise RuntimeError("full count is not 1297")

    domains = Counter(m["domain"] for m in meta)
    graph_count = sum(int(m["has_graph"]) for m in meta)

    print("[ok] PHYSICS deployment validated")
    print("[ok] canonical test: 1000")
    print("[ok] validation: 297")
    print("[ok] all: 1297")
    print(f"[info] multimodal test tasks with graphs: {graph_count}")
    print("[info] test domain counts:")
    for k, v in sorted(domains.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
