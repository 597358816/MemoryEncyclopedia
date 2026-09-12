from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from .backend import QwenVLLM, DEFAULT_SOLVER_MODEL
from ..adapters import load_items, prediction_row
from ..specs import SPECS, OFFLINE_GENERATION


def read_existing(path: Path, benchmark: str) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    id_key = "question_id" if benchmark == "livecodebench" else "id"
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            if id_key in row:
                out[str(row[id_key])] = row
    return out


def write_ordered(path: Path, items, rows_by_id):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            row = rows_by_id.get(item.item_id)
            if row is not None:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser(
        description="Load Qwen3-4B once and generate all offline benchmarks."
    )
    ap.add_argument("--repo", default=".")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--benchmarks", required=True,
                    help="Comma-separated offline benchmarks")
    ap.add_argument("--model", default=DEFAULT_SOLVER_MODEL)
    ap.add_argument("--tensor-parallel-size", type=int, default=1)
    ap.add_argument("--dtype", default="bfloat16")
    ap.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    ap.add_argument("--max-model-len", type=int, default=32768)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--top-p", type=float, default=0.95)
    ap.add_argument("--top-k", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--disable-thinking", action="store_true")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--olymmath-split", default="en-hard")
    ap.add_argument("--physics-split", default="textonly")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    run_dir = Path(args.run_dir).resolve()
    benches = [x.strip() for x in args.benchmarks.split(",") if x.strip()]
    split_override = {
        "olymmath": args.olymmath_split,
        "physics": args.physics_split,
    }

    # Load and validate all datasets before allocating GPU memory.
    loaded = {}
    for b in benches:
        spec = SPECS.get(b)
        if spec is None:
            raise SystemExit(f"unknown benchmark: {b}")
        if b not in OFFLINE_GENERATION:
            raise SystemExit(f"{b} is not supported by the offline-generation runner")
        split = split_override.get(b, spec.default_split)
        items = load_items(repo, b, split)
        if args.limit is not None:
            items = items[:args.limit]
        loaded[b] = items
        print(f"[load] {b}: {len(items)} items", flush=True)

    backend = QwenVLLM(
        args.model,
        tensor_parallel_size=args.tensor_parallel_size,
        dtype=args.dtype,
        gpu_memory_utilization=args.gpu_memory_utilization,
        max_model_len=args.max_model_len,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        top_p=args.top_p,
        top_k=args.top_k,
        seed=args.seed,
        enable_thinking=not args.disable_thinking,
    )

    suite_meta = {
        "solver_model": args.model,
        "tensor_parallel_size": args.tensor_parallel_size,
        "max_model_len": args.max_model_len,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "seed": args.seed,
        "enable_thinking": not args.disable_thinking,
        "benchmarks": benches,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "inference_config.json").write_text(
        json.dumps(suite_meta, ensure_ascii=False, indent=2) + "\n"
    )

    for b in benches:
        items = loaded[b]
        pred_path = run_dir / b / "predictions.jsonl"
        existing = read_existing(pred_path, b) if args.resume else {}
        pending = [x for x in items if x.item_id not in existing]
        print(
            f"[infer] {b}: total={len(items)} done={len(existing)} "
            f"pending={len(pending)}",
            flush=True,
        )

        for start in range(0, len(pending), args.batch_size):
            batch = pending[start:start + args.batch_size]
            responses = backend.generate([x.messages for x in batch])
            for item, response in zip(batch, responses):
                existing[item.item_id] = prediction_row(item, response)
            # Rewrite in canonical task order to keep row-aligned evaluators happy.
            write_ordered(pred_path, items, existing)
            print(
                f"[infer] {b}: "
                f"{min(start + len(batch), len(pending))}/{len(pending)} pending",
                flush=True,
            )

        meta = {
            "benchmark": b,
            "n": len(items),
            "predictions": str(pred_path),
            "complete": all(x.item_id in existing for x in items),
        }
        (pred_path.parent / "inference_meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2) + "\n"
        )
        print(f"[ok] {b} -> {pred_path}", flush=True)


if __name__ == "__main__":
    main()
