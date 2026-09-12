#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

try:
    import tomllib
except ImportError:
    raise RuntimeError("Python >=3.11 is required (tomllib).")

ROOT = Path(__file__).resolve().parent
DEFAULT_SOURCE = ROOT.parents[1] / "external" / "terminal-bench-2"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_tasks(source: Path):
    out = []
    for p in sorted(source.rglob("task.toml")):
        d = p.parent
        inst = d / "instruction.md"
        sol = d / "solution" / "solve.sh"
        tests = d / "tests" / "test.sh"
        if inst.exists() and sol.exists() and tests.exists():
            out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--allow-non89", action="store_true")
    args = ap.parse_args()

    source = args.source.resolve()
    if not source.exists():
        raise FileNotFoundError(
            f"Official task tree not found: {source}\n"
            "Run data/terminal_bench_2/eval/download_official.sh first."
        )

    task_dirs = find_tasks(source)
    if len(task_dirs) != 89 and not args.allow_non89:
        raise RuntimeError(
            f"Expected 89 complete Terminal-Bench 2.0 tasks, found {len(task_dirs)}. "
            "Use --allow-non89 only for debugging."
        )

    tasks, gold, meta, data, prompts = [], [], [], [], []
    categories, difficulties = Counter(), Counter()

    for d in task_dirs:
        cfg_path = d / "task.toml"
        cfg = tomllib.loads(read_text(cfg_path))
        task_cfg = cfg.get("task", {})
        md = cfg.get("metadata", {})
        verifier = cfg.get("verifier", {})
        agent = cfg.get("agent", {})
        env = cfg.get("environment", {})
        source_cfg = cfg.get("source", {})

        task_id = str(task_cfg.get("name") or f"terminal-bench/{d.name}")
        instruction = read_text(d / "instruction.md")
        solution = read_text(d / "solution" / "solve.sh")

        category = md.get("category")
        difficulty = md.get("difficulty")
        if category:
            categories[str(category)] += 1
        if difficulty:
            difficulties[str(difficulty)] += 1

        # MODEL-SAFE. Do not add solution/test/verifier fields here.
        tasks.append({
            "task_id": task_id,
            "problem": instruction,
            "description": task_cfg.get("description"),
            "category": category,
            "difficulty": difficulty,
            "agent_timeout_sec": agent.get("timeout_sec"),
        })

        prompts.append({
            "task_id": task_id,
            "prompt": instruction,
        })

        # Evaluator-only GT. Terminal-Bench does not have a single text answer;
        # the public oracle script and tests define correctness.
        gold.append({
            "task_id": task_id,
            "ground_truth_type": "programmatic_verifier",
            "oracle_solution": solution,
            "oracle_solution_path": str((d / "solution" / "solve.sh").relative_to(source)),
            "test_entrypoint_path": str((d / "tests" / "test.sh").relative_to(source)),
            "expected_oracle_reward": 1.0,
        })

        # Encyclopedia convenience view; NEVER feed this to the model.
        data.append({
            "problem": instruction,
            "answer": solution,
        })

        meta.append({
            "task_id": task_id,
            "task_slug": d.name,
            "source_task_dir": str(d.relative_to(source)),
            "schema_version": cfg.get("schema_version"),
            "description": task_cfg.get("description"),
            "keywords": task_cfg.get("keywords", []),
            "metadata": md,
            "agent": agent,
            "verifier": {
                "timeout_sec": verifier.get("timeout_sec"),
                "environment_mode": verifier.get("environment_mode"),
            },
            "environment": {
                "docker_image": env.get("docker_image"),
                "build_timeout_sec": env.get("build_timeout_sec"),
                "cpus": env.get("cpus"),
                "memory_mb": env.get("memory_mb"),
                "storage_mb": env.get("storage_mb"),
                "gpus": env.get("gpus"),
                "gpu_types": env.get("gpu_types"),
                "allow_internet": env.get("allow_internet"),
                "network_mode": env.get("network_mode"),
            },
            "source": source_cfg,
            "task_toml_sha256": sha256_file(cfg_path),
            "instruction_sha256": sha256_file(d / "instruction.md"),
            "oracle_sha256": sha256_file(d / "solution" / "solve.sh"),
            "test_sha256": sha256_file(d / "tests" / "test.sh"),
        })

    write_jsonl(ROOT / "tasks.jsonl", tasks)
    write_jsonl(ROOT / "prompts.jsonl", prompts)
    write_jsonl(ROOT / "gold.jsonl", gold)
    write_jsonl(ROOT / "data.jsonl", data)
    write_jsonl(ROOT / "metadata.jsonl", meta)

    manifest = {
        "benchmark": "Terminal-Bench 2.0",
        "official_dataset": "terminal-bench/terminal-bench-2",
        "task_count": len(tasks),
        "expected_task_count": 89,
        "source_tree": str(source),
        "category_counts": dict(sorted(categories.items())),
        "difficulty_counts": dict(sorted(difficulties.items())),
        "ground_truth": {
            "exists": True,
            "public": True,
            "type": "programmatic_verifier",
            "oracle_solution_public": True,
            "tests_public": True,
            "canonical_text_answer": False,
        },
        "evaluation": {
            "official_harness": "Harbor",
            "local_requires_docker": True,
            "metric": "reward / success rate",
            "model_output_type": "interactive terminal actions / modified environment state",
            "offline_text_answer_scoring": False,
        },
        "model_safe_input": "tasks.jsonl",
        "prompt_catalog": "prompts.jsonl",
        "evaluator_only_gt": "gold.jsonl",
        "convenience_problem_answer_view": "data.jsonl",
    }
    (ROOT / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    resolved = {
        "source_tree": str(source),
        "task_count": len(task_dirs),
        "task_ids": [x["task_id"] for x in tasks],
    }
    (ROOT / "SOURCE_RESOLVED.json").write_text(
        json.dumps(resolved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[done] tasks      : {len(tasks)}")
    print(f"[done] tasks.jsonl: {ROOT / 'tasks.jsonl'}")
    print(f"[done] gold.jsonl : {ROOT / 'gold.jsonl'}")
    print(f"[done] data.jsonl : {ROOT / 'data.jsonl'}")
    print(f"[done] metadata   : {ROOT / 'metadata.jsonl'}")
    print(f"[done] prompts    : {ROOT / 'prompts.jsonl'}")


if __name__ == "__main__":
    main()
