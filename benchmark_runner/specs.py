from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json


@dataclass(frozen=True)
class BenchmarkSpec:
    name: str
    kind: str  # answer | executable | scicode | agent_required
    evaluator: str
    description: str
    default_split: str | None = None


SPECS = {
    "arxivmath": BenchmarkSpec(
        "arxivmath", "answer", "local_judge",
        "ArXivMath answer benchmark. Qwen3-14B unified judge.",
    ),
    "olymmath": BenchmarkSpec(
        "olymmath", "answer", "local_judge",
        "OlymMATH answer benchmark. Qwen3-14B unified judge.",
        "en-hard",
    ),
    "physics": BenchmarkSpec(
        "physics", "answer", "local_judge",
        "PHYSICS text-only answer benchmark. Qwen3-14B unified judge.",
        "textonly",
    ),
    "frontierscience_olympiad": BenchmarkSpec(
        "frontierscience_olympiad", "answer", "local_judge",
        "FrontierScience-Olympiad. Qwen3-14B unified judge.",
    ),
    "livecodebench": BenchmarkSpec(
        "livecodebench", "executable", "official",
        "LiveCodeBench release_v6 executable tests.",
        "release_v6",
    ),
    "scicode": BenchmarkSpec(
        "scicode", "scicode", "official",
        "SciCode canonical sequential Inspect + executable tests.",
        "test",
    ),
    "swebench_pro": BenchmarkSpec(
        "swebench_pro", "agent_required", "official",
        "SWE-bench Pro requires a repository/terminal agent loop and official tests.",
    ),
}


DEFAULT_SUITE = [
    "arxivmath",
    "olymmath",
    "physics",
    "frontierscience_olympiad",
    "livecodebench",
    "scicode",
    "swebench_pro",
]


OFFLINE_GENERATION = [
    "arxivmath",
    "olymmath",
    "physics",
    "frontierscience_olympiad",
    "livecodebench",
]

ANSWER_BENCHMARKS = [
    "arxivmath",
    "olymmath",
    "physics",
    "frontierscience_olympiad",
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception as e:
                raise RuntimeError(f"{path}:{n}: invalid JSON: {e}") from e
            if not isinstance(row, dict):
                raise RuntimeError(f"{path}:{n}: row must be a JSON object")
            rows.append(row)
    return rows
