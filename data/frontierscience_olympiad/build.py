#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

HERE = Path(__file__).resolve().parent

REPO_ID = "openai/frontierscience"
FILENAME = "olympiad/test.jsonl"
# This is the commit that first uploaded the public Olympiad gold file. Pinning
# it makes the benchmark content reproducible even if Hugging Face main changes.
DEFAULT_REVISION = "647a421c89d15aceaaa1a328e69b950b7632d2cf"
EXPECTED = 100


def read_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as e:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {e}") from e
    return rows


def dump_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--revision", default=DEFAULT_REVISION)
    ap.add_argument("--out-dir", type=Path, default=HERE)
    args = ap.parse_args()

    print(f"[download] {REPO_ID}/{FILENAME} @ {args.revision}")
    local = Path(
        hf_hub_download(
            repo_id=REPO_ID,
            filename=FILENAME,
            repo_type="dataset",
            revision=args.revision,
        )
    )
    rows = read_jsonl(local)

    if len(rows) != EXPECTED:
        raise RuntimeError(
            f"Expected {EXPECTED} public Olympiad gold tasks, got {len(rows)}. "
            "Do not silently change the benchmark denominator."
        )

    required = {"problem", "answer", "subject", "task_group_id"}
    core, tasks, gold, meta = [], [], [], []
    seen = set()

    for idx, row in enumerate(rows):
        missing = required.difference(row)
        if missing:
            raise KeyError(f"row {idx}: upstream schema changed; missing {sorted(missing)}")

        problem = str(row["problem"]).strip()
        answer = str(row["answer"]).strip()
        subject = str(row["subject"]).strip().lower()
        task_id = str(row["task_group_id"]).strip()

        if not problem or not answer or not subject or not task_id:
            raise ValueError(f"row {idx}: empty required field")
        if task_id in seen:
            raise RuntimeError(f"duplicate task_group_id: {task_id}")
        seen.add(task_id)
        if subject not in {"physics", "chemistry", "biology"}:
            raise RuntimeError(f"unexpected subject={subject!r} at {task_id}")

        # Encyclopedia compatibility view.
        core.append({
            "problem": problem,
            "answer": answer,
        })

        # Model-safe view: no gold answer.
        tasks.append({
            "id": task_id,
            "subject": subject,
            "problem": problem,
        })

        # Evaluator-only view.
        gold.append({
            "id": task_id,
            "answer": answer,
        })

        meta.append({
            "id": task_id,
            "subject": subject,
            "row_index": idx,
            "hf_repo": REPO_ID,
            "hf_file": FILENAME,
            "hf_revision": args.revision,
        })

    dump_jsonl(args.out_dir / "data.jsonl", core)
    dump_jsonl(args.out_dir / "tasks.jsonl", tasks)
    dump_jsonl(args.out_dir / "gold.jsonl", gold)
    dump_jsonl(args.out_dir / "metadata.jsonl", meta)

    counts = Counter(x["subject"] for x in tasks)
    manifest = {
        "hf_repo": REPO_ID,
        "hf_file": FILENAME,
        "hf_revision": args.revision,
        "count": len(tasks),
        "subject_counts": dict(sorted(counts.items())),
        "canonical_model_input": "tasks.jsonl",
        "canonical_gold": "gold.jsonl",
        "encyclopedia_pair_file": "data.jsonl",
    }
    (args.out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[ok] wrote {len(tasks)} FrontierScience-Olympiad tasks")
    print(f"[ok] subject counts: {dict(sorted(counts.items()))}")
    print(f"[ok] model inputs -> {args.out_dir / 'tasks.jsonl'}")
    print(f"[ok] gold         -> {args.out_dir / 'gold.jsonl'}")
    print(f"[ok] pairs        -> {args.out_dir / 'data.jsonl'}")


if __name__ == "__main__":
    main()
