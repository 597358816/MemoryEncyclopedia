#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

def strip_fences(text: str) -> str:
    s = text.strip()
    m = re.fullmatch(r"```(?:python|py)?\s*\n?(.*?)\n?```", s, flags=re.S | re.I)
    return m.group(1).strip() + "\n" if m else text

ap = argparse.ArgumentParser()
ap.add_argument("--input", required=True, help="JSONL: question_id + code")
ap.add_argument("--output", required=True, help="Official custom evaluator JSON")
ap.add_argument("--tasks", default="data/livecodebench/tasks.jsonl")
ap.add_argument("--strip-fences", action="store_true")
args = ap.parse_args()

tasks = [
    json.loads(x) for x in Path(args.tasks).read_text().splitlines() if x.strip()
]
task_ids = [str(x["question_id"]) for x in tasks]
expected = set(task_ids)

rows = {}
for n, line in enumerate(Path(args.input).read_text().splitlines(), 1):
    if not line.strip():
        continue
    x = json.loads(line)
    qid = str(x["question_id"])
    if qid in rows:
        raise SystemExit(f"duplicate question_id at line {n}: {qid}")
    code = x["code"]
    if not isinstance(code, str):
        raise SystemExit(f"line {n}: code must be a string")
    if args.strip_fences:
        code = strip_fences(code)
    rows[qid] = code

missing = expected - set(rows)
extra = set(rows) - expected
if missing or extra:
    raise SystemExit(
        f"prediction IDs mismatch: missing={len(missing)} extra={len(extra)}; "
        f"examples_missing={list(sorted(missing))[:5]} "
        f"examples_extra={list(sorted(extra))[:5]}"
    )

# Dict form is supported by the official custom evaluator; it sorts by question_id.
out = [
    {"question_id": qid, "code_list": [rows[qid]]}
    for qid in task_ids
]
Path(args.output).parent.mkdir(parents=True, exist_ok=True)
Path(args.output).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
print(f"[ok] converted {len(out)} predictions -> {args.output}")
