#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from datasets import load_dataset

REPO = "livecodebench/code_generation_lite"
CONFIG = os.environ.get("LCB_FORMAL_RELEASE", "release_v6")
BASE = Path(os.environ.get("LCB_DATA_ROOT", Path(__file__).resolve().parent))
CACHE = BASE / "cache" / CONFIG
manifest_path = CACHE / "dataset_manifest.json"

if not manifest_path.exists():
    raise SystemExit(
        f"Missing {manifest_path}. Run eval/download_release.py --config {CONFIG} first."
    )

dm = json.loads(manifest_path.read_text())
revision = dm["dataset_revision"]
hf_cache = os.environ.get("HF_DATASETS_CACHE")

ds = load_dataset(
    REPO,
    CONFIG,
    split="test",
    revision=revision,
    cache_dir=hf_cache,
)

def jloads(x):
    if x is None or x == "":
        return None
    try:
        return json.loads(x)
    except Exception:
        return x

tasks = []
gold = []
data = []
meta = []

for r in ds:
    task = {
        "benchmark": "LiveCodeBench",
        "scenario": "codegeneration",
        "release": CONFIG,
        "question_id": r["question_id"],
        "question_title": r["question_title"],
        "question_content": r["question_content"],
        "starter_code": r["starter_code"],
        "platform": r["platform"],
        "contest_id": r["contest_id"],
        "contest_date": r["contest_date"],
        "difficulty": r["difficulty"],
        "metadata": jloads(r["metadata"]),
    }
    private_blob = r["private_test_cases"] or ""
    public_blob = r["public_test_cases"] or ""
    g = {
        "benchmark": "LiveCodeBench",
        "release": CONFIG,
        "question_id": r["question_id"],
        "public_test_cases": jloads(public_blob),
        "private_test_cases_embedded": False,
        "private_test_cases_sha256": hashlib.sha256(
            private_blob.encode("utf-8")
        ).hexdigest(),
        "private_test_cases_source": {
            "dataset": REPO,
            "revision": revision,
            "config": CONFIG,
            "column": "private_test_cases",
        },
        "gt_public": True,
        "evaluator": "official LiveCodeBench custom_evaluator / modified APPS checker",
    }
    m = {
        "benchmark": "LiveCodeBench",
        "release": CONFIG,
        "question_id": r["question_id"],
        "platform": r["platform"],
        "contest_id": r["contest_id"],
        "contest_date": r["contest_date"],
        "difficulty": r["difficulty"],
        "has_starter_code": bool(r["starter_code"]),
        "gt_public": True,
        "gt_type": "executable public/private tests",
    }
    tasks.append(task)
    gold.append(g)
    data.append({"task": task, "gold": g})
    meta.append(m)

def write_jsonl(path, rows):
    with Path(path).open("w") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

write_jsonl(BASE / "tasks.jsonl", tasks)
write_jsonl(BASE / "gold.jsonl", gold)
write_jsonl(BASE / "data.jsonl", data)
write_jsonl(BASE / "metadata.jsonl", meta)

difficulty = {}
platform = {}
for r in meta:
    difficulty[r["difficulty"]] = difficulty.get(r["difficulty"], 0) + 1
    platform[r["platform"]] = platform.get(r["platform"], 0) + 1

manifest = {
    "benchmark": "LiveCodeBench",
    "scenario": "codegeneration",
    "dataset": REPO,
    "dataset_revision": revision,
    "release": CONFIG,
    "count": len(tasks),
    "expected_release_v6_count": 1055 if CONFIG == "release_v6" else None,
    "difficulty_counts": difficulty,
    "platform_counts": platform,
    "model_input": "tasks.jsonl",
    "evaluator_gt": "HF dataset private_test_cases at pinned revision",
    "gold_index": "gold.jsonl",
    "canonical_evaluator": "external/LiveCodeBench/lcb_runner/runner/custom_evaluator.py",
    "primary_metric_for_one_candidate": "pass@1",
}
(BASE / "MANIFEST.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
)
print(json.dumps(manifest, indent=2, ensure_ascii=False))
