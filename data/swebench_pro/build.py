#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path

import pandas as pd
from datasets import load_dataset
from huggingface_hub import HfApi

HERE = Path(__file__).resolve().parent
DATASET = "ScaleAI/SWE-bench_Pro"
SPLIT = "test"
EXPECTED_CURRENT = 731


def dump_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_listish(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    s = str(value).strip()
    if not s:
        return []
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    return [s]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=HERE)
    ap.add_argument(
        "--allow-count-change",
        action="store_true",
        help="Accept an upstream public-dataset count different from 731 after inspection.",
    )
    args = ap.parse_args()

    print(f"[load] {DATASET}:{SPLIT}")
    ds = load_dataset(DATASET, split=SPLIT)

    if len(ds) != EXPECTED_CURRENT and not args.allow_count_change:
        raise RuntimeError(
            f"Expected current public count {EXPECTED_CURRENT}, got {len(ds)}. "
            "Scale may have updated the benchmark. Inspect upstream and rerun "
            "with --allow-count-change only after deciding to pin the new revision."
        )

    info = HfApi().dataset_info(DATASET)
    revision = info.sha

    required = {
        "repo",
        "instance_id",
        "base_commit",
        "patch",
        "test_patch",
        "problem_statement",
        "repo_language",
        "fail_to_pass",
        "pass_to_pass",
        "before_repo_set_cmd",
        "selected_test_files_to_run",
        "dockerhub_tag",
    }

    data_rows = []
    tasks = []
    gold = []
    metadata = []
    raw_rows = []
    seen = set()

    for i, row in enumerate(ds):
        missing = required.difference(row.keys())
        if missing:
            raise KeyError(f"row {i}: upstream schema changed; missing {sorted(missing)}")

        iid = str(row["instance_id"]).strip()
        repo = str(row["repo"]).strip()
        problem = str(row["problem_statement"]).strip()
        base_commit = str(row["base_commit"]).strip()

        if not iid or not repo or not problem or not base_commit:
            raise ValueError(f"row {i}: empty required task field")
        if iid in seen:
            raise RuntimeError(f"duplicate instance_id: {iid}")
        seen.add(iid)

        # Encyclopedia compatibility only. In code benchmarks, "answer" is the
        # gold patch; do NOT use data.jsonl as model input.
        data_rows.append({
            "problem": problem,
            "answer": str(row["patch"]),
        })

        # Safe model-visible task view.
        task = {
            "instance_id": iid,
            "repo": repo,
            "base_commit": base_commit,
            "problem_statement": problem,
            "repo_language": row["repo_language"],
            "dockerhub_tag": row["dockerhub_tag"],
        }
        # requirements/interface are contextual specs, not evaluator secrets.
        for field in ("requirements", "interface", "issue_specificity", "issue_categories"):
            if field in row and row[field] is not None:
                task[field] = row[field]
        tasks.append(task)

        # Evaluator-only / GT view.
        gold.append({
            "instance_id": iid,
            "patch": row["patch"],
            "test_patch": row["test_patch"],
            "fail_to_pass": normalize_listish(row["fail_to_pass"]),
            "pass_to_pass": normalize_listish(row["pass_to_pass"]),
        })

        metadata.append({
            "instance_id": iid,
            "repo": repo,
            "repo_language": row["repo_language"],
            "row_index": i,
            "hf_dataset": DATASET,
            "hf_split": SPLIT,
            "hf_revision": revision,
            "dockerhub_tag": row["dockerhub_tag"],
        })

        # Keep exact upstream fields for the official evaluator.
        raw_rows.append(dict(row))

    dump_jsonl(args.out_dir / "data.jsonl", data_rows)
    dump_jsonl(args.out_dir / "tasks.jsonl", tasks)
    dump_jsonl(args.out_dir / "gold.jsonl", gold)
    dump_jsonl(args.out_dir / "metadata.jsonl", metadata)
    dump_jsonl(args.out_dir / "raw.jsonl", raw_rows)

    # The upstream evaluator accepts JSONL, but CSV is convenient for compatibility.
    pd.DataFrame(raw_rows).to_csv(args.out_dir / "raw.csv", index=False)

    repo_counts = Counter(x["repo"] for x in tasks)
    lang_counts = Counter(str(x["repo_language"]) for x in tasks)
    manifest = {
        "hf_dataset": DATASET,
        "hf_split": SPLIT,
        "hf_revision": revision,
        "count": len(tasks),
        "repo_count": len(repo_counts),
        "repo_counts": dict(sorted(repo_counts.items())),
        "language_counts": dict(sorted(lang_counts.items())),
        "model_input": "tasks.jsonl",
        "evaluator_input": "raw.jsonl",
        "gold": "gold.jsonl",
        "encyclopedia_pairs": "data.jsonl",
    }
    (args.out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[ok] public tasks: {len(tasks)}")
    print(f"[ok] public repos : {len(repo_counts)}")
    print(f"[ok] HF revision  : {revision}")
    print(f"[ok] model input  -> {args.out_dir / 'tasks.jsonl'}")
    print(f"[ok] official raw -> {args.out_dir / 'raw.jsonl'}")
    print(f"[ok] gold         -> {args.out_dir / 'gold.jsonl'}")


if __name__ == "__main__":
    main()
