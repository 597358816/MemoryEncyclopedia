# SciCode deployment

This directory wraps the original **SciCode** benchmark for the Memory Encyclopedia
repository convention.

## Benchmark facts

- 80 main problems in total: 15 validation + 65 test.
- 338 subproblems are reported by the benchmark authors across the full benchmark.
- Scientific domains include physics, mathematics, materials science, biology, and chemistry.
- Each main problem is decomposed into ordered substeps.
- The official evaluator executes generated Python code against tests and numeric reference targets.
- A main problem is solved only if all of its scored substeps pass.
- Ground truth is public: reference code, test cases, and numeric HDF5 targets are available.

## Repository files

After `build.py`:

- `tasks.jsonl`: model-safe benchmark view. No reference code, tests, or numeric targets.
- `gold.jsonl`: evaluator/analysis-only public GT metadata.
- `data.jsonl`: convenience encyclopedia view containing both task and GT fields. **Never model input.**
- `metadata.jsonl`: split/domain/dependency/step-count metadata.
- `prompts.jsonl`: convenience textual prompts, not a replacement for the official sequential Inspect harness.
- `MANIFEST.json`: counts and provenance.

The canonical model evaluation should use the upstream `inspect_ai` integration in
`external/SciCode/eval/inspect_ai/scicode.py`.

## Important: original SciCode vs SciCode-Verified

This package deploys the original SciCode because that is the benchmark entry in the
project list. A 2026 independent derivative, SciCode-Verified, corrects a substantial
number of original benchmark defects. Do not mix its corrected prompts/targets with
original SciCode scores. If desired, deploy it later as a distinct benchmark entry.

## Quick start

```bash
source data/scicode/eval/env.sh
bash data/scicode/eval/setup_scicode.sh
bash data/scicode/eval/download_official.sh

python data/scicode/build.py
python data/scicode/validate.py
python data/scicode/eval/doctor.py

# No model/API call: official evaluator sanity check on validation using gold code
bash data/scicode/eval/run_gold_validation.sh
```

For a real model:

```bash
export SCICODE_MODEL=openai/gpt-4o
export OPENAI_API_KEY=...
bash data/scicode/eval/run_model.sh
```

Use `SCICODE_SPLIT=test` for the canonical 65-main-problem test evaluation.
