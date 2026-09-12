#!/usr/bin/env python3
"""
Paper-faithful model-judge scorer for FrontierScience-Olympiad.

The FrontierScience paper uses GPT-5 with high reasoning effort to judge
semantic equivalence between the attempted response and the public short
reference answer. This adapter follows that criterion but intentionally uses a
compact paraphrased judge instruction rather than embedding the paper's
verbatim Appendix-B prompt.

For exact paper-prompt reproduction, use the Inspect Evals integration provided
by `setup_inspect_evals.sh`.

Input modes:
1) one trial/problem:
   {"id":"...","response":"... FINAL ANSWER ..."}
2) multiple independent trials/problem:
   {"id":"...","responses":["...", "...", ...]}

The paper reports Olympiad accuracy averaged over 20 independent trials.
It does NOT use majority vote.

This script can make many paid API calls. It refuses to submit unless
`--confirm-api-calls` is supplied.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
from collections import defaultdict
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parents[1]


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def judge_one(model, effort, problem, reference, attempted):
    client = OpenAI()
    instruction = (
        "Grade whether an attempted answer to a science-olympiad problem is "
        "fully equivalent to the reference answer. Be strict but fair. Account "
        "for algebraic equivalence, reasonable one-decimal rounding, equivalent "
        "units, synonymous chemical identities/formulas, and equivalent named "
        "entities or methods. End with exactly VERDICT: CORRECT or "
        "VERDICT: INCORRECT."
    )
    payload = (
        f"PROBLEM:\n{problem}\n\n"
        f"REFERENCE ANSWER:\n{reference}\n\n"
        f"ATTEMPTED ANSWER:\n{attempted}"
    )
    response = client.responses.create(
        model=model,
        reasoning={"effort": effort},
        instructions=instruction,
        input=payload,
    )
    text = response.output_text
    verdicts = re.findall(r"VERDICT:\s*(CORRECT|INCORRECT)", text, flags=re.I)
    if not verdicts:
        raise RuntimeError(f"Judge returned no parseable verdict: {text[-500:]}")
    correct = verdicts[-1].upper() == "CORRECT"
    return {
        "correct": correct,
        "judge_text": text,
        "request_id": getattr(response, "_request_id", None),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions", type=Path)
    ap.add_argument("--judge-model", default="gpt-5")
    ap.add_argument(
        "--reasoning-effort",
        choices=["low", "medium", "high", "xhigh"],
        default="high",
    )
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--confirm-api-calls", action="store_true")
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set.")
    if not args.confirm_api_calls:
        raise SystemExit(
            "No API calls made. Re-run with --confirm-api-calls after checking "
            "judge model, trial count, and expected cost."
        )

    tasks = read_jsonl(HERE / "tasks.jsonl")
    gold = read_jsonl(HERE / "gold.jsonl")
    pred = read_jsonl(args.predictions)
    if not (len(tasks) == len(gold) == len(pred) == 100):
        raise ValueError(
            f"need exactly 100 aligned problems: tasks={len(tasks)} gold={len(gold)} pred={len(pred)}"
        )

    jobs = []
    trials_per_problem = None

    for i, (t, g, p) in enumerate(zip(tasks, gold, pred)):
        if "id" in p and p["id"] != t["id"]:
            raise ValueError(f"row {i}: id mismatch")

        if "responses" in p:
            responses = [str(x) for x in p["responses"]]
        elif "response" in p:
            responses = [str(p["response"])]
        elif "prediction" in p:
            responses = [str(p["prediction"])]
        elif "answer" in p:
            responses = [str(p["answer"])]
        else:
            raise KeyError(f"row {i}: need responses/response/prediction/answer")

        if not responses:
            raise ValueError(f"row {i}: empty responses")

        if trials_per_problem is None:
            trials_per_problem = len(responses)
        elif len(responses) != trials_per_problem:
            raise ValueError(
                f"all problems must have the same trial count; row {i} has "
                f"{len(responses)}, expected {trials_per_problem}"
            )

        for trial_idx, response in enumerate(responses):
            jobs.append({
                "problem_index": i,
                "trial_index": trial_idx,
                "id": t["id"],
                "subject": t["subject"],
                "problem": t["problem"],
                "reference": g["answer"],
                "attempted": response,
            })

    print(
        f"[confirm] grading {len(jobs)} attempts = "
        f"100 problems x {trials_per_problem} trial(s)"
    )
    if trials_per_problem == 20:
        print("[info] trial count matches the paper's Olympiad evaluation.")
    else:
        print(
            "[note] paper-comparable Olympiad reporting uses 20 independent trials/problem."
        )

    results = [None] * len(jobs)

    def worker(pair):
        idx, job = pair
        judged = judge_one(
            args.judge_model,
            args.reasoning_effort,
            job["problem"],
            job["reference"],
            job["attempted"],
        )
        return idx, {**job, **judged}

    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(worker, x) for x in enumerate(jobs)]
        for done_i, fut in enumerate(cf.as_completed(futures), 1):
            idx, row = fut.result()
            results[idx] = row
            print(
                f"[{done_i}/{len(jobs)}] {row['id']} trial={row['trial_index']} "
                f"{'CORRECT' if row['correct'] else 'INCORRECT'}",
                flush=True,
            )

    correct = sum(int(x["correct"]) for x in results)
    by_subject = defaultdict(lambda: {"correct": 0, "n": 0})
    by_problem = defaultdict(list)

    for x in results:
        by_subject[x["subject"]]["n"] += 1
        by_subject[x["subject"]]["correct"] += int(x["correct"])
        by_problem[x["id"]].append(int(x["correct"]))

    metrics = {
        "problems": 100,
        "trials_per_problem": trials_per_problem,
        "attempts": len(results),
        "accuracy": correct / len(results),
        "aggregation": "mean correctness over all independent attempts; no majority vote",
        "judge_model": args.judge_model,
        "judge_reasoning_effort": args.reasoning_effort,
        "paper_trial_count_match": trials_per_problem == 20,
        "by_subject": {
            s: {
                "attempts": d["n"],
                "accuracy": d["correct"] / d["n"],
            }
            for s, d in sorted(by_subject.items())
        },
        "per_problem_mean_accuracy": {
            pid: sum(vals) / len(vals) for pid, vals in by_problem.items()
        },
        "note": (
            "This adapter follows the paper's equivalence criterion with a compact "
            "paraphrased judge instruction. Use Inspect Evals for the verbatim "
            "paper judge-prompt implementation."
        ),
    }

    out = args.predictions.with_suffix(args.predictions.suffix + ".judge.graded.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for x in results:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    mout = args.predictions.with_suffix(args.predictions.suffix + ".judge.metrics.json")
    mout.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({k: v for k, v in metrics.items() if k != "per_problem_mean_accuracy"},
                     ensure_ascii=False, indent=2))
    print(f"[ok] details -> {out}")
    print(f"[ok] metrics -> {mout}")


if __name__ == "__main__":
    main()
