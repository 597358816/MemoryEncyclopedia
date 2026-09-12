#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

SYSTEM = (
    "Solve the advanced physics problem step by step. "
    "Place each final answer in a LaTeX \\\\boxed{...} expression."
)


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--split",
        choices=["test", "validation", "hard", "textonly", "all"],
        default="test",
    )
    ap.add_argument(
        "--drop-graph-tasks",
        action="store_true",
        help="Exclude tasks whose official record has a non-empty graphs field.",
    )
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    path = HERE / "splits" / args.split / "tasks.jsonl"
    tasks = read_jsonl(path)
    if args.drop_graph_tasks:
        tasks = [x for x in tasks if not x.get("graphs")]

    out = args.output or (HERE / f"prompts_{args.split}.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps({
                "id": t["id"],
                "domain": t["domain"],
                "system": SYSTEM,
                "problem": t["problem"],
                # Preserve upstream graph payload for a VLM-aware runner.
                "graphs": t.get("graphs"),
            }, ensure_ascii=False) + "\n")

    print(f"[ok] wrote {len(tasks)} prompts -> {out}")


if __name__ == "__main__":
    main()
