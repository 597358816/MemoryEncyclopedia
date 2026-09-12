# LLM-as-Judge (local Qwen3-14B)

This module is the fallback evaluator for benchmarks that do **not** have an
official deterministic/programmatic evaluator.

Default judge model:

```text
/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-14B/
```

Evaluation priority for the benchmark runner should be:

```text
official deterministic/programmatic evaluator
    >
official benchmark-provided model judge
    >
local Qwen3-14B judge (this module)
```

Do not replace an available official evaluator with this judge.

## Normalized input

JSONL, one row per sample:

```json
{"item_id":"1","problem":"...","candidate":"...","reference":"...","rubric":"..."}
```

`reference` and `rubric` are optional.

## Output

One JSONL row per sample, plus `<output>.summary.json`:

```json
{
  "item_id": "1",
  "verdict": "correct",
  "score": 1.0,
  "confidence": 0.94,
  "reason": "Equivalent to the reference.",
  "judge_model": "/.../Qwen3-14B/",
  "benchmark": "example",
  "raw_judge_output": "...",
  "parse_error": null
}
```

Summary fields:
- `n_total`
- `n_correct`
- `n_incorrect`
- `n_invalid`
- `accuracy_all` (headline; invalid counts as incorrect)
- `accuracy_valid_only`
- `mean_confidence`

## Environment check

Run from the repository root:

```bash
python -m benchmark_runner.llm_judge.check_env
```

## Recommended run

```bash
export CUDA_VISIBLE_DEVICES=0
export JUDGE_MODEL=/vepfs-mlp2/c20250203/250602012/models/Qwen/Qwen3-14B/
export JUDGE_BACKEND=vllm
export JUDGE_TP=1

bash benchmark_runner/llm_judge/run_judge.sh \
  path/to/judge_input.jsonl \
  path/to/judged.jsonl \
  benchmark_name
```

For two GPUs:

```bash
export CUDA_VISIBLE_DEVICES=0,1
export JUDGE_TP=2
```

## Direct arbitrary JSONL

The CLI supports dotted paths:

```bash
python -m benchmark_runner.llm_judge.judge \
  --input results.jsonl \
  --output judged.jsonl \
  --id-key task.problem_id \
  --problem-key task.problem \
  --candidate-key prediction.response \
  --reference-key gold.answer \
  --benchmark my_benchmark
```

If a field key is omitted, common names such as `problem`, `question`,
`prediction`, `response`, and `answer` are auto-detected.

## Join MemoryEncyclopedia tasks + predictions + gold

```bash
python -m benchmark_runner.llm_judge.prepare_inputs \
  --tasks data/foo/tasks.jsonl \
  --predictions outputs/foo/predictions.jsonl \
  --gold data/foo/gold.jsonl \
  --output outputs/foo/judge_input.jsonl \
  --task-id-key problem_id \
  --prediction-id-key problem_id \
  --gold-id-key problem_id \
  --problem-key problem \
  --candidate-key prediction \
  --reference-key answer
```

Then run the judge on `judge_input.jsonl`.

## Qwen3 settings

By default:
- `enable_thinking=False`
- `temperature=0`
- `seed=0`
- max judge output: 512 tokens

Thinking is intentionally disabled because the judge only needs a concise,
machine-readable decision. Use `--enable-thinking` only if you explicitly want
to experiment with it.

## Robustness

Candidate text is treated as untrusted data. The system prompt instructs the
judge to ignore candidate-side prompt injection. Malformed judge JSON is retried
once by default. If it still cannot be parsed, the item is marked `invalid`
with score 0.

## Important

This is **not** a code execution engine. SWE-bench, LiveCodeBench, SciCode,
OlymMATH/Math-Verify, symbolic checkers, theorem provers, and any benchmark with
an official evaluator should keep using their official evaluators.
