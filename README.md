# MemoryEncyclopedia runner — unified judge v2

This overlay changes the evaluation policy to:

```text
Answer/open-ended:
  ArXivMath, OlymMATH, PHYSICS, FrontierScience-Olympiad
      -> one shared Qwen3-14B judge process

Executable:
  LiveCodeBench, SciCode, SWE-bench Pro
      -> official verifier
```

It should be extracted over the previous Qwen runner. The previously installed
`benchmark_runner/llm_judge/` directory is retained.

Start with:

```bash
python -m benchmark_runner.doctor

python -m benchmark_runner.router \
  --benchmarks arxivmath,olymmath,physics,frontierscience_olympiad \
  --stage all \
  --limit 2 \
  --run-dir runs/qwen3_4b_judge_smoke \
  --resume
```
