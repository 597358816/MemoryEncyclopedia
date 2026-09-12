from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess


DEFAULT_SOLVER = "/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-4B/"
DEFAULT_JUDGE = "/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-14B/"


FILES = {
    "arxivmath": [
        "data/arxivmath/data.jsonl",
        "data/arxivmath/metadata.jsonl",
    ],
    "olymmath": [
        "data/olymmath/splits/en-hard/data.jsonl",
        "data/olymmath/splits/en-hard/metadata.jsonl",
    ],
    "physics": [
        "data/physics/splits/textonly/tasks.jsonl",
        "data/physics/splits/textonly/gold.jsonl",
    ],
    "frontierscience_olympiad": [
        "data/frontierscience_olympiad/tasks.jsonl",
        "data/frontierscience_olympiad/gold.jsonl",
    ],
    "livecodebench": [
        "data/livecodebench/tasks.jsonl",
        "data/livecodebench/eval/convert_predictions.py",
        "data/livecodebench/eval/run_custom_eval.sh",
    ],
    "scicode": [
        "data/scicode/eval/run_model.sh",
        "external/SciCode/eval/inspect_ai/scicode.py",
    ],
    "swebench_pro": [
        "data/swebench_pro/tasks.jsonl",
        "data/swebench_pro/eval/run_local_docker.sh",
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--solver-model", default=DEFAULT_SOLVER)
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    failures = 0

    print("[evaluation policy]")
    print("  answer benchmarks     -> Qwen3-14B unified judge")
    print("  executable benchmarks -> official verifier")
    print()

    for label, path in [
        ("solver model", Path(args.solver_model)),
        ("judge model", Path(args.judge_model)),
    ]:
        if path.is_dir():
            print(f"[ok] {label}: {path}")
        else:
            print(f"[FAIL] {label}: {path}")
            failures += 1

    for mod in ["torch", "transformers", "vllm"]:
        try:
            m = __import__(mod)
            print(f"[ok] {mod}: {getattr(m, '__version__', '?')}")
        except Exception as e:
            print(f"[FAIL] {mod}: {e}")
            failures += 1

    judge_pkg = repo / "benchmark_runner" / "llm_judge" / "judge.py"
    if judge_pkg.exists():
        print(f"[ok] llm_judge: {judge_pkg}")
    else:
        print(f"[FAIL] llm_judge missing: {judge_pkg}")
        failures += 1

    print("\n[benchmark files]")
    for b, rels in FILES.items():
        print(f"\n{b}:")
        for rel in rels:
            p = repo / rel
            if p.exists():
                print(f"  [ok] {rel}")
            else:
                print(f"  [missing] {rel}")

    try:
        raw = subprocess.check_output(
            ["conda", "env", "list", "--json"],
            text=True,
        )
        envs = [Path(x).name for x in json.loads(raw).get("envs", [])]
        print("\n[conda envs]", ", ".join(envs))
    except Exception as e:
        print("[note] could not list conda envs:", e)

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
