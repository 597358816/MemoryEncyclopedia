from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import re

from .specs import read_jsonl


@dataclass
class InferenceItem:
    item_id: str
    messages: list[dict[str, str]]
    benchmark: str
    meta: dict[str, Any]


def _boxed_math_messages(prompt: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": prompt}]


def load_arxivmath(repo: Path, split: str | None = None) -> list[InferenceItem]:
    base = repo / "data" / "arxivmath"
    data = read_jsonl(base / "data.jsonl")
    meta = read_jsonl(base / "metadata.jsonl")
    if len(data) != len(meta):
        raise RuntimeError("ArXivMath data/metadata row mismatch")

    long_inst = (
        "You are given a difficult question. Your task is to solve the problem.\n"
        "The question is written in such a way that it solely requires you to find "
        "the final answer. Make sure to follow the additional formatting instructions "
        "if they are provided in the question.\n"
        "Put the final answer you find within \\\\boxed{}."
    )
    short_inst = (
        "You are given a difficult question. Your task is to solve the problem.\n"
        "Put the final answer you find within \\\\boxed{}."
    )
    old = {"2025-12", "2026-01", "2026-02"}
    out = []
    for d, m in zip(data, meta):
        inst = long_inst if m["release"] in old else short_inst
        prompt = inst + "\n\n" + d["problem"]
        out.append(InferenceItem(
            str(m["id"]),
            _boxed_math_messages(prompt),
            "arxivmath",
            {"release": m["release"]},
        ))
    return out


def load_olymmath(repo: Path, split: str = "en-hard") -> list[InferenceItem]:
    base = repo / "data" / "olymmath"
    if split == "en-all":
        data_path = base / "data.jsonl"
        meta_path = base / "metadata.jsonl"
        language = "en"
    else:
        data_path = base / "splits" / split / "data.jsonl"
        meta_path = base / "splits" / split / "metadata.jsonl"
        language = split[:2]

    data = read_jsonl(data_path)
    meta = read_jsonl(meta_path)
    inst = (
        "Please reason step by step, and put your final answer within \\\\boxed{}."
        if language == "en"
        else "请逐步推理，并在 \\\\boxed{} 内给出您的最终答案。"
    )
    return [
        InferenceItem(
            str(m["unique_id"]),
            [{"role": "user", "content": inst + "\n\n" + d["problem"]}],
            "olymmath",
            {
                "subject": m.get("subject"),
                "difficulty": m.get("difficulty"),
                "split": split,
            },
        )
        for d, m in zip(data, meta)
    ]


def load_physics(repo: Path, split: str = "textonly") -> list[InferenceItem]:
    base = repo / "data" / "physics" / "splits" / split
    tasks = read_jsonl(base / "tasks.jsonl")
    system = (
        "Solve the advanced physics problem step by step. "
        "Place each final answer in a LaTeX \\\\boxed{...} expression."
    )
    out = []
    for t in tasks:
        graphs = t.get("graphs")
        if graphs:
            # Qwen3-4B is a text model. Do not pretend graph payloads are visible.
            raise RuntimeError(
                f"PHYSICS split={split!r} contains graph task {t['id']!r}. "
                "Use --physics-split textonly for Qwen3-4B."
            )
        out.append(InferenceItem(
            str(t["id"]),
            [
                {"role": "system", "content": system},
                {"role": "user", "content": t["problem"]},
            ],
            "physics",
            {"domain": t.get("domain"), "split": split},
        ))
    return out


def load_frontierscience(repo: Path, split: str | None = None) -> list[InferenceItem]:
    tasks = read_jsonl(repo / "data" / "frontierscience_olympiad" / "tasks.jsonl")
    system = (
        "Solve the science olympiad problem carefully. Give a concise final answer. "
        "At the end, write 'FINAL ANSWER: ' followed by your final answer."
    )
    return [
        InferenceItem(
            str(t["id"]),
            [
                {"role": "system", "content": system},
                {"role": "user", "content": t["problem"]},
            ],
            "frontierscience_olympiad",
            {"subject": t.get("subject")},
        )
        for t in tasks
    ]


def load_livecodebench(repo: Path, split: str = "release_v6") -> list[InferenceItem]:
    tasks = read_jsonl(repo / "data" / "livecodebench" / "tasks.jsonl")
    out = []
    for t in tasks:
        prompt = (
            "Solve the programming problem in Python 3. Return only executable "
            "Python source code, with no Markdown fences and no explanation.\n\n"
            f"Title: {t.get('question_title','')}\n\n"
            f"{t['question_content']}"
        )
        if t.get("starter_code"):
            prompt += "\n\nStarter code:\n" + str(t["starter_code"])
        out.append(InferenceItem(
            str(t["question_id"]),
            [{"role": "user", "content": prompt}],
            "livecodebench",
            {
                "difficulty": t.get("difficulty"),
                "platform": t.get("platform"),
                "release": t.get("release", split),
            },
        ))
    return out


LOADERS = {
    "arxivmath": load_arxivmath,
    "olymmath": load_olymmath,
    "physics": load_physics,
    "frontierscience_olympiad": load_frontierscience,
    "livecodebench": load_livecodebench,
}


def strip_thinking(text: str) -> str:
    # Qwen3 can emit <think>...</think>. Preserve ordinary answers, but code
    # extractors should not feed a reasoning block to executable evaluators.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1]
    return text.strip()


def extract_code(text: str) -> str:
    text = strip_thinking(text)
    blocks = re.findall(r"```(?:python|py)?\s*(.*?)```", text, flags=re.I | re.S)
    if blocks:
        return blocks[-1].strip() + "\n"
    return text.strip() + ("\n" if text.strip() else "")


def prediction_row(item: InferenceItem, response: str) -> dict[str, Any]:
    if item.benchmark == "livecodebench":
        return {
            "question_id": item.item_id,
            "code": extract_code(response),
            "raw_response": response,
        }
    if item.benchmark == "swebench_pro":
        return {
            "instance_id": item.item_id,
            "response": response,
        }
    return {
        "id": item.item_id,
        "response": response,
    }


def load_items(repo: Path, benchmark: str, split: str | None = None):
    if benchmark not in LOADERS:
        raise KeyError(f"no offline inference adapter for {benchmark}")
    fn = LOADERS[benchmark]
    if split is None:
        return fn(repo)
    return fn(repo, split)
