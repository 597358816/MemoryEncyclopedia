#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from huggingface_hub import HfApi
from datasets import load_dataset

REPO = "livecodebench/code_generation_lite"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.environ.get("LCB_FORMAL_RELEASE", "release_v6"))
    ap.add_argument("--force-redownload", action="store_true")
    args = ap.parse_args()

    root = Path(os.environ.get("LCB_DATA_ROOT", "data/livecodebench"))
    cache_root = Path(os.environ.get("HF_DATASETS_CACHE", root / "cache" / "hf"))
    out = root / "cache" / args.config
    out.mkdir(parents=True, exist_ok=True)

    api = HfApi()
    info = api.dataset_info(REPO)
    revision = info.sha
    print(f"[hf] repo={REPO}")
    print(f"[hf] revision={revision}")
    print(f"[hf] config={args.config}")

    kwargs = dict(
        path=REPO,
        name=args.config,
        split="test",
        revision=revision,
        cache_dir=str(cache_root),
    )
    if args.force_redownload:
        kwargs["download_mode"] = "force_redownload"

    # Positional config avoids the historical version_tag BuilderConfig issue.
    ds = load_dataset(
        REPO,
        args.config,
        split="test",
        revision=revision,
        cache_dir=str(cache_root),
        download_mode=("force_redownload" if args.force_redownload else None),
    )

    manifest = {
        "dataset_repo": REPO,
        "dataset_revision": revision,
        "config": args.config,
        "count": len(ds),
        "columns": list(ds.column_names),
        "cache_dir": str(cache_root),
    }
    (out / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )

    # Save only model-safe IDs/metadata as a compact index. Do not duplicate
    # multi-GB private test bodies.
    index_path = out / "index.jsonl"
    with index_path.open("w") as f:
        for r in ds:
            item = {
                "question_id": r["question_id"],
                "question_title": r["question_title"],
                "platform": r["platform"],
                "contest_id": r["contest_id"],
                "contest_date": r["contest_date"],
                "difficulty": r["difficulty"],
            }
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"[ok] compact index: {index_path}")

if __name__ == "__main__":
    main()
