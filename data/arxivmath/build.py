#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from datasets import load_dataset
from huggingface_hub import HfApi

HERE = Path(__file__).resolve().parent

RELEASES = {
    "2025-12": {"dataset": "MathArena/arxivmath-1225", "split": "train", "expected": 17},
    "2026-01": {"dataset": "MathArena/arxivmath-0126", "split": "train", "expected": 23},
    "2026-02": {"dataset": "MathArena/arxivmath-0226", "split": "train", "expected": 32},
    "2026-03": {"dataset": "MathArena/arxivmath-0326", "split": "train", "expected": 30},
    "2026-04": {"dataset": "MathArena/arxivmath-0426", "split": "train", "expected": 41},
    "2026-05": {"dataset": "MathArena/arxivmath-0526", "split": "train", "expected": 40},
}


def normalize_source(value):
    if value is None:
        return None
    # Older HF versions inferred source as float for arXiv IDs such as 2601.00917.
    # Avoid scientific notation and preserve a readable identifier when possible.
    if isinstance(value, float):
        return f"{value:.5f}"
    return str(value)


def materialize_release(release: str, spec: dict, out_dir: Path, api: HfApi):
    print(f"[load] {release}: {spec['dataset']}:{spec['split']}")
    ds = load_dataset(spec["dataset"], split=spec["split"])

    if len(ds) != spec["expected"]:
        raise RuntimeError(
            f"{release}: expected {spec['expected']} rows from official config, "
            f"but Hugging Face returned {len(ds)}. "
            "The benchmark may have been updated; inspect before silently changing results."
        )

    info = api.dataset_info(spec["dataset"])
    revision = info.sha

    release_dir = out_dir / "releases" / release
    release_dir.mkdir(parents=True, exist_ok=True)

    core_rows = []
    meta_rows = []

    for row in ds:
        if "problem" not in row or "answer" not in row:
            raise KeyError(
                f"{release}: dataset schema changed; fields={sorted(row.keys())}"
            )

        problem = str(row["problem"]).strip()
        answer = str(row["answer"]).strip()
        if not problem or not answer:
            raise ValueError(f"{release}: empty problem/answer at problem_idx={row.get('problem_idx')}")

        core_rows.append({"problem": problem, "answer": answer})

        meta = {
            "id": f"arxivmath_{release}_{int(row['problem_idx']):03d}",
            "release": release,
            "problem_idx": int(row["problem_idx"]),
            "hf_dataset": spec["dataset"],
            "hf_revision": revision,
            "source": normalize_source(row.get("source")),
        }
        for optional in ("problem_type", "title", "authors"):
            if optional in row and row[optional] is not None:
                meta[optional] = row[optional]
        meta_rows.append(meta)

    with (release_dir / "data.jsonl").open("w", encoding="utf-8") as f:
        for x in core_rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    with (release_dir / "metadata.jsonl").open("w", encoding="utf-8") as f:
        for x in meta_rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    return core_rows, meta_rows, {
        "release": release,
        "dataset": spec["dataset"],
        "split": spec["split"],
        "hf_revision": revision,
        "count": len(core_rows),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--release",
        choices=["all", *RELEASES.keys()],
        default="all",
        help="Materialize all current releases or one monthly release.",
    )
    ap.add_argument("--out-dir", type=Path, default=HERE)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    api = HfApi()

    selected = RELEASES if args.release == "all" else {args.release: RELEASES[args.release]}

    all_core = []
    all_meta = []
    manifest = {"releases": []}

    for release, spec in selected.items():
        core, meta, rel_manifest = materialize_release(release, spec, args.out_dir, api)
        all_core.extend(core)
        all_meta.extend(meta)
        manifest["releases"].append(rel_manifest)

    # Only write canonical combined data.jsonl when all releases are requested.
    if args.release == "all":
        expected_total = sum(x["expected"] for x in RELEASES.values())
        if len(all_core) != expected_total:
            raise RuntimeError(f"combined count mismatch: {len(all_core)} != {expected_total}")

        with (args.out_dir / "data.jsonl").open("w", encoding="utf-8") as f:
            for x in all_core:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")

        with (args.out_dir / "metadata.jsonl").open("w", encoding="utf-8") as f:
            for x in all_meta:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")

        manifest["combined_count"] = len(all_core)
        manifest["combined_file"] = "data.jsonl"

    with (args.out_dir / "MANIFEST.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[ok] materialized {len(all_core)} examples")
    if args.release == "all":
        print(f"[ok] canonical file: {args.out_dir / 'data.jsonl'}")
        print(f"[ok] metadata file : {args.out_dir / 'metadata.jsonl'}")
    print(f"[ok] manifest      : {args.out_dir / 'MANIFEST.json'}")


if __name__ == "__main__":
    main()
