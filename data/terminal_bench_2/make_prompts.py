#!/usr/bin/env python3
# prompts.jsonl is already produced by build.py; this script regenerates it from tasks.jsonl.
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
with (ROOT/"tasks.jsonl").open(encoding="utf-8") as f, (ROOT/"prompts.jsonl").open("w",encoding="utf-8") as o:
    n=0
    for line in f:
        if not line.strip(): continue
        x=json.loads(line)
        o.write(json.dumps({"task_id":x["task_id"],"prompt":x["problem"]},ensure_ascii=False)+"\n")
        n+=1
print(f"[done] prompts={n}: {ROOT/'prompts.jsonl'}")
