#!/usr/bin/env python3
"""
Create model-ready JSONL prompts from data.jsonl.

Output:
    {"id": "...", "release": "...", "prompt": "..."}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

INSTRUCTION_LONG = (
    "You are given a difficult question. Your task is to solve the problem.\n"
    "The question is written in such a way that it solely requires you to find "
    "the final answer. Make sure to follow the additional formatting instructions "
    "if they are provided in the question.\n"
    "Put the final answer you find within \\\\boxed{{}}."
)

INSTRUCTION_SHORT = (
    "You are given a difficult question. Your task is to solve the problem.\n"
    "Put the final answer you find within \\\\boxed{{}}."
)


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=HERE / "prompts.jsonl")
    args = ap.parse_args()

    data = read_jsonl(HERE / "data.jsonl")
    meta = read_jsonl(HERE / "metadata.jsonl")

    with args.output.open("w", encoding="utf-8") as f:
        for d, m in zip(data, meta):
            # Official configs used the longer wording for Dec/Jan/Feb and the
            # shorter wording for Mar/Apr/May. Preserve that distinction.
            instruction = INSTRUCTION_LONG if m["release"] in {"2025-12", "2026-01", "2026-02"} else INSTRUCTION_SHORT
            prompt = instruction + "\n\n" + d["problem"]
            f.write(json.dumps(
                {"id": m["id"], "release": m["release"], "prompt": prompt},
                ensure_ascii=False
            ) + "\n")

    print(f"[ok] prompts -> {args.output}")


if __name__ == "__main__":
    main()
