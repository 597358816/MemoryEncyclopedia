# FrontierScience-Olympiad

This deployment targets the **100-question open gold set** of
FrontierScience-Olympiad released by OpenAI.

It is a fully public, text-only benchmark across:

- Physics
- Chemistry
- Biology

The full FrontierScience project contains more held-out questions, but this
folder intentionally represents the public 100-question Olympiad gold set.

## 1. Materialize the official dataset

```bash
pip install -r requirements-data.txt

python data/frontierscience_olympiad/build.py
python data/frontierscience_olympiad/validate.py
```

The builder downloads the official Hugging Face file:

```text
openai/frontierscience
└── olympiad/test.jsonl
```

and pins the Olympiad file to the public upload commit:

```text
647a421c89d15aceaaa1a328e69b950b7632d2cf
```

Generated layout:

```text
data/frontierscience_olympiad/
├── data.jsonl
├── tasks.jsonl
├── gold.jsonl
├── metadata.jsonl
├── MANIFEST.json
└── SOURCE.json
```

## 2. File semantics

### `tasks.jsonl` — model input

```json
{
  "id": "...",
  "subject": "physics",
  "problem": "..."
}
```

The `problem` string is the official dataset text. It already contains the
solver instruction requiring a final line beginning with `FINAL ANSWER`.

Do not append a second benchmark instruction unless your experiment explicitly
changes the prompt.

### `gold.jsonl` — evaluator only

```json
{
  "id": "...",
  "answer": "..."
}
```

### `data.jsonl` — encyclopedia compatibility

```json
{
  "problem": "...",
  "answer": "..."
}
```

As with PHYSICS, your model runner should read `tasks.jsonl`, not `data.jsonl`.

### `metadata.jsonl`

Stores ID, subject, row index and exact HF revision.

## 3. Generate prompt files

All subjects:

```bash
python data/frontierscience_olympiad/make_prompts.py
```

One subject:

```bash
python data/frontierscience_olympiad/make_prompts.py --subject physics
python data/frontierscience_olympiad/make_prompts.py --subject chemistry
python data/frontierscience_olympiad/make_prompts.py --subject biology
```

## 4. Ground truth and output types

The GT is public but heterogeneous.

Typical references include:

```text
numeric answer
algebraic expression
formula with units
chemical formula / compound name
InChI / SMILES / IUPAC identifiers
named biological entity/pathway/method
```

This is why a plain string exact-match evaluator is inadequate.

## 5. Paper evaluation protocol

The FrontierScience paper states:

```text
grader:
  GPT-5 model judge
  reasoning effort = high

Olympiad criterion:
  compare attempted response with short reference answer
  allow true semantic/equivalence matches such as:
    equivalent algebra
    reasonable one-decimal rounding
    equivalent units
    equivalent compound/formula naming
    equivalent entity/method names

solver tools:
  no browsing

trials:
  20 independent trials per problem

metric:
  mean accuracy over the independent trials
```

Important:

```text
20 trials != majority vote
```

If all 100 problems have 20 responses, the reported Olympiad accuracy is the
mean correctness over all 2,000 judged attempts.

## 6. Cheap local development evaluator

For fast iteration without judge API calls:

```bash
pip install -r requirements-local-eval.txt

python data/frontierscience_olympiad/eval/score_local.py \
    predictions.jsonl
```

Prediction format:

```json
{
  "id": "...",
  "response": "reasoning ...\nFINAL ANSWER: ..."
}
```

The local evaluator tries:

```text
normalized exact
→ one-decimal numeric equivalence
→ conservative SymPy equivalence
→ normalized exact phrase
→ unresolved
```

It reports:

```text
lower_bound_accuracy
unresolved_fraction
per-subject statistics
```

Unresolved comparisons are counted incorrect, so this is deliberately
conservative.

**Do not report this as the official FrontierScience score.**

## 7. Model-judge scoring for your own Memory Agent outputs

Install:

```bash
pip install -r requirements-judge.txt
export OPENAI_API_KEY=...
```

For one response per problem:

```json
{"id":"...","response":"...\nFINAL ANSWER: ..."}
```

Run:

```bash
python data/frontierscience_olympiad/eval/score_model_judge.py \
    predictions.jsonl \
    --judge-model gpt-5 \
    --reasoning-effort high \
    --confirm-api-calls
```

The script deliberately requires `--confirm-api-calls` so that you do not
accidentally launch hundreds or thousands of paid grader calls.

### Twenty-trial paper-style inputs

Store one row/problem:

```json
{
  "id": "...",
  "responses": [
    "trial 1 full response",
    "trial 2 full response",
    "... 20 total ..."
  ]
}
```

Then use the same command.

The output reports:

```text
problems = 100
trials_per_problem = 20
attempts = 2000
accuracy = mean correctness over all 2000 attempts
```

No majority vote is applied.

The adapter's judge instruction is a compact paraphrase of the paper's
criterion. This avoids coupling your repository to copied prompt text.

## 8. Exact paper-prompt community implementation

OpenAI publishes the dataset and methodology, but not a dedicated official
FrontierScience evaluation repository.

For a ready-made implementation that uses the paper's Olympiad judge prompt,
this pack supports the UK AISI / Inspect Evals implementation:

```bash
bash data/frontierscience_olympiad/eval/setup_inspect_evals.sh
```

Then, for a baseline model:

```bash
export OPENAI_API_KEY=...

bash data/frontierscience_olympiad/eval/run_inspect_paper_style.sh \
    openai/YOUR_SOLVER_MODEL \
    openai/gpt-5 \
    20
```

Equivalent core command:

```bash
inspect eval inspect_evals/frontierscience \
  --model openai/YOUR_SOLVER_MODEL \
  -T format=olympic \
  -T grader_model=openai/gpt-5 \
  --epochs 20
```

The Inspect Evals project reports that its implementation uses the official
FrontierScience Olympiad judge prompt and validates close to the paper's
published results.

This is a **third-party evaluation code repository**, so record its exact Git
commit (`eval/INSPECT_EVALS_COMMIT.txt`) in your experiment metadata.

## 9. Recommended Memory Encyclopedia setting

For development:

```text
tasks = 100
trials/problem = 1
grader = local lower bound or fixed model judge
browsing = disabled
```

For final paper-comparable evaluation:

```text
tasks = 100
trials/problem = 20
grader = GPT-5
grader reasoning = high
browsing = disabled
metric = mean trial accuracy
```

For your controlled experiment:

```text
No Memory
vs
Memory
```

Keep constant:

- the exact 100 task IDs;
- solver model/version;
- sampling/reasoning settings;
- trial count;
- judge model/version;
- judge reasoning effort;
- evaluator implementation/revision.

Only the memory mechanism should change.

## Registry entry

```text
benchmark: FrontierScience-Olympiad
category: Science / Olympiad expert reasoning
deployment_status: fully_local_data + model_judge_evaluation

public_gold_tasks: 100
subjects:
  physics
  chemistry
  biology

ground_truth: yes
ground_truth_public: yes
ground_truth_type:
  number / expression / chemistry identity / fuzzy entity phrase

modality: text
browsing: disabled in paper

official_dedicated_eval_repo: no
paper_grader: GPT-5 high reasoning
paper_trials_per_problem: 20
paper_metric: mean accuracy
majority_vote: no

fully_offline_official_score: no
local_development_scorer: yes

third_party_paper-prompt_evaluator:
  UKGovernmentBEIS/inspect_evals
```
