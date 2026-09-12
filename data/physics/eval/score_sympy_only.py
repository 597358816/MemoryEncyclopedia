#!/usr/bin/env python3
"""
Fully local PHYSICS development scorer.

This is intentionally NOT claimed to be the official benchmark score. It:
- extracts all \\boxed{...} answers;
- tries normalized exact match;
- tries SymPy LaTeX equivalence;
- marks text / unparsable comparisons unresolved instead of calling an LLM.

Reported `lower_bound_accuracy` treats unresolved comparisons as incorrect.
Use this for cheap iteration, then use `score_official_hybrid.py` for final
results.
"""
from __future__ import annotations

import argparse
import json
import re
import signal
from collections import defaultdict
from pathlib import Path

from sympy import simplify, expand, trigsimp
from sympy.parsing.latex import parse_latex

HERE = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def extract_boxed_all(text):
    out = []
    i = 0
    marker = r"\boxed{"
    while True:
        j = text.find(marker, i)
        if j < 0:
            break
        start = j + len(marker)
        depth = 1
        p = start
        while p < len(text) and depth:
            if text[p] == "{" and (p == 0 or text[p-1] != "\\"):
                depth += 1
            elif text[p] == "}" and (p == 0 or text[p-1] != "\\"):
                depth -= 1
            p += 1
        if depth == 0:
            out.append(text[start:p-1])
            i = p
        else:
            break
    return out


def norm(x):
    return re.sub(r"\s+", "", str(x)).strip().rstrip(".")


def preprocess(x):
    x = str(x)
    x = re.sub(r"_\{.*?\}", "", x)
    x = re.sub(r"_\\?\w", "", x)
    x = x.replace(r"\left", "").replace(r"\right", "").replace(r"\cdot", "*")
    if r"\implies" in x:
        x = x.split(r"\implies")[-1].strip()
    if "=" in x:
        x = x.split("=")[-1].strip()
    return x


class Alarm(Exception):
    pass


def _alarm(signum, frame):
    raise Alarm()


def compare(a, b):
    if norm(a) == norm(b):
        return True, "normalized_exact"

    # Text-rich answers are exactly the class for which upstream falls back
    # to GPT-4o. Leave them unresolved locally.
    if r"\text" in a or r"\text" in b:
        return None, "text_unresolved"

    try:
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(10)
        ea = trigsimp(expand(parse_latex(preprocess(a))))
        eb = trigsimp(expand(parse_latex(preprocess(b))))
        ok = simplify(ea - eb) == 0 or ea.equals(eb)
        signal.alarm(0)
        return bool(ok), "sympy"
    except Exception:
        try:
            signal.alarm(0)
        except Exception:
            pass
        return None, "parse_unresolved"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    ap.add_argument(
        "--split",
        choices=["test", "validation", "hard", "textonly", "all"],
        default="test",
    )
    args = ap.parse_args()

    tasks = read_jsonl(HERE / "splits" / args.split / "tasks.jsonl")
    gold = read_jsonl(HERE / "splits" / args.split / "gold.jsonl")
    pred = read_jsonl(args.predictions)
    if not (len(tasks) == len(gold) == len(pred)):
        raise ValueError(
            f"row mismatch tasks={len(tasks)} gold={len(gold)} pred={len(pred)}"
        )

    details = []
    unresolved_comparisons = 0
    total_comparisons = 0
    domain_scores = defaultdict(list)

    for i, (task, gt, p) in enumerate(zip(tasks, gold, pred)):
        if "id" in p and p["id"] != task["id"]:
            raise ValueError(f"row {i}: id mismatch")

        if "response" in p:
            response = str(p["response"])
        elif "llm_answers" in p:
            response = str(p["llm_answers"])
        elif "prediction" in p:
            response = rf"\boxed{{{p['prediction']}}}"
        else:
            raise KeyError(f"row {i}: need response/llm_answers/prediction")

        extracted = extract_boxed_all(response)
        correct = 0
        comp_details = []

        for ans in extracted:
            matched = False
            for ref in gt["answer"]:
                result, method = compare(ans, ref)
                total_comparisons += 1
                if result is None:
                    unresolved_comparisons += 1
                comp_details.append({
                    "prediction": ans,
                    "reference": ref,
                    "result": result,
                    "method": method,
                })
                if result is True:
                    correct += 1
                    matched = True
                    break
            if matched:
                continue

        score = correct / len(extracted) if extracted else 0.0
        domain_scores[task["domain"]].append(score)
        details.append({
            "id": task["id"],
            "domain": task["domain"],
            "accuracy_lower_bound": score,
            "extracted_answers": extracted,
            "comparisons": comp_details,
        })

    overall = (
        sum(x["accuracy_lower_bound"] for x in details) / len(details)
        if details else 0.0
    )
    metrics = {
        "split": args.split,
        "n": len(details),
        "lower_bound_accuracy": overall,
        "comparison_unresolved_fraction": (
            unresolved_comparisons / total_comparisons if total_comparisons else 0.0
        ),
        "by_domain": {
            d: {
                "n": len(scores),
                "lower_bound_accuracy": sum(scores) / len(scores) if scores else 0.0,
            }
            for d, scores in sorted(domain_scores.items())
        },
        "warning": (
            "Development-only symbolic lower bound. "
            "Use official hybrid scorer for paper/leaderboard results."
        ),
    }

    out = args.predictions.with_suffix(args.predictions.suffix + ".sympy.graded.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for x in details:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    mout = args.predictions.with_suffix(args.predictions.suffix + ".sympy.metrics.json")
    mout.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"[ok] details -> {out}")
    print(f"[ok] metrics -> {mout}")


if __name__ == "__main__":
    main()
