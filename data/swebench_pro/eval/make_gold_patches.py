#!/usr/bin/env python3
"""
Create evaluator-format gold patches from public GT.

Useful only as a harness smoke test. Never expose these patches to the agent.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--output", type=Path, default=Path("swebench_pro_gold_patches.json"))
    args = ap.parse_args()

    gold = read_jsonl(HERE / "gold.jsonl")
    if args.limit is not None:
        gold = gold[:args.limit]

    rows = [
        {"instance_id": x["instance_id"], "patch": x["patch"], "prefix": "gold"}
        for x in gold
    ]
    args.output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] gold patches: {len(rows)} -> {args.output}")


if __name__ == "__main__":
    main()
