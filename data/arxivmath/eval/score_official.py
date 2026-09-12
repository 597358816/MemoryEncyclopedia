#!/usr/bin/env python3
"""
Score pre-generated ArXivMath responses with the official MathArena parser/grader.

Run this in the Python >=3.12 environment where the official `matharena`
repository has been installed with `pip install -e`.

Predictions JSONL must align row-for-row with data.jsonl and contain either:
    {"response": "full model response ending with \\boxed{...}"}
or:
    {"prediction": "final answer only"}

For `prediction`, this wrapper converts it to `\\boxed{prediction}` before
passing it to the official parser.

This reproduces the answer extraction / symbolic grading path. It does NOT
reproduce model sampling settings. For leaderboard-comparable generation, run
the official MathArena runner directly with the monthly competition configs.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from matharena.grader import extract_and_grade

HERE = Path(__file__).resolve().parents[1]

CONFIG = {
    "final_answer": True,
    "strict_parsing": False,
    "exact_match_parsing": False,
    "typed_delimited_answers": True,
}


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    ap.add_argument("--data", type=Path, default=HERE / "data.jsonl")
    ap.add_argument("--metadata", type=Path, default=HERE / "metadata.jsonl")
    args = ap.parse_args()

    gold = read_jsonl(args.data)
    meta = read_jsonl(args.metadata)
    pred = read_jsonl(args.predictions)

    if not (len(gold) == len(meta) == len(pred)):
        raise ValueError(
            f"row mismatch: gold={len(gold)} meta={len(meta)} predictions={len(pred)}"
        )

    details = []
    per_release = Counter()
    per_release_correct = Counter()

    for i, (g, m, p) in enumerate(zip(gold, meta, pred)):
        if "response" in p:
            response = str(p["response"])
        elif "prediction" in p:
            response = rf"\boxed{{{p['prediction']}}}"
        elif "answer" in p:
            response = rf"\boxed{{{p['answer']}}}"
        else:
            raise KeyError(f"row {i}: need response, prediction, or answer")

        messages = [
            {"role": "user", "content": g["problem"]},
            {"role": "assistant", "content": response},
        ]

        parsed, correct, warning = extract_and_grade(
            messages=messages,
            output_tokens=0,
            gold_answer=g["answer"],
            competition_config=CONFIG,
            problem={
                "problem_idx": m["problem_idx"],
                "problem": g["problem"],
                "answer": g["answer"],
            },
            debug_info=m["id"],
        )

        release = m["release"]
        per_release[release] += 1
        per_release_correct[release] += int(bool(correct))

        details.append({
            "index": i,
            "id": m["id"],
            "release": release,
            "gold_answer": g["answer"],
            "parsed_answer": None if parsed is None else str(parsed),
            "correct": bool(correct),
            "warning": warning,
        })

    out_path = args.predictions.with_suffix(args.predictions.suffix + ".graded.jsonl")
    with out_path.open("w", encoding="utf-8") as f:
        for x in details:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    total_correct = sum(per_release_correct.values())
    total = len(details)
    summary = {
        "total": total,
        "correct": total_correct,
        "accuracy": total_correct / total if total else 0.0,
        "per_release": {
            r: {
                "n": per_release[r],
                "correct": per_release_correct[r],
                "accuracy": per_release_correct[r] / per_release[r],
            }
            for r in sorted(per_release)
        },
        "note": (
            "Combined accuracy is a convenience aggregate over monthly releases. "
            "For official comparison, report each monthly release separately."
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[ok] details -> {out_path}")


if __name__ == "__main__":
    main()
