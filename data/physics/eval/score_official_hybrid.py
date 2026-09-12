#!/usr/bin/env python3
"""
Score externally generated PHYSICS responses through the official benchmark's
hybrid equivalence implementation.

Requires:
    export OPENAI_API_KEY=...

This wrapper imports `extract_boxed.py` and `equation_equivilancy.py` from the
cloned official yale-nlp/Physics repository. The latter uses SymPy first and
falls back to GPT-4o.

Prediction JSONL is aligned row-by-row with the selected split. Accepted forms:
    {"response": "reasoning ... \\boxed{...}"}
    {"llm_answers": "..."}
    {"prediction": "final answer"}  # one-box convenience only

For multi-part PHYSICS tasks, preserve the full model response so all boxed
answers can be extracted.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO_ROOT = HERE.parents[1]


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def flatten_extracted(x):
    if not x:
        return []
    if isinstance(x, list) and x and isinstance(x[0], list):
        return [item for sub in x for item in sub]
    return x if isinstance(x, list) else [x]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    ap.add_argument(
        "--split",
        choices=["test", "validation", "hard", "textonly", "all"],
        default="test",
    )
    ap.add_argument(
        "--official-repo",
        type=Path,
        default=REPO_ROOT / "external" / "Physics",
    )
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is required for the official PHYSICS hybrid scorer "
            "because unresolved/text answers fall back to GPT-4o."
        )

    official = args.official_repo.resolve()
    if not (official / "equation_equivilancy.py").exists():
        raise FileNotFoundError(
            f"Missing official checkout at {official}; run setup_official.sh first."
        )

    sys.path.insert(0, str(official))
    import extract_boxed
    import equation_equivilancy

    tasks = read_jsonl(HERE / "splits" / args.split / "tasks.jsonl")
    gold = read_jsonl(HERE / "splits" / args.split / "gold.jsonl")
    pred = read_jsonl(args.predictions)

    if not (len(tasks) == len(gold) == len(pred)):
        raise ValueError(
            f"row mismatch: tasks={len(tasks)} gold={len(gold)} predictions={len(pred)}"
        )

    details = []
    domain_scores = defaultdict(list)

    for i, (task, gt, p) in enumerate(zip(tasks, gold, pred)):
        if "id" in p and p["id"] != task["id"]:
            raise ValueError(
                f"row {i}: prediction id={p['id']} expected={task['id']}"
            )

        if "response" in p:
            response = str(p["response"])
        elif "llm_answers" in p:
            response = str(p["llm_answers"])
        elif "prediction" in p:
            response = rf"\boxed{{{p['prediction']}}}"
        else:
            raise KeyError(f"row {i}: need response/llm_answers/prediction")

        extracted = extract_boxed.extract_final_answer_allform(
            response, answer_type="list"
        )
        extracted = flatten_extracted(extracted)

        correct_count = 0
        comparisons = []
        for ans in extracted:
            matched = False
            for ref in gt["answer"]:
                eq = equation_equivilancy.is_equiv(ans, ref, verbose=False)
                comparisons.append(eq)
                if eq.get("final_result") is True:
                    correct_count += 1
                    matched = True
                    break
            if matched:
                continue

        problem_accuracy = (
            correct_count / len(extracted) if extracted else 0.0
        )
        domain_scores[task["domain"]].append(problem_accuracy)

        details.append({
            "id": task["id"],
            "domain": task["domain"],
            "extracted_answers": extracted,
            "gold_answers": gt["answer"],
            "correct_count": correct_count,
            "num_extracted": len(extracted),
            "accuracy": problem_accuracy,
            "equivalency_results": comparisons,
        })

        print(
            f"[{i+1}/{len(tasks)}] {task['id']} accuracy={problem_accuracy:.3f}",
            flush=True,
        )

    overall = sum(x["accuracy"] for x in details) / len(details) if details else 0.0
    metrics = {
        "split": args.split,
        "n": len(details),
        "accuracy": overall,
        "by_domain": {
            d: {
                "n": len(scores),
                "accuracy": sum(scores) / len(scores) if scores else 0.0,
            }
            for d, scores in sorted(domain_scores.items())
        },
        "scorer": "official yale-nlp/Physics SymPy + GPT-4o hybrid logic",
    }

    out = args.predictions.with_suffix(args.predictions.suffix + ".graded.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for x in details:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    mout = args.predictions.with_suffix(args.predictions.suffix + ".metrics.json")
    mout.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"[ok] details -> {out}")
    print(f"[ok] metrics -> {mout}")


if __name__ == "__main__":
    main()
