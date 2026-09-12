from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

from .eval_utils import (
    conda_wrap,
    parse_metrics_from_stdout,
    run_logged,
    shell_join,
    write_metrics,
    write_status,
)
from .judge_bridge import build_rows, write_jsonl
from .specs import (
    ANSWER_BENCHMARKS,
    DEFAULT_SUITE,
    OFFLINE_GENERATION,
    SPECS,
    read_jsonl,
)


DEFAULT_SOLVER = "/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-4B/"
DEFAULT_JUDGE = "/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-14B/"


def parse_list(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_SUITE)
    return [x.strip() for x in value.split(",") if x.strip()]


def check_known(benches: list[str]):
    unknown = [x for x in benches if x not in SPECS]
    if unknown:
        raise SystemExit(f"unknown benchmark(s): {unknown}")


def offline_benches(benches: list[str]) -> list[str]:
    return [b for b in benches if b in OFFLINE_GENERATION]


def run_inference(args, repo: Path, run_dir: Path, benches: list[str]):
    offline = offline_benches(benches)
    if not offline:
        return

    cmd = [
        sys.executable, "-m", "benchmark_runner.inference.run_suite",
        "--repo", str(repo),
        "--run-dir", str(run_dir),
        "--benchmarks", ",".join(offline),
        "--model", args.solver_model,
        "--tensor-parallel-size", str(args.solver_tp),
        "--gpu-memory-utilization", str(args.solver_gpu_memory),
        "--max-model-len", str(args.solver_max_model_len),
        "--max-tokens", str(args.solver_max_tokens),
        "--temperature", str(args.solver_temperature),
        "--top-p", str(args.solver_top_p),
        "--top-k", str(args.solver_top_k),
        "--seed", str(args.seed),
        "--batch-size", str(args.batch_size),
        "--olymmath-split", args.olymmath_split,
        "--physics-split", args.physics_split,
    ]
    if args.limit is not None:
        cmd += ["--limit", str(args.limit)]
    if args.resume:
        cmd += ["--resume"]
    if args.disable_solver_thinking:
        cmd += ["--disable-thinking"]

    print("[router] inference subprocess:", shell_join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(repo))
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def summarize_judged(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"correct": 0, "incorrect": 0, "invalid": 0}
    conf = 0.0
    for r in rows:
        verdict = str(r.get("verdict", "invalid"))
        if verdict not in counts:
            verdict = "invalid"
        counts[verdict] += 1
        try:
            conf += float(r.get("confidence", 0.0))
        except Exception:
            pass

    n = len(rows)
    valid = counts["correct"] + counts["incorrect"]
    return {
        "n_total": n,
        "n_correct": counts["correct"],
        "n_incorrect": counts["incorrect"],
        "n_invalid": counts["invalid"],
        # Headline metric: invalid is conservatively not correct.
        "accuracy_all": counts["correct"] / n if n else None,
        "accuracy_valid_only": counts["correct"] / valid if valid else None,
        "mean_confidence": conf / n if n else None,
    }


def evaluate_answer_suite(
    args,
    repo: Path,
    run_dir: Path,
    benches: list[str],
) -> int:
    selected = [b for b in benches if b in ANSWER_BENCHMARKS]
    if not selected:
        return 0

    combined_rows: list[dict[str, Any]] = []
    per_benchmark_inputs: dict[str, list[dict[str, Any]]] = {}

    for b in selected:
        pred = run_dir / b / "predictions.jsonl"
        if not pred.exists():
            raise FileNotFoundError(
                f"{b}: missing predictions file {pred}. Run inference first."
            )
        rows = build_rows(
            b,
            repo,
            pred,
            olymmath_split=args.olymmath_split,
            physics_split=args.physics_split,
        )
        per_benchmark_inputs[b] = rows
        combined_rows.extend(rows)

        # Keep a benchmark-local normalized input for auditing.
        write_jsonl(run_dir / b / "judge_input.jsonl", rows)

    unified_dir = run_dir / "_unified_answer_judge"
    unified_dir.mkdir(parents=True, exist_ok=True)
    judge_input = unified_dir / "judge_input.jsonl"
    judged = unified_dir / "judged.jsonl"
    write_jsonl(judge_input, combined_rows)

    # If this is not a resume run, do not reuse stale judge decisions.
    if not args.resume and judged.exists():
        judged.unlink()
    sidecar = Path(str(judged) + ".summary.json")
    if not args.resume and sidecar.exists():
        sidecar.unlink()

    cmd = [
        sys.executable,
        "-m", "benchmark_runner.llm_judge.judge",
        "--input", str(judge_input),
        "--output", str(judged),
        "--benchmark", "unified_answer_suite",
        "--id-key", "item_id",
        "--problem-key", "problem",
        "--candidate-key", "candidate",
        "--reference-key", "reference",
        "--rubric-key", "rubric",
        "--model", args.judge_model,
        "--backend", args.judge_backend,
        "--tensor-parallel-size", str(args.judge_tp),
        "--batch-size", str(args.judge_batch_size),
        "--gpu-memory-utilization", str(args.judge_gpu_memory),
        "--max-model-len", str(args.judge_max_model_len),
        "--max-tokens", str(args.judge_max_tokens),
    ]
    if args.resume:
        cmd += ["--resume"]

    print(
        f"[router] unified answer judge: {len(combined_rows)} samples "
        f"across {selected}",
        flush=True,
    )
    res = run_logged(cmd, cwd=repo, out_dir=unified_dir)

    if res["returncode"] != 0:
        for b in selected:
            write_status(run_dir / b, {
                "benchmark": b,
                "status": "error",
                "evaluator": "Qwen3-14B unified local judge",
                "judge_model": args.judge_model,
                "shared_judge_log_dir": str(unified_dir),
                **res,
            })
        return res["returncode"]

    judged_rows = read_jsonl(judged)
    by_benchmark: dict[str, list[dict[str, Any]]] = {b: [] for b in selected}

    for r in judged_rows:
        iid = str(r.get("item_id", ""))
        if "::" not in iid:
            continue
        b, original_id = iid.split("::", 1)
        if b not in by_benchmark:
            continue
        x = dict(r)
        x["unified_item_id"] = iid
        x["item_id"] = original_id
        x["benchmark"] = b
        by_benchmark[b].append(x)

    expected = {b: len(per_benchmark_inputs[b]) for b in selected}
    actual = {b: len(by_benchmark[b]) for b in selected}
    if expected != actual:
        raise RuntimeError(
            f"unified judge partition mismatch expected={expected}, actual={actual}"
        )

    for b in selected:
        out = run_dir / b
        local_judged = out / "judged.jsonl"
        write_jsonl(local_judged, by_benchmark[b])
        metrics = summarize_judged(by_benchmark[b])
        metrics.update({
            "benchmark": b,
            "evaluator": "Qwen3-14B unified local judge",
            "judge_model": args.judge_model,
        })
        write_metrics(out, metrics)
        write_status(out, {
            "benchmark": b,
            "status": "ok",
            "evaluator": "Qwen3-14B unified local judge",
            "judge_model": args.judge_model,
            "n": len(by_benchmark[b]),
            "shared_judge_log_dir": str(unified_dir),
            "note": (
                "This is a unified local-judge score, not the benchmark's "
                "official answer-scoring protocol."
            ),
        })
        print(
            f"[judge] {b}: "
            f"{metrics['n_correct']}/{metrics['n_total']} "
            f"accuracy={metrics['accuracy_all']:.4f}",
            flush=True,
        )

    return 0


def evaluate_livecodebench(args, repo, run_dir):
    out = run_dir / "livecodebench"
    pred = out / "predictions.jsonl"
    custom = out / "custom_outputs.json"

    command = (
        "source data/livecodebench/eval/env.sh && "
        f"python data/livecodebench/eval/convert_predictions.py "
        f"--input {pred} --output {custom} --strip-fences && "
        f"bash data/livecodebench/eval/run_custom_eval.sh {custom}"
    )
    res = run_logged(
        conda_wrap(command, args.lcb_env),
        cwd=repo,
        out_dir=out,
    )
    metrics = None
    if res["returncode"] == 0:
        metrics = parse_metrics_from_stdout(
            Path(res["stdout"]).read_text(),
            "livecodebench",
        )
    write_metrics(out, metrics)
    write_status(out, {
        "benchmark": "livecodebench",
        "status": "ok" if res["returncode"] == 0 else "error",
        "evaluator": "official LiveCodeBench executable evaluator",
        "release": "release_v6",
        **res,
    })
    return res["returncode"]


def run_scicode(args, repo, run_dir):
    cmd = [
        sys.executable,
        "-m", "benchmark_runner.scicode_local",
        "--repo", str(repo),
        "--run-dir", str(run_dir),
        "--model", args.solver_model,
        "--tensor-parallel-size", str(args.solver_tp),
        "--gpu-memory-utilization", str(args.solver_gpu_memory),
        "--max-model-len", str(args.solver_max_model_len),
        "--max-tokens", str(args.solver_max_tokens),
        "--scicode-env", args.scicode_env,
        "--split", args.scicode_split,
        "--port", str(args.scicode_port),
    ]
    if args.limit is not None:
        cmd += ["--limit", str(args.limit)]
    print("[router] SciCode subprocess:", shell_join(cmd), flush=True)
    return subprocess.run(cmd, cwd=str(repo)).returncode


def mark_agent_required(run_dir: Path):
    out = run_dir / "swebench_pro"
    write_status(out, {
        "benchmark": "swebench_pro",
        "status": "agent_required",
        "evaluator": "official SWE-bench Pro repository tests",
        "reason": (
            "SWE-bench Pro requires repository checkout + shell/editor/test "
            "interaction and a final git diff. The flat Qwen inference runner "
            "is intentionally not used."
        ),
        "next_component": "repo-level Qwen3-4B memory-agent runner",
    })


def collect_suite_summary(run_dir: Path, benches: list[str]):
    rows = {}
    for b in benches:
        p = run_dir / b / "status.json"
        m = run_dir / b / "metrics.json"
        row = {}
        if p.exists():
            row["status"] = json.loads(p.read_text())
        else:
            row["status"] = {"status": "missing"}
        if m.exists():
            row["metrics"] = json.loads(m.read_text())
        rows[b] = row

    summary = {
        "run_dir": str(run_dir),
        "evaluation_policy": {
            "answer_benchmarks": "Qwen3-14B unified local judge",
            "executable_benchmarks": "official executable evaluator",
        },
        "benchmarks": rows,
    }
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    return summary


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Qwen3-4B runner: answer benchmarks -> Qwen3-14B judge; "
            "executable benchmarks -> official verifier."
        )
    )
    ap.add_argument("--repo", default=".")
    ap.add_argument("--run-dir", default="runs/qwen3_4b_baseline")
    ap.add_argument("--benchmarks", default=",".join(DEFAULT_SUITE))
    ap.add_argument(
        "--stage",
        choices=["inference", "evaluate", "all"],
        default="all",
    )
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int)

    # Solver.
    ap.add_argument("--solver-model", default=DEFAULT_SOLVER)
    ap.add_argument("--solver-tp", type=int, default=1)
    ap.add_argument("--solver-gpu-memory", type=float, default=0.90)
    ap.add_argument("--solver-max-model-len", type=int, default=32768)
    ap.add_argument("--solver-max-tokens", type=int, default=8192)
    ap.add_argument("--solver-temperature", type=float, default=0.6)
    ap.add_argument("--solver-top-p", type=float, default=0.95)
    ap.add_argument("--solver-top-k", type=int, default=20)
    ap.add_argument("--disable-solver-thinking", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--batch-size", type=int, default=32)

    # Unified answer judge.
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE)
    ap.add_argument(
        "--judge-backend",
        choices=["vllm", "transformers"],
        default="vllm",
    )
    ap.add_argument("--judge-tp", type=int, default=1)
    ap.add_argument("--judge-batch-size", type=int, default=32)
    ap.add_argument("--judge-gpu-memory", type=float, default=0.90)
    ap.add_argument("--judge-max-model-len", type=int, default=32768)
    ap.add_argument("--judge-max-tokens", type=int, default=512)

    # Benchmark selection.
    ap.add_argument("--olymmath-split", default="en-hard")
    ap.add_argument("--physics-split", default="textonly")
    ap.add_argument("--scicode-split", default="test")
    ap.add_argument("--scicode-port", type=int, default=18000)

    # Only executable benchmark evaluator envs remain.
    ap.add_argument("--lcb-env", default="lcb")
    ap.add_argument("--scicode-env", default="scicode")

    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    run_dir_arg = Path(args.run_dir)
    run_dir = (
        run_dir_arg.resolve()
        if run_dir_arg.is_absolute()
        else (repo / run_dir_arg).resolve()
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    benches = parse_list(args.benchmarks)
    check_known(benches)

    config = vars(args).copy()
    config["repo"] = str(repo)
    config["run_dir"] = str(run_dir)
    config["evaluation_policy"] = {
        "answer_benchmarks": "Qwen3-14B unified local judge",
        "executable_benchmarks": "official executable evaluator",
    }
    (run_dir / "router_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    )

    if args.stage in {"inference", "all"}:
        run_inference(args, repo, run_dir, benches)

    if args.stage in {"evaluate", "all"}:
        if args.limit is not None:
            print(
                "[router] --limit is set. Partial answer benchmarks CAN be "
                "judged, but strict full-dataset executable evaluators are skipped.",
                flush=True,
            )

        # All answer benchmarks are concatenated and judged in one 14B process.
        answer_selected = [b for b in benches if b in ANSWER_BENCHMARKS]
        if answer_selected:
            print(
                "\n===== unified Qwen3-14B answer judging =====",
                flush=True,
            )
            try:
                evaluate_answer_suite(
                    args, repo, run_dir, answer_selected
                )
            except Exception as e:
                print(f"[router] unified answer judge error: {e}", flush=True)
                for b in answer_selected:
                    write_status(run_dir / b, {
                        "benchmark": b,
                        "status": "error",
                        "evaluator": "Qwen3-14B unified local judge",
                        "error": repr(e),
                    })

        if "livecodebench" in benches:
            if args.limit is not None:
                write_status(run_dir / "livecodebench", {
                    "benchmark": "livecodebench",
                    "status": "partial_inference_only",
                    "reason": (
                        "Official LiveCodeBench evaluation requires a complete "
                        "release-aligned prediction file."
                    ),
                })
            else:
                print("\n===== evaluate livecodebench =====", flush=True)
                try:
                    evaluate_livecodebench(args, repo, run_dir)
                except Exception as e:
                    write_status(run_dir / "livecodebench", {
                        "benchmark": "livecodebench",
                        "status": "error",
                        "error": repr(e),
                    })

        if "scicode" in benches:
            print("\n===== evaluate scicode =====", flush=True)
            try:
                run_scicode(args, repo, run_dir)
            except Exception as e:
                write_status(run_dir / "scicode", {
                    "benchmark": "scicode",
                    "status": "error",
                    "error": repr(e),
                })

        if "swebench_pro" in benches:
            mark_agent_required(run_dir)

    summary = collect_suite_summary(run_dir, benches)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
