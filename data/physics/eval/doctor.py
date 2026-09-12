#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO_ROOT = HERE.parents[1]


def count(path):
    with path.open(encoding="utf-8") as f:
        return sum(1 for x in f if x.strip())


def main():
    checks = [
        (HERE / "data.jsonl", 1000),
        (HERE / "tasks.jsonl", 1000),
        (HERE / "gold.jsonl", 1000),
        (HERE / "splits/validation/data.jsonl", 297),
        (HERE / "splits/all/data.jsonl", 1297),
    ]

    failed = False
    for path, expected in checks:
        if not path.exists():
            print(f"[!!] missing {path}")
            failed = True
            continue
        n = count(path)
        ok = n == expected
        print(f"{'[ok]' if ok else '[!!]'} {path}: {n} (expected {expected})")
        failed |= not ok

    official = REPO_ROOT / "external" / "Physics"
    print(f"{'[ok]' if official.exists() else '[!!]'} official repo: {official}")
    print(
        f"{'[ok]' if os.getenv('OPENAI_API_KEY') else '[--]'} OPENAI_API_KEY "
        f"{'set' if os.getenv('OPENAI_API_KEY') else 'not set (only needed for official hybrid grading)'}"
    )

    if failed:
        raise SystemExit(1)

    print("\n[ok] PHYSICS data deployment is healthy")


if __name__ == "__main__":
    main()
