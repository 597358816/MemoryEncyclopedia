#!/usr/bin/env python3
"""
Normalize model/agent outputs into the JSON list expected by the official
SWE-bench Pro evaluator.

Accepted aligned JSONL row forms:
  {"instance_id":"...","patch":"diff --git ..."}
  {"instance_id":"...","model_patch":"diff --git ..."}
  {"instance_id":"...","response":"diff --git ..."}

The recommended workflow is for your agent to produce `git diff` after it
finishes each repository task.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def extract_patch(text):
    text = str(text).strip()
    blocks = re.findall(r"```(?:diff|patch)?\s*(.*?)```", text, flags=re.S | re.I)
    candidates = blocks if blocks else [text]
    for candidate in reversed(candidates):
        pos = candidate.find("diff --git ")
        if pos >= 0:
            return candidate[pos:].strip()
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--output", type=Path, default=Path("swebench_pro_patches.json"))
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()

    tasks = read_jsonl(HERE / "tasks.jsonl")
    task_ids = [x["instance_id"] for x in tasks]
    task_set = set(task_ids)
    preds = read_jsonl(args.predictions)

    by_id = {}
    for i, p in enumerate(preds):
        iid = p.get("instance_id")
        if iid is None:
            if len(preds) == len(tasks):
                iid = task_ids[i]
            else:
                raise ValueError(f"row {i}: missing instance_id in a non-aligned/partial file")
        if iid not in task_set:
            raise ValueError(f"row {i}: unknown instance_id {iid}")
        if iid in by_id:
            raise ValueError(f"duplicate prediction for {iid}")

        raw_patch = p.get("patch", p.get("model_patch", p.get("response")))
        if raw_patch is None:
            raise KeyError(f"{iid}: need patch/model_patch/response")
        patch = extract_patch(raw_patch)
        by_id[iid] = patch

    if not args.allow_partial and set(by_id) != task_set:
        missing = task_set - set(by_id)
        raise ValueError(
            f"expected all {len(task_set)} public tasks, got {len(by_id)}; "
            f"missing {len(missing)}. Use --allow-partial for development subsets."
        )

    rows = [
        {"instance_id": iid, "patch": by_id[iid], "prefix": args.prefix}
        for iid in task_ids if iid in by_id
    ]

    args.output.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[ok] patches: {len(rows)} -> {args.output}")


if __name__ == "__main__":
    main()
