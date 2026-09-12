#!/usr/bin/env python3
import argparse, json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--tasks", default="data/livecodebench/tasks.jsonl")
ap.add_argument("--output", default="data/livecodebench/predictions/predictions.jsonl")
args = ap.parse_args()

rows = [json.loads(x) for x in Path(args.tasks).read_text().splitlines() if x.strip()]
out = Path(args.output)
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("w") as f:
    for r in rows:
        f.write(json.dumps({
            "question_id": r["question_id"],
            "code": "# replace with your memory-system generated Python solution\n"
        }, ensure_ascii=False) + "\n")
print(f"[ok] wrote template with {len(rows)} rows: {out}")
