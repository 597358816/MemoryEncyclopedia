#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def count(path):
    with path.open(encoding="utf-8") as f:
        return sum(1 for x in f if x.strip())


def main():
    files = {
        "data": HERE / "data.jsonl",
        "tasks": HERE / "tasks.jsonl",
        "gold": HERE / "gold.jsonl",
        "metadata": HERE / "metadata.jsonl",
    }
    failed = False
    for name, path in files.items():
        if not path.exists():
            print(f"[!!] {name}: missing {path}")
            failed = True
            continue
        n = count(path)
        ok = n == 100
        print(f"{'[ok]' if ok else '[!!]'} {name}: {n}")
        failed |= not ok

    print(
        f"{'[ok]' if os.getenv('OPENAI_API_KEY') else '[--]'} OPENAI_API_KEY "
        f"{'set' if os.getenv('OPENAI_API_KEY') else 'not set (needed only for model-judge grading)'}"
    )
    has_inspect = importlib.util.find_spec("inspect_ai") is not None
    print(f"{'[ok]' if has_inspect else '[--]'} inspect-ai {'installed' if has_inspect else 'not installed'}")

    if failed:
        raise SystemExit(1)

    print("\n[ok] FrontierScience-Olympiad local data deployment is healthy")


if __name__ == "__main__":
    main()
