#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "2025-12": 17,
    "2026-01": 23,
    "2026-02": 32,
    "2026-03": 30,
    "2026-04": 41,
    "2026-05": 40,
}


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=HERE)
    args = ap.parse_args()

    core = read_jsonl(args.dir / "data.jsonl")
    meta = read_jsonl(args.dir / "metadata.jsonl")

    if len(core) != len(meta):
        raise RuntimeError(f"data/metadata row mismatch: {len(core)} vs {len(meta)}")

    expected_total = sum(EXPECTED.values())
    if len(core) != expected_total:
        raise RuntimeError(f"expected {expected_total} rows, found {len(core)}")

    counts = Counter(m["release"] for m in meta)
    if dict(counts) != EXPECTED:
        raise RuntimeError(f"release counts mismatch: {dict(counts)} != {EXPECTED}")

    ids = [m["id"] for m in meta]
    if len(set(ids)) != len(ids):
        raise RuntimeError("duplicate metadata ids")

    for i, row in enumerate(core):
        if set(row) != {"problem", "answer"}:
            raise RuntimeError(f"row {i}: core schema must be exactly problem/answer; got {sorted(row)}")
        if not isinstance(row["problem"], str) or not row["problem"].strip():
            raise RuntimeError(f"row {i}: empty/invalid problem")
        if not isinstance(row["answer"], str) or not row["answer"].strip():
            raise RuntimeError(f"row {i}: empty/invalid answer")

    print("[ok] ArXivMath dataset validated")
    print(f"[ok] total: {len(core)}")
    for release in EXPECTED:
        print(f"  {release}: {counts[release]}")


if __name__ == "__main__":
    main()
