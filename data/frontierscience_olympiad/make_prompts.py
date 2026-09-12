#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--subject",
        choices=["all", "physics", "chemistry", "biology"],
        default="all",
    )
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()

    tasks = read_jsonl(HERE / "tasks.jsonl")
    if args.subject != "all":
        tasks = [x for x in tasks if x["subject"] == args.subject]

    out = args.output or (HERE / f"prompts_{args.subject}.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for t in tasks:
            # The official dataset already contains the complete solver instruction,
            # including the FINAL ANSWER formatting requirement. Do not append a
            # second prompt here.
            f.write(json.dumps({
                "id": t["id"],
                "subject": t["subject"],
                "prompt": t["problem"],
            }, ensure_ascii=False) + "\n")

    print(f"[ok] wrote {len(tasks)} prompts -> {out}")


if __name__ == "__main__":
    main()
