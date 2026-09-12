#!/usr/bin/env python3
"""
Create generic model/agent task messages.

SWE-bench Pro is fundamentally an environment task: the agent should work in
the repository at `base_commit`. This file only produces the task instruction;
it does not emulate the repository environment.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(x) for x in f if x.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=HERE / "prompts.jsonl")
    args = ap.parse_args()

    tasks = read_jsonl(HERE / "tasks.jsonl")
    with args.output.open("w", encoding="utf-8") as f:
        for t in tasks:
            context = []
            if t.get("requirements"):
                context.append(f"Requirements/context:\n{t['requirements']}")
            if t.get("interface"):
                context.append(f"Interface/specification:\n{t['interface']}")

            prompt = (
                "You are working in an existing software repository. "
                "Resolve the issue below by modifying the repository. "
                "Do not merely describe the fix; implement it and leave the working tree "
                "with the complete code changes.\n\n"
                f"Repository: {t['repo']}\n"
                f"Base commit: {t['base_commit']}\n\n"
                f"Issue:\n{t['problem_statement']}"
            )
            if context:
                prompt += "\n\n" + "\n\n".join(context)

            f.write(json.dumps({
                "instance_id": t["instance_id"],
                "repo": t["repo"],
                "base_commit": t["base_commit"],
                "dockerhub_tag": t["dockerhub_tag"],
                "prompt": prompt,
            }, ensure_ascii=False) + "\n")

    print(f"[ok] wrote {len(tasks)} prompts -> {args.output}")


if __name__ == "__main__":
    main()
