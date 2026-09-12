# PHYSICS deployment

PHYSICS is a 1,297-problem expert-annotated benchmark built from advanced
university / PhD-qualifying physics problems across six domains:

- Atomic Physics
- Electromagnetism
- Classical Mechanics
- Optics
- Quantum Mechanics
- Thermodynamics & Statistical Mechanics

The official repository exposes public questions, worked solutions,
`final_answers`, and any associated graph/image payloads.

## 1. Clone the official repository

```bash
bash data/physics/setup_official.sh
```

This creates:

```text
external/Physics/
```

and records the commit in:

```text
data/physics/eval/OFFICIAL_COMMIT.txt
```

## 2. Materialize the benchmark

No Hugging Face dependency is required.

```bash
python data/physics/build.py
python data/physics/validate.py
```

The builder verifies:

```text
test       = 1000
validation = 297
all        = 1297
test ∩ validation = ∅
test ∪ validation = all
```

It also materializes the upstream `hard` and `textonly` variants.

Result:

```text
data/physics/
├── data.jsonl                 # canonical official test = 1000
├── tasks.jsonl                # model-safe test inputs; no GT
├── gold.jsonl                 # answers + worked solutions
├── metadata.jsonl
├── validation.jsonl
├── hard.jsonl
├── textonly.jsonl
├── MANIFEST.json
└── splits/
    ├── test/
    │   ├── data.jsonl
    │   ├── tasks.jsonl
    │   ├── gold.jsonl
    │   └── metadata.jsonl
    ├── validation/
    ├── hard/
    ├── textonly/
    └── all/
```

### Core problem/answer format

The canonical file follows the encyclopedia convention:

```json
{
  "problem": "...",
  "answer": ["...", "..."]
}
```

`answer` is intentionally a **list**, not always a string. Many PHYSICS records
have multiple subquestions and multiple final answers. Flattening the list
would lose official evaluation semantics.

For actual model execution, use `tasks.jsonl` so the model never sees the
worked solution or GT:

```json
{
  "id": "quantum/...",
  "domain": "quantum",
  "problem": "...",
  "graphs": null
}
```

`graphs` is preserved exactly from the upstream record for multimodal runners.

## 3. If your model is text-only

Two clean choices:

### A. Use the official text-only variant

```text
data/physics/splits/textonly/
```

This is preferred for a text-only memory system.

### B. Use a chosen split but remove graph-bearing tasks

```bash
python data/physics/make_prompts.py \
  --split test \
  --drop-graph-tasks
```

Do not silently drop figures and still call the result the full PHYSICS test.

## 4. Generate prompts

```bash
python data/physics/make_prompts.py --split test
```

The generated prompt asks for step-by-step reasoning and requires each final
answer in `\boxed{...}`, matching the benchmark's answer-extraction contract.

The output also preserves the upstream `graphs` payload.

## 5. Why there are two scorers

PHYSICS does have public ground truth, but its official automated evaluator is
**hybrid**, not fully deterministic:

```text
model response
    ↓
extract boxed answers
    ↓
for each candidate vs each reference:
    SymPy parse/equivalence
        ↓ if unresolved / false
    GPT-4o equivalence judge
    ↓
problem accuracy
```

The upstream implementation also routes answers containing LaTeX `\text{...}`
directly to the GPT-4o comparison path.

Therefore:

```text
GT public                  = YES
official score local data  = YES
fully offline official     = NO
LLM judge                  = YES (fallback)
special benchmark access   = NO
```

Unlike CritPt, no benchmark-specific approval is needed.

## 6. Cheap fully local development score

Install:

```bash
pip install -r requirements-eval.txt
```

Suppose `predictions.jsonl` is aligned with the test split:

```json
{"id":"atomic/...","response":"... \\boxed{54.4\\,\\mathrm{eV}}"}
```

Run:

```bash
python data/physics/eval/score_sympy_only.py \
  predictions.jsonl \
  --split test
```

This uses normalized exact match + SymPy only.

It reports:

```text
lower_bound_accuracy
comparison_unresolved_fraction
per-domain lower-bound accuracy
```

Text/unparsable answers are treated as unresolved and therefore incorrect in
the lower-bound score.

Use this during rapid memory-system development.

**Do not report it as the official PHYSICS number.**

## 7. Official hybrid score

Install the same small evaluation environment:

```bash
pip install -r requirements-eval.txt
export OPENAI_API_KEY=...
```

Then:

```bash
python data/physics/eval/score_official_hybrid.py \
  predictions.jsonl \
  --split test
```

This imports the actual upstream:

```text
extract_boxed.py
equation_equivilancy.py
```

from `external/Physics`.

Therefore answer extraction and SymPy/GPT-4o fallback behavior are taken from
the official repository version recorded in `OFFICIAL_COMMIT.txt`.

The upstream equivalence implementation hard-codes GPT-4o as its fallback
judge. Pin the official repo commit when reporting a result because evaluator
behavior can change.

## 8. Official scoring semantics are slightly unusual

For each problem, the public evaluator:

1. extracts all boxed answers from the model response;
2. for each extracted answer, checks it against the list of reference
   `final_answers`;
3. counts a candidate as correct when it matches any reference;
4. computes:

```text
problem_accuracy = correct_extracted_answers / extracted_answers
```

and the dataset score is the mean of per-problem accuracy.

This means you should preserve the model's full response rather than
pre-collapsing a multi-part answer into one string.

For memory experiments, keep this scorer identical across all conditions.

## 9. Run the authors' vLLM baseline generation code

The official repo's baseline generator uses:

```text
temperature        = 0
max_tokens         = 8192
repetition_penalty = 1.2
```

For a local Hugging Face model, the upstream environment uses vLLM. Their
published `requirements.txt` contains a duplicate/conflicting SymPy pin, so
prefer a dedicated inference environment rather than blindly merging it into
your main `memory` environment.

Typical setup:

```bash
conda create -n physics-vllm python=3.11 -y
conda activate physics-vllm

pip install torch==2.5.1 vllm==0.6.6.post1 tqdm==4.67.1
```

Then:

```bash
bash data/physics/eval/run_official_vllm.sh \
  /path/to/model \
  physics_outputs
```

For your own memory agent, you do not need this vLLM wrapper; generate your
own `predictions.jsonl` and route it through the same grader.

## 10. Recommended configuration for the Memory Encyclopedia

For the first controlled experiment, I recommend one of:

### Most comparable

```text
split: test
n: 1000
modality: multimodal where graphs exist
scorer: official hybrid
```

### Easier text-memory experiment

```text
split: textonly
scorer: official hybrid
```

### Higher-difficulty focused experiment

```text
split: hard
scorer: official hybrid
```

Keep the exact split IDs fixed between No-Memory and Memory conditions.

## Registry entry

```text
benchmark: PHYSICS
category: Science / advanced physics reasoning
deployment_status: fully_local_data + hybrid_local/API_grading

total: 1297
test: 1000
validation: 297
domains: 6

ground_truth: yes
ground_truth_public: yes
ground_truth_type: final-answer list

multimodal: yes
textonly_variant: yes
hard_variant: yes

official_evaluator:
  boxed answer extraction
  SymPy equivalence
  GPT-4o fallback judge

llm_judge: yes
special_grader_access: no
docker_required: no
external_task_repo: no
official_code_repo: yale-nlp/Physics
```
