#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

DOMAINS = [
    "atomic",
    "electro",
    "mechanics",
    "optics",
    "quantum",
    "statistics",
]

DOMAIN_LABELS = {
    "atomic": "Atomic Physics",
    "electro": "Electromagnetism",
    "mechanics": "Classical Mechanics",
    "optics": "Optics",
    "quantum": "Quantum Mechanics",
    "statistics": "Thermodynamics & Statistical Mechanics",
}

SPLITS = {
    "test": ("PHYSICS-test", "_dataset_test.jsonl"),
    "validation": ("PHYSICS-eval", "_dataset_eval.jsonl"),
    "hard": ("PHYSICS-hard", "_dataset_hard.jsonl"),
    "textonly": ("PHYSICS-textonly", "_dataset_textonly.jsonl"),
    "all": (None, "_dataset.jsonl"),
}

EXPECTED = {
    "test": 1000,
    "validation": 297,
    "all": 1297,
}


def read_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8-sig") as f:
        for lineno, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except Exception as e:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {e}") from e
    return rows


def dump_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")


def source_path(official: Path, split: str, domain: str) -> Path:
    folder, suffix = SPLITS[split]
    if split == "all":
        return official / "PHYSICS" / f"{domain}_dataset.jsonl"
    return official / "PHYSICS" / folder / f"{domain}{suffix}"


def normalize_split(official: Path, split: str):
    core, tasks, gold, meta = [], [], [], []
    seen = set()

    for domain in DOMAINS:
        path = source_path(official, split, domain)
        if not path.exists():
            if split in {"hard", "textonly"}:
                print(f"[skip missing] {path}")
                continue
            raise FileNotFoundError(path)

        rows = read_jsonl(path)
        print(f"[load] {split:10s} {domain:10s} {len(rows):4d}")

        for row_idx, row in enumerate(rows):
            required = {"id", "questions", "solutions", "final_answers", "graphs"}
            missing = required.difference(row)
            if missing:
                raise KeyError(f"{path}: schema changed; missing {sorted(missing)}")

            pid = str(row["id"]).strip()
            problem = str(row["questions"]).strip()
            answers = row["final_answers"]
            if isinstance(answers, str):
                answers = [answers]
            if not isinstance(answers, list):
                raise TypeError(f"{pid}: final_answers must be list/string")
            answers = [str(a).strip() for a in answers]

            if not pid or not problem or not answers:
                raise ValueError(f"{path}: empty id/problem/final_answers at row {row_idx}")
            if pid in seen:
                raise RuntimeError(f"{split}: duplicate id {pid}")
            seen.add(pid)

            # Keep the user's problem/answer pair convention. `answer` is a list
            # because many PHYSICS problems contain multiple requested subanswers.
            core.append({
                "problem": problem,
                "answer": answers,
            })

            # Safe model-input view: no gold solution/answers.
            tasks.append({
                "id": pid,
                "domain": domain,
                "domain_label": DOMAIN_LABELS[domain],
                "problem": problem,
                "graphs": row["graphs"],
            })

            # Gold is deliberately separated to reduce accidental leakage.
            gold.append({
                "id": pid,
                "answer": answers,
                "solution": row["solutions"],
            })

            meta.append({
                "id": pid,
                "domain": domain,
                "domain_label": DOMAIN_LABELS[domain],
                "split": split,
                "row_in_domain_file": row_idx,
                "source_file": str(path),
                "has_graph": bool(row["graphs"]),
                "num_final_answers": len(answers),
            })

    return core, tasks, gold, meta


def git_commit(repo: Path):
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            text=True,
        ).strip()
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--official-repo",
        type=Path,
        default=REPO_ROOT / "external" / "Physics",
    )
    ap.add_argument("--out-dir", type=Path, default=HERE)
    args = ap.parse_args()

    official = args.official_repo.resolve()
    if not (official / "PHYSICS").exists():
        raise FileNotFoundError(
            f"Official PHYSICS checkout not found at {official}. "
            "Run `bash data/physics/setup_official.sh` first."
        )

    manifest = {
        "official_repo": str(official),
        "official_commit": git_commit(official),
        "splits": {},
    }

    built = {}
    for split in SPLITS:
        core, tasks, gold, meta = normalize_split(official, split)
        built[split] = (core, tasks, gold, meta)

        out = args.out_dir / "splits" / split
        dump_jsonl(out / "data.jsonl", core)
        dump_jsonl(out / "tasks.jsonl", tasks)
        dump_jsonl(out / "gold.jsonl", gold)
        dump_jsonl(out / "metadata.jsonl", meta)

        manifest["splits"][split] = {
            "count": len(core),
            "graph_tasks": sum(int(m["has_graph"]) for m in meta),
            "domain_counts": {
                d: sum(int(m["domain"] == d) for m in meta)
                for d in DOMAINS
            },
        }

        if split in EXPECTED and len(core) != EXPECTED[split]:
            raise RuntimeError(
                f"{split}: expected {EXPECTED[split]} rows, found {len(core)}. "
                "Official repository changed; inspect before accepting."
            )

    test_ids = {x["id"] for x in built["test"][1]}
    val_ids = {x["id"] for x in built["validation"][1]}
    all_ids = {x["id"] for x in built["all"][1]}

    if test_ids & val_ids:
        raise RuntimeError("test and validation IDs overlap")
    if test_ids | val_ids != all_ids:
        raise RuntimeError(
            "test ∪ validation does not exactly equal the 1297-problem full dataset"
        )

    for optional in ("hard", "textonly"):
        ids = {x["id"] for x in built[optional][1]}
        unknown = ids - all_ids
        if unknown:
            raise RuntimeError(f"{optional}: contains IDs outside full benchmark")

    # Canonical aliases = official 1000-problem test split.
    for filename in ("data.jsonl", "tasks.jsonl", "gold.jsonl", "metadata.jsonl"):
        shutil.copyfile(
            args.out_dir / "splits" / "test" / filename,
            args.out_dir / filename,
        )

    # Convenience aliases.
    for split in ("validation", "hard", "textonly"):
        shutil.copyfile(
            args.out_dir / "splits" / split / "data.jsonl",
            args.out_dir / f"{split}.jsonl",
        )

    (args.out_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("[ok] PHYSICS materialized")
    print(f"[ok] canonical test: {len(built['test'][0])}")
    print(f"[ok] validation    : {len(built['validation'][0])}")
    print(f"[ok] full          : {len(built['all'][0])}")
    print(f"[ok] hard          : {len(built['hard'][0])}")
    print(f"[ok] textonly      : {len(built['textonly'][0])}")
    print(f"[ok] data          : {args.out_dir / 'data.jsonl'}")


if __name__ == "__main__":
    main()
