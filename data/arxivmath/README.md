# ArXivMath deployment

This folder deploys the currently published monthly **ArXivMath** final-answer
benchmarks from MathArena.

As of 2026-09-09, the official MathArena repository contains these releases:

| Release | HF dataset | Problems |
|---|---|---:|
| 2025-12 | `MathArena/arxivmath-1225` | 17 |
| 2026-01 | `MathArena/arxivmath-0126` | 23 |
| 2026-02 | `MathArena/arxivmath-0226` | 32 |
| 2026-03 | `MathArena/arxivmath-0326` | 30 |
| 2026-04 | `MathArena/arxivmath-0426` | 41 |
| 2026-05 | `MathArena/arxivmath-0526` | 40 |
| **Total** | | **183** |

Do not use only `MathArena/arxivmath` as the canonical complete local copy:
the monthly datasets are the source of truth for the newer releases.

## 1. Materialize data

Your existing Python 3.11 `memory` environment is sufficient for this step.

```bash
pip install -r requirements-data.txt
python data/arxivmath/build.py
python data/arxivmath/validate.py
```

Result:

```text
data/arxivmath/
├── data.jsonl
├── metadata.jsonl
├── MANIFEST.json
├── SOURCE.json
└── releases/
    ├── 2025-12/
    │   ├── data.jsonl
    │   └── metadata.jsonl
    ├── 2026-01/
    ├── 2026-02/
    ├── 2026-03/
    ├── 2026-04/
    └── 2026-05/
```

Canonical `data.jsonl` uses exactly:

```json
{"problem": "...", "answer": "..."}
```

`metadata.jsonl` preserves the release, original `problem_idx`, arXiv source,
paper metadata when available, HF dataset, and exact Hugging Face revision SHA.

This matters because ArXivMath is dynamic.

## 2. Prompt format

MathArena asks the model to solve the question and put its final answer inside
`\boxed{}`. The older Dec/Jan/Feb configs use a slightly longer instruction;
Mar/Apr/May use the shorter instruction.

Generate model-ready prompts:

```bash
python data/arxivmath/make_prompts.py
```

This writes `data/arxivmath/prompts.jsonl`.

## 3. Official grading

ArXivMath is programmatically graded. MathArena uses its own answer parser and
symbolic comparison, with `strict_parsing: false`; this is more robust than
plain string equality.

The official MathArena package currently requires **Python >= 3.12**. Your
existing traceback showed your `memory` environment uses Python 3.11, so use a
separate evaluator environment rather than upgrading that environment in place:

```bash
conda create -n matharena python=3.12 -y
conda activate matharena

bash data/arxivmath/eval/setup_matharena.sh
```

The setup script clones the official repository, installs it editable, and
records the exact Git commit in:

```text
data/arxivmath/eval/MATHARENA_COMMIT.txt
```

### Score pre-generated responses

Input JSONL must be aligned with `data.jsonl` and contain one of:

```json
{"response": "full model response with \\boxed{...}"}
```

or, if your runner already extracted final answers:

```json
{"prediction": "..."}
```

Then:

```bash
conda activate matharena
python data/arxivmath/eval/score_official.py predictions.jsonl
```

The wrapper calls the official:

```python
matharena.grader.extract_and_grade(...)
```

and reports both per-release accuracy and the convenience combined accuracy.

## 4. Leaderboard-comparable run

If you want results maximally comparable to MathArena, do not use only the
combined 183-row file. Run their official runner separately for each release:

```bash
cd external/matharena

python scripts/run.py --comp arxiv/december --models YOUR_MODEL_CONFIG --n 4
python scripts/run.py --comp arxiv/january  --models YOUR_MODEL_CONFIG --n 4
python scripts/run.py --comp arxiv/february --models YOUR_MODEL_CONFIG --n 4
python scripts/run.py --comp arxiv/march    --models YOUR_MODEL_CONFIG --n 4
python scripts/run.py --comp arxiv/april    --models YOUR_MODEL_CONFIG --n 4
python scripts/run.py --comp arxiv/may      --models YOUR_MODEL_CONFIG --n 4
```

MathArena defaults to **4 runs per problem**. For your memory experiments, it
is fine to choose another `n`, but record it explicitly and keep it fixed
across memory/no-memory conditions.

## 5. Recommended encyclopedia metadata

```text
benchmark: ArXivMath
category: Math / research-level final answer
deployment_status: fully_local
dynamic: yes
ground_truth: yes
ground_truth_public: yes
ground_truth_type: final mathematical expression
deterministic_evaluation: yes
official_eval_repo: eth-sri/matharena
external_task_repo: no
docker_required: no
llm_judge: no
primary_metric: accuracy
current_local_releases: 2025-12 ... 2026-05
current_local_problem_count: 183
```

## 6. Reproducibility rule

Always archive:

- `MANIFEST.json` (HF revision SHA per monthly dataset)
- `eval/MATHARENA_COMMIT.txt` (grader implementation)
- model/version
- sampling config
- number of runs per problem

This avoids silently changing scores when the dynamic dataset or evaluator is
updated.
