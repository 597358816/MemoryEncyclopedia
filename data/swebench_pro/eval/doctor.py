#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
OFFICIAL = ROOT / "external" / "SWE-bench_Pro-os"


def count(path):
    with path.open(encoding="utf-8") as f:
        return sum(1 for x in f if x.strip())


def main():
    failed = False

    for filename in ("tasks.jsonl", "gold.jsonl", "raw.jsonl", "metadata.jsonl"):
        p = HERE / filename
        if not p.exists():
            print(f"[!!] missing {p}")
            failed = True
            continue
        n = count(p)
        ok = n == 731
        print(f"{'[ok]' if ok else '[!!]'} {filename}: {n}")
        failed |= not ok

    print(f"{'[ok]' if OFFICIAL.exists() else '[!!]'} official repo: {OFFICIAL}")
    failed |= not OFFICIAL.exists()

    docker = shutil.which("docker")
    print(f"{'[ok]' if docker else '[!!]'} docker: {docker or 'missing'}")
    if docker:
        try:
            subprocess.run(
                ["docker", "info"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=15,
            )
            print("[ok] docker daemon reachable")
        except Exception:
            print("[!!] docker command exists but daemon is not reachable")
            failed = True
    else:
        failed = True

    if failed:
        raise SystemExit(1)

    print("\n[ok] SWE-bench Pro public local-eval deployment is ready")


if __name__ == "__main__":
    main()
