from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os
import re
import shlex
import subprocess


def shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(x)) for x in parts)


def conda_wrap(command: str, env_name: str | None) -> list[str]:
    if env_name:
        return ["conda", "run", "-n", env_name, "bash", "-lc", command]
    return ["bash", "-lc", command]


def run_logged(
    argv: list[str],
    *,
    cwd: Path,
    out_dir: Path,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = out_dir / "evaluation.stdout.txt"
    stderr_path = out_dir / "evaluation.stderr.txt"

    merged = os.environ.copy()
    if env:
        merged.update({k: str(v) for k, v in env.items()})

    print("[eval]", shell_join(argv), flush=True)
    proc = subprocess.run(
        argv,
        cwd=str(cwd),
        env=merged,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_path.write_text(proc.stdout or "", encoding="utf-8")
    stderr_path.write_text(proc.stderr or "", encoding="utf-8")

    # Echo enough for interactive use while preserving complete logs.
    if proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    if proc.stderr:
        print(proc.stderr, end="" if proc.stderr.endswith("\n") else "\n")

    return {
        "returncode": proc.returncode,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }


def extract_json_objects(text: str) -> list[Any]:
    out = []
    for start, ch in enumerate(text):
        if ch != "{":
            continue
        depth = 0
        quoted = False
        escaped = False
        for i in range(start, len(text)):
            c = text[i]
            if quoted:
                if escaped:
                    escaped = False
                elif c == "\\":
                    escaped = True
                elif c == '"':
                    quoted = False
                continue
            if c == '"':
                quoted = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        out.append(json.loads(text[start:i + 1]))
                    except Exception:
                        pass
                    break
    return out


def parse_metrics_from_stdout(text: str, benchmark: str) -> dict[str, Any] | None:
    objs = extract_json_objects(text)
    if objs:
        # Evaluators generally print their summary as the last JSON object.
        for obj in reversed(objs):
            if isinstance(obj, dict):
                return obj

    if benchmark == "livecodebench":
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        for line in reversed(lines):
            try:
                return {"pass_at_1": float(line)}
            except Exception:
                continue
    return None


def write_status(out_dir: Path, status: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_metrics(out_dir: Path, metrics: dict[str, Any] | None) -> None:
    if metrics is None:
        return
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
