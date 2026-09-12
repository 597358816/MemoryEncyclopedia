#!/usr/bin/env python3
"""
Cheap fully-local development scorer for FrontierScience-Olympiad.

This is NOT the paper scorer. The paper uses GPT-5 at high reasoning effort as
a semantic equivalence judge.

Local behavior:
- extract the last `FINAL ANSWER...` portion when present;
- normalized exact match;
- single-number comparison after one-decimal rounding;
- conservative SymPy equivalence for LaTeX-like expressions;
- conservative normalized text match;
- otherwise mark the comparison unresolved.

`lower_bound_accuracy` treats unresolved items as incorrect.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from pathlib import Path

from sympy import simplify
from sympy.parsing.latex import parse_latex

HERE = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def extract_final(response: str) -> str:
    matches = list(re.finditer(r"(?im)^\s*FINAL\s+ANSWER\s*:?\s*(.*)$", response))
    if matches:
        tail = response[matches[-1].start():]
        first = re.sub(r"(?im)^\s*FINAL\s+ANSWER\s*:?\s*", "", tail, count=1)
        return first.strip()
    return response.strip()


def norm_text(x: str) -> str:
    x = html.unescape(str(x))
    x = x.replace("`", "")
    x = re.sub(r"\\\(|\\\)|\\\[|\\\]", "", x)
    x = re.sub(r"\s+", " ", x).strip().casefold()
    x = x.rstrip(" .;'\"")
    return x


def numeric_values(x: str):
    # Conservative: only use this path when the cleaned answer contains exactly
    # one ordinary/scientific-notation number.
    s = html.unescape(x).replace("×", "x")
    vals = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?(?:\s*(?:[eE]|x\s*10\^?)\s*[-+]?\d+)?", s)
    parsed = []
    for v in vals:
        q = re.sub(r"\s+", "", v)
        try:
            if re.search(r"x10\^?", q, re.I):
                base, exp = re.split(r"x10\^?", q, flags=re.I)
                parsed.append(float(base) * (10 ** int(exp)))
            else:
                parsed.append(float(q))
        except Exception:
            pass
    return parsed


def latex_clean(x: str) -> str:
    x = html.unescape(x)
    x = x.replace("`", "")
    x = re.sub(r"\\\(|\\\)|\\\[|\\\]", "", x)
    # Drop common text/unit wrappers for symbolic attempts.
    x = re.sub(r"\\(?:mathrm|text)\{[^{}]*\}", "", x)
    return x.strip()


def compare(pred: str, ref: str):
    pn, rn = norm_text(pred), norm_text(ref)
    if pn == rn:
        return True, "normalized_exact"

    pnums, rnums = numeric_values(pred), numeric_values(ref)
    if len(pnums) == len(rnums) == 1:
        # Paper judge prompt explicitly allows equivalence under 1-decimal-place
        # rounding (example: 6.69 vs 6.7).
        if round(pnums[0], 1) == round(rnums[0], 1):
            return True, "one_decimal_numeric"

    # Try symbolic math only when neither side looks like a chemistry/entity tag.
    taggy = any(tok in (pred + ref).lower() for tok in ("<inchi>", "<smiles>", "<iupac>"))
    if not taggy:
        try:
            a = parse_latex(latex_clean(pred))
            b = parse_latex(latex_clean(ref))
            if simplify(a - b) == 0 or a.equals(b):
                return True, "sympy"
        except Exception:
            pass

    # Conservative phrase normalization: exact after punctuation removal.
    pphrase = re.sub(r"[^a-z0-9]+", " ", pn).strip()
    rphrase = re.sub(r"[^a-z0-9]+", " ", rn).strip()
    if pphrase and pphrase == rphrase:
        return True, "normalized_phrase"

    return None, "unresolved"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    args = ap.parse_args()

    tasks = read_jsonl(HERE / "tasks.jsonl")
    gold = read_jsonl(HERE / "gold.jsonl")
    pred = read_jsonl(args.predictions)
    if not (len(tasks) == len(gold) == len(pred) == 100):
        raise ValueError(
            f"need exactly 100 aligned rows: tasks={len(tasks)} gold={len(gold)} pred={len(pred)}"
        )

    details = []
    by_subject = defaultdict(lambda: {"correct": 0, "n": 0, "unresolved": 0})
    correct = unresolved = 0

    for i, (t, g, p) in enumerate(zip(tasks, gold, pred)):
        if "id" in p and p["id"] != t["id"]:
            raise ValueError(f"row {i}: id mismatch")

        response = p.get("response", p.get("prediction", p.get("answer")))
        if response is None:
            raise KeyError(f"row {i}: need response/prediction/answer")

        attempted = extract_final(str(response))
        result, method = compare(attempted, g["answer"])

        is_correct = result is True
        is_unresolved = result is None
        correct += int(is_correct)
        unresolved += int(is_unresolved)

        s = t["subject"]
        by_subject[s]["n"] += 1
        by_subject[s]["correct"] += int(is_correct)
        by_subject[s]["unresolved"] += int(is_unresolved)

        details.append({
            "id": t["id"],
            "subject": s,
            "attempted_answer": attempted,
            "reference_answer": g["answer"],
            "correct_lower_bound": is_correct,
            "unresolved": is_unresolved,
            "method": method,
        })

    metrics = {
        "n": 100,
        "correct_lower_bound": correct,
        "lower_bound_accuracy": correct / 100,
        "unresolved": unresolved,
        "unresolved_fraction": unresolved / 100,
        "by_subject": {
            s: {
                "n": d["n"],
                "lower_bound_accuracy": d["correct"] / d["n"],
                "unresolved_fraction": d["unresolved"] / d["n"],
            }
            for s, d in sorted(by_subject.items())
        },
        "warning": "Development-only scorer; paper evaluation uses a GPT-5 high-effort judge.",
    }

    out = args.predictions.with_suffix(args.predictions.suffix + ".local.graded.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for x in details:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    mout = args.predictions.with_suffix(args.predictions.suffix + ".local.metrics.json")
    mout.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"[ok] details -> {out}")
    print(f"[ok] metrics -> {mout}")


if __name__ == "__main__":
    main()
