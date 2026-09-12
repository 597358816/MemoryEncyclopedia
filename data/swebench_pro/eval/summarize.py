#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eval_results", type=Path, help="official output_dir/eval_results.json")
    args = ap.parse_args()

    results = json.loads(args.eval_results.read_text(encoding="utf-8"))
    tasks = {x["instance_id"]: x for x in read_jsonl(HERE / "tasks.jsonl")}

    by_repo = defaultdict(lambda: {"resolved": 0, "n": 0})
    by_lang = defaultdict(lambda: {"resolved": 0, "n": 0})
    resolved = 0

    for iid, ok in results.items():
        if iid not in tasks:
            continue
        t = tasks[iid]
        v = bool(ok)
        resolved += int(v)
        by_repo[t["repo"]]["n"] += 1
        by_repo[t["repo"]]["resolved"] += int(v)
        lang = str(t["repo_language"])
        by_lang[lang]["n"] += 1
        by_lang[lang]["resolved"] += int(v)

    n = len(results)
    summary = {
        "evaluated": n,
        "resolved": resolved,
        "resolved_rate": resolved / n if n else 0.0,
        "by_repo": {
            k: {**v, "resolved_rate": v["resolved"] / v["n"]}
            for k, v in sorted(by_repo.items())
        },
        "by_language": {
            k: {**v, "resolved_rate": v["resolved"] / v["n"]}
            for k, v in sorted(by_lang.items())
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
