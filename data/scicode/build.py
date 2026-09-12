#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("SCICODE_REPO_ROOT", Path.cwd()))
BASE = ROOT / "data" / "scicode"
CACHE = BASE / "cache" / "official_hf"

EXPECTED_SPLITS = {
    "validation": ("problems_dev.jsonl", 15),
    "test": ("problems_test.jsonl", 65),
}

GT_KEYS_STEP = {
    "ground_truth_code",
    "test_cases",
}
GT_KEYS_MAIN = {
    "general_solution",
    "general_tests",
}

def load_jsonl(path: Path):
    rows = []
    with path.open() as f:
        for i, line in enumerate(f, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except Exception as e:
                    raise RuntimeError(f"{path}:{i}: invalid JSON: {e}") from e
    return rows

def clean_step(step: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in step.items() if k not in GT_KEYS_STEP}

def task_view(row: dict[str, Any], split: str) -> dict[str, Any]:
    return {
        "benchmark": "SciCode",
        "split": split,
        "problem_id": str(row.get("problem_id", "")),
        "problem_name": row.get("problem_name"),
        "problem_description_main": row.get("problem_description_main", ""),
        "problem_background_main": row.get("problem_background_main", ""),
        "problem_io": row.get("problem_io", ""),
        "required_dependencies": row.get("required_dependencies", ""),
        "sub_steps": [clean_step(s) for s in row.get("sub_steps", [])],
    }

def gold_view(row: dict[str, Any], split: str) -> dict[str, Any]:
    return {
        "benchmark": "SciCode",
        "split": split,
        "problem_id": str(row.get("problem_id", "")),
        "problem_name": row.get("problem_name"),
        "general_solution": row.get("general_solution"),
        "general_tests": row.get("general_tests"),
        "sub_steps": [
            {
                "step_number": s.get("step_number"),
                "ground_truth_code": s.get("ground_truth_code"),
                "test_cases": s.get("test_cases"),
            }
            for s in row.get("sub_steps", [])
        ],
        "numeric_targets": "external/SciCode/eval/data/test_data.h5",
        "gt_public": True,
        "evaluator": "official SciCode inspect_ai integration",
    }

def prompt_view(task: dict[str, Any]) -> dict[str, Any]:
    # Convenience only. Official evaluation is sequential and should use inspect_ai.
    lines = [
        task["problem_description_main"].strip(),
        "",
        "I/O specification:",
        task["problem_io"].strip(),
        "",
        "Required dependencies:",
        task["required_dependencies"].strip(),
        "",
        "Substeps:",
    ]
    for s in task["sub_steps"]:
        lines.append(f"\n[{s.get('step_number','')}] {s.get('step_description_prompt','')}")
        if s.get("function_header"):
            lines.append(s["function_header"])
    return {
        "problem_id": task["problem_id"],
        "split": task["split"],
        "prompt": "\n".join(lines).strip(),
        "warning": "Convenience prompt only; canonical evaluation uses ordered sequential substeps via official inspect_ai.",
    }

def write_jsonl(path: Path, rows):
    with path.open("w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

all_tasks = []
all_gold = []
all_data = []
all_meta = []
all_prompts = []

for split, (fname, expected) in EXPECTED_SPLITS.items():
    p = CACHE / fname
    if not p.exists():
        raise SystemExit(f"Missing {p}. Run eval/download_official.sh first.")
    rows = load_jsonl(p)
    if len(rows) != expected:
        raise SystemExit(f"{p}: expected {expected} rows, got {len(rows)}")

    for row in rows:
        t = task_view(row, split)
        g = gold_view(row, split)
        all_tasks.append(t)
        all_gold.append(g)
        all_data.append({"task": t, "gold": g})
        all_prompts.append(prompt_view(t))
        all_meta.append({
            "benchmark": "SciCode",
            "split": split,
            "problem_id": t["problem_id"],
            "problem_name": t["problem_name"],
            "num_substeps": len(t["sub_steps"]),
            "required_dependencies": t["required_dependencies"],
            "with_background_available": bool(
                t.get("problem_background_main")
                or any(s.get("step_background") for s in t["sub_steps"])
            ),
            "gt_public": True,
            "gt_type": "reference code + tests + HDF5 numeric targets",
            "canonical_evaluator": "external/SciCode/eval/inspect_ai/scicode.py",
        })

BASE.mkdir(parents=True, exist_ok=True)
write_jsonl(BASE / "tasks.jsonl", all_tasks)
write_jsonl(BASE / "gold.jsonl", all_gold)
write_jsonl(BASE / "data.jsonl", all_data)
write_jsonl(BASE / "metadata.jsonl", all_meta)
write_jsonl(BASE / "prompts.jsonl", all_prompts)

counts = {}
for r in all_meta:
    counts[r["split"]] = counts.get(r["split"], 0) + 1

manifest = {
    "benchmark": "SciCode",
    "main_problem_count": len(all_tasks),
    "split_counts": counts,
    "substep_count_from_downloaded_rows": sum(r["num_substeps"] for r in all_meta),
    "author_reported_total_subproblems": 338,
    "model_input": "tasks.jsonl",
    "evaluator_only_gt": "gold.jsonl + external/SciCode/eval/data/test_data.h5",
    "convenience_gt_exposing_view": "data.jsonl",
    "canonical_evaluator": "official inspect_ai integration",
}
(BASE / "MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
)
print(json.dumps(manifest, indent=2, ensure_ascii=False))
