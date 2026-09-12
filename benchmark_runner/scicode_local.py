from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request


DEFAULT_MODEL = "/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-4B/"


def wait_server(url: str, proc: subprocess.Popen, timeout: float = 180.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(
                f"vLLM server exited early with code {proc.returncode}"
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if 200 <= r.status < 300:
                    return
        except Exception as e:
            last = e
        time.sleep(2)
    raise RuntimeError(f"vLLM server did not become ready: {last}")


def main():
    ap = argparse.ArgumentParser(
        description="Run SciCode Inspect against a local Qwen3-4B vLLM server."
    )
    ap.add_argument("--repo", default=".")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--served-model-name", default="qwen3-4b")
    ap.add_argument("--port", type=int, default=18000)
    ap.add_argument("--tensor-parallel-size", type=int, default=1)
    ap.add_argument("--gpu-memory-utilization", type=float, default=0.90)
    ap.add_argument("--max-model-len", type=int, default=32768)
    ap.add_argument("--scicode-env", default="scicode")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-tokens", type=int, default=8192)
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    out = Path(args.run_dir).resolve() / "scicode"
    out.mkdir(parents=True, exist_ok=True)
    server_log = (out / "vllm_server.log").open("w", encoding="utf-8")

    server_cmd = [
        sys.executable,
        "-m",
        "vllm.entrypoints.openai.api_server",
        "--model", args.model,
        "--served-model-name", args.served_model_name,
        "--host", "127.0.0.1",
        "--port", str(args.port),
        "--tensor-parallel-size", str(args.tensor_parallel_size),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
        "--max-model-len", str(args.max_model_len),
        "--dtype", "bfloat16",
        "--trust-remote-code",
    ]
    print("[scicode] starting:", " ".join(server_cmd), flush=True)
    proc = subprocess.Popen(
        server_cmd,
        cwd=str(repo),
        stdout=server_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    try:
        wait_server(f"http://127.0.0.1:{args.port}/v1/models", proc)
        print("[scicode] local OpenAI-compatible server ready", flush=True)

        env = os.environ.copy()
        env.update({
            "OPENAI_API_KEY": "EMPTY",
            "OPENAI_BASE_URL": f"http://127.0.0.1:{args.port}/v1",
            "SCICODE_MODEL": f"openai/{args.served_model_name}",
            "SCICODE_SPLIT": args.split,
            "SCICODE_OUTPUT_DIR": str(out / "inspect_outputs"),
            "SCICODE_MAX_TOKENS": str(args.max_tokens),
        })
        if args.limit is not None:
            env["SCICODE_LIMIT"] = str(args.limit)

        command = (
            f"cd {repo!s} && "
            "bash data/scicode/eval/run_model.sh"
        )
        argv = ["conda", "run", "-n", args.scicode_env, "bash", "-lc", command]
        print("[scicode] evaluator:", " ".join(argv), flush=True)
        ev = subprocess.run(
            argv,
            cwd=str(repo),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        (out / "evaluation.stdout.txt").write_text(ev.stdout or "", encoding="utf-8")
        (out / "evaluation.stderr.txt").write_text(ev.stderr or "", encoding="utf-8")
        if ev.stdout:
            print(ev.stdout, end="" if ev.stdout.endswith("\n") else "\n")
        if ev.stderr:
            print(ev.stderr, end="" if ev.stderr.endswith("\n") else "\n")

        status = {
            "benchmark": "scicode",
            "status": "ok" if ev.returncode == 0 else "error",
            "returncode": ev.returncode,
            "solver_model": args.model,
            "served_model_name": args.served_model_name,
            "split": args.split,
            "limit": args.limit,
            "canonical_evaluator": "official SciCode inspect_ai",
        }
        (out / "status.json").write_text(
            json.dumps(status, ensure_ascii=False, indent=2) + "\n"
        )
        if ev.returncode != 0:
            raise SystemExit(ev.returncode)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except Exception:
            pass
        try:
            proc.wait(timeout=20)
        except Exception:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                pass
        server_log.close()


if __name__ == "__main__":
    main()
