# Terminal-Bench 2.0 deployment for Memory Encyclopedia

This package targets **Terminal-Bench 2.0**, the 89-task public terminal-agent benchmark.
The official evaluation harness is **Harbor**.

## Important semantic difference from code-generation benchmarks

Terminal-Bench is **not** an offline `prompt -> text answer -> exact checker` benchmark.

Official evaluation is:

```
instruction
  -> agent enters task-specific terminal/container
  -> agent executes commands and edits/builds files
  -> Harbor runs hidden-from-agent verifier phase
  -> reward / success
```

Therefore `tasks.jsonl` and `prompts.jsonl` are useful for the encyclopedia/catalog,
but an official model score must be produced through a Harbor-compatible agent.

Never feed `data.jsonl`, `gold.jsonl`, `solution/`, or `tests/` to the model.

## Directory convention

After materialization:

```
data/terminal_bench_2/
├── data.jsonl         # problem + public oracle solution; NEVER model input
├── tasks.jsonl        # model-safe instruction/catalog
├── prompts.jsonl      # task_id + instruction
├── gold.jsonl         # evaluator-only oracle + verifier paths
├── metadata.jsonl
├── MANIFEST.json
├── SOURCE.json
├── SOURCE_RESOLVED.json
└── eval/
```

Official task packages are downloaded under:

```
external/terminal-bench-2/
```

## 1. Install/check Harbor

From repository root:

```bash
bash data/terminal_bench_2/eval/setup_harbor.sh
```

The wrappers isolate Harbor's HOME/cache under:

```
/vepfs-mlp2/c20250203/250602012/cache/terminal_bench_2
```

Override with:

```bash
export TB2_CACHE_ROOT=/another/cache/path
```

## 2. Download the official 89 task packages

```bash
bash data/terminal_bench_2/eval/download_official.sh
```

## 3. Materialize encyclopedia JSONL files

```bash
python data/terminal_bench_2/build.py
python data/terminal_bench_2/validate.py
```

Expected count: 89.

## 4. Oracle smoke test first

Run one task:

```bash
bash data/terminal_bench_2/eval/run_oracle_smoke.sh
```

Default smoke task is `make-mips-interpreter`. You can choose another downloaded task:

```bash
bash data/terminal_bench_2/eval/run_oracle_smoke.sh regex-log
```

Oracle reward should be 1.0. This tests Docker + environment + public oracle + verifier.

## 5. Full oracle validation

The official project recommends validating oracle solutions before benchmarking agents.

```bash
N_CONCURRENT=4 bash data/terminal_bench_2/eval/run_oracle_full.sh
```

## 6. Run a built-in Harbor agent

Example pattern:

```bash
export AGENT=claude-code
export MODEL=provider/model-name
export PROVIDER_API_KEY=...
N_CONCURRENT=4 bash data/terminal_bench_2/eval/run_agent.sh
```

Use the actual API-key environment variable required by your provider.

## 7. Run your Memory agent

For a custom Harbor agent:

```bash
export AGENT_IMPORT_PATH='your_package.your_agent:YourAgent'
export MODEL='provider/model-name'

N_CONCURRENT=4 \
bash data/terminal_bench_2/eval/run_custom_agent.sh
```

For a Memory ablation, keep the dataset, environment, timeouts, verifier, model,
and agent scaffold fixed. Change only the memory mechanism.

## Ground truth

Terminal-Bench 2.0 has public programmatic GT:
- public human/oracle solution scripts;
- public programmatic tests/verifiers;
- no unique canonical text answer.

Primary result is Harbor reward / task success. For leaderboard-style reliability,
the official leaderboard uses repeated attempts (`-k 5` in current instructions).

## Docker note

Unlike LiveCodeBench-Pro's go-judge path, Terminal-Bench 2.0 does not have a
benchmark-wide requirement for `docker run --privileged`. Local Harbor runs still
require a working Docker daemon, and individual tasks can have task-specific
resource/environment constraints. Start with the one-task oracle smoke test.
