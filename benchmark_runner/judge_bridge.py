from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from .specs import read_jsonl


RUBRICS = {
    "arxivmath": (
        "Judge mathematical correctness against the reference answer. Accept "
        "algebraically equivalent forms, equivalent exact constants, and standard "
        "equivalent notation. Ignore harmless formatting such as LaTeX boxes. "
        "Do not accept a wrong final value merely because the reasoning is plausible."
    ),
    "olymmath": (
        "Judge the final mathematical answer against the reference answer. Accept "
        "mathematically equivalent expressions, equivalent sets/intervals, equivalent "
        "geometric forms, and harmless formatting differences. The candidate must "
        "satisfy every requested part."
    ),
    "physics": (
        "Judge whether the candidate correctly answers every requested physics "
        "subpart. The reference may be a list of final answers. Accept equivalent "
        "formulas, equivalent units, standard unit conversions, sign conventions "
        "when physically equivalent, and reasonable numerical rounding. If any "
        "required subanswer is materially wrong or missing, mark incorrect."
    ),
    "frontierscience_olympiad": (
        "Judge whether the attempted answer is fully equivalent to the reference "
        "answer for a science olympiad problem. Be strict but fair. Accept algebraic "
        "equivalence, reasonable numerical rounding, equivalent units, synonymous "
        "chemical identities/formulas, and equivalent named entities or methods."
    ),
}


def _prediction_id(row: dict[str, Any]) -> str:
    for k in ("id", "question_id", "problem_id", "task_id", "instance_id"):
        if k in row:
            return str(row[k])
    raise KeyError(f"prediction has no recognized id field: {row.keys()}")


def _candidate(row: dict[str, Any]) -> str:
    for k in ("response", "prediction", "output", "candidate", "answer"):
        if k in row:
            return str(row[k])
    raise KeyError(f"prediction has no recognized response field: {row.keys()}")


def _index_predictions(predictions: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(predictions):
        iid = _prediction_id(row)
        if iid in out:
            raise RuntimeError(f"duplicate prediction id: {iid}")
        out[iid] = row
    if not out:
        raise RuntimeError(f"no predictions in {predictions}")
    return out


def _row(
    benchmark: str,
    original_id: str,
    problem: Any,
    candidate: Any,
    reference: Any,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        # Prefix IDs so all answer benchmarks can be judged in one 14B process.
        "item_id": f"{benchmark}::{original_id}",
        "original_id": original_id,
        "benchmark": benchmark,
        "problem": str(problem),
        "candidate": str(candidate),
        "reference": (
            reference
            if isinstance(reference, str)
            else json.dumps(reference, ensure_ascii=False)
        ),
        "rubric": RUBRICS[benchmark],
        "metadata": metadata or {},
    }


def arxivmath_rows(repo: Path, predictions: Path) -> list[dict[str, Any]]:
    base = repo / "data" / "arxivmath"
    data = read_jsonl(base / "data.jsonl")
    meta = read_jsonl(base / "metadata.jsonl")
    if len(data) != len(meta):
        raise RuntimeError("ArXivMath data/metadata row mismatch")

    source = {
        str(m["id"]): (d, m)
        for d, m in zip(data, meta)
    }
    preds = _index_predictions(predictions)

    unknown = set(preds) - set(source)
    if unknown:
        raise RuntimeError(f"ArXivMath unknown prediction ids: {sorted(unknown)[:5]}")

    rows = []
    # Preserve canonical benchmark order, while allowing a partial prediction file.
    for iid, (d, m) in source.items():
        if iid not in preds:
            continue
        rows.append(_row(
            "arxivmath",
            iid,
            d["problem"],
            _candidate(preds[iid]),
            d["answer"],
            {"release": m.get("release")},
        ))
    return rows


def olymmath_rows(
    repo: Path,
    predictions: Path,
    split: str = "en-hard",
) -> list[dict[str, Any]]:
    base = repo / "data" / "olymmath"
    if split == "en-all":
        data_path = base / "data.jsonl"
        meta_path = base / "metadata.jsonl"
    else:
        data_path = base / "splits" / split / "data.jsonl"
        meta_path = base / "splits" / split / "metadata.jsonl"

    data = read_jsonl(data_path)
    meta = read_jsonl(meta_path)
    if len(data) != len(meta):
        raise RuntimeError("OlymMATH data/metadata row mismatch")

    source = {}
    for d, m in zip(data, meta):
        iid = str(m.get("unique_id", m["id"]))
        source[iid] = (d, m)

    preds = _index_predictions(predictions)
    unknown = set(preds) - set(source)
    if unknown:
        raise RuntimeError(f"OlymMATH unknown prediction ids: {sorted(unknown)[:5]}")

    rows = []
    for iid, (d, m) in source.items():
        if iid not in preds:
            continue
        rows.append(_row(
            "olymmath",
            iid,
            d["problem"],
            _candidate(preds[iid]),
            d["answer"],
            {
                "split": split,
                "subject": m.get("subject"),
                "difficulty": m.get("difficulty"),
                "language": m.get("language"),
            },
        ))
    return rows


def physics_rows(
    repo: Path,
    predictions: Path,
    split: str = "textonly",
) -> list[dict[str, Any]]:
    base = repo / "data" / "physics" / "splits" / split
    tasks = read_jsonl(base / "tasks.jsonl")
    gold = read_jsonl(base / "gold.jsonl")

    task_map = {str(x["id"]): x for x in tasks}
    gold_map = {str(x["id"]): x for x in gold}
    if set(task_map) != set(gold_map):
        raise RuntimeError("PHYSICS tasks/gold id mismatch")

    preds = _index_predictions(predictions)
    unknown = set(preds) - set(task_map)
    if unknown:
        raise RuntimeError(f"PHYSICS unknown prediction ids: {sorted(unknown)[:5]}")

    rows = []
    for iid, t in task_map.items():
        if iid not in preds:
            continue
        g = gold_map[iid]
        rows.append(_row(
            "physics",
            iid,
            t["problem"],
            _candidate(preds[iid]),
            g["answer"],
            {
                "split": split,
                "domain": t.get("domain"),
                "domain_label": t.get("domain_label"),
            },
        ))
    return rows


def frontierscience_rows(repo: Path, predictions: Path) -> list[dict[str, Any]]:
    base = repo / "data" / "frontierscience_olympiad"
    tasks = read_jsonl(base / "tasks.jsonl")
    gold = read_jsonl(base / "gold.jsonl")

    task_map = {str(x["id"]): x for x in tasks}
    gold_map = {str(x["id"]): x for x in gold}
    if set(task_map) != set(gold_map):
        raise RuntimeError("FrontierScience tasks/gold id mismatch")

    preds = _index_predictions(predictions)
    unknown = set(preds) - set(task_map)
    if unknown:
        raise RuntimeError(
            f"FrontierScience unknown prediction ids: {sorted(unknown)[:5]}"
        )

    rows = []
    for iid, t in task_map.items():
        if iid not in preds:
            continue
        rows.append(_row(
            "frontierscience_olympiad",
            iid,
            t["problem"],
            _candidate(preds[iid]),
            gold_map[iid]["answer"],
            {"subject": t.get("subject")},
        ))
    return rows


BUILDERS = {
    "arxivmath": arxivmath_rows,
    "olymmath": olymmath_rows,
    "physics": physics_rows,
    "frontierscience_olympiad": frontierscience_rows,
}


def build_rows(
    benchmark: str,
    repo: Path,
    predictions: Path,
    *,
    olymmath_split: str = "en-hard",
    physics_split: str = "textonly",
) -> list[dict[str, Any]]:
    if benchmark == "olymmath":
        return olymmath_rows(repo, predictions, olymmath_split)
    if benchmark == "physics":
        return physics_rows(repo, predictions, physics_split)
    if benchmark not in BUILDERS:
        raise KeyError(benchmark)
    return BUILDERS[benchmark](repo, predictions)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
