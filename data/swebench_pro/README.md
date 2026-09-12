# SWE-bench Pro

This deployment targets the **public SWE-bench Pro split**.

As of 2026-09-09:

```text
paper benchmark:
  1,865 problems
  41 repositories

public HF split:
  731 problems
  11 open-source repositories

held-out:
  12 repositories
  private

commercial:
  18 proprietary repositories
  private
```

The public 731 are the portion you can fully self-host.

## 1. Materialize public tasks

```bash
pip install -r requirements-data.txt

python data/swebench_pro/build.py
python data/swebench_pro/validate.py
```

Generated:

```text
data/swebench_pro/
├── data.jsonl
├── tasks.jsonl
├── gold.jsonl
├── metadata.jsonl
├── raw.jsonl
├── raw.csv
└── MANIFEST.json
```

### `tasks.jsonl` — model/agent input

Contains only model-visible task context:

```json
{
  "instance_id": "...",
  "repo": "owner/repo",
  "base_commit": "...",
  "problem_statement": "...",
  "repo_language": "...",
  "dockerhub_tag": "..."
}
```

It may also contain public issue context such as `requirements` or `interface`.

It deliberately excludes:

```text
patch
test_patch
fail_to_pass
pass_to_pass
selected_test_files_to_run
before_repo_set_cmd
```

Those are evaluator/GT fields and must not leak into the agent context.

### `gold.jsonl` — evaluator-only GT

```json
{
  "instance_id": "...",
  "patch": "diff --git ...",
  "test_patch": "...",
  "fail_to_pass": [...],
  "pass_to_pass": [...]
}
```

### `raw.jsonl`

Exact upstream HF records used by the official evaluator.

### `data.jsonl`

Encyclopedia compatibility:

```json
{
  "problem": "<problem_statement>",
  "answer": "<gold patch>"
}
```

Never use this file as model input.

## 2. Why SWE-bench Pro is not a normal problem/answer benchmark

The actual task is:

```text
issue
  +
repository @ base_commit
        ↓
coding agent
  edits files / runs commands / inspects tests
        ↓
git diff
        ↓
Docker evaluator
        ↓
fail_to_pass tests all pass
AND
pass_to_pass tests still pass
        ↓
resolved = true/false
```

Therefore the repository environment is part of the benchmark input.

## 3. Install the official evaluation harness

```bash
bash data/swebench_pro/eval/setup_official.sh
```

This clones with submodules:

```text
external/SWE-bench_Pro-os/
```

and saves:

```text
data/swebench_pro/eval/OFFICIAL_COMMIT.txt
```

Install the upstream evaluator dependencies in a dedicated environment:

```bash
conda create -n swebench-pro python=3.11 -y
conda activate swebench-pro

pip install -r external/SWE-bench_Pro-os/requirements.txt
```

Do not merge the entire agent/evaluator stack into your main memory environment
unless you deliberately want those versions there.

## 4. Docker

Official reproducible evaluation uses per-instance Docker images.

Check:

```bash
docker version
docker info
```

Images are hosted under:

```text
jefzda/sweap-images
```

and each HF task contains its image tag.

The official repository recommends Modal for large evaluations but also
supports local Docker via:

```text
--use_local_docker
```

This deployment uses local Docker by default.

## 5. Smoke-test the evaluation harness with gold patches

First test one public task:

```bash
python data/swebench_pro/eval/make_gold_patches.py \
  --limit 1 \
  --output gold_1.json

bash data/swebench_pro/eval/run_local_docker.sh \
  gold_1.json \
  swebench_pro_eval_outputs/gold_1 \
  1
```

If the environment is healthy, the resulting task should resolve.

Then optionally test several:

```bash
python data/swebench_pro/eval/make_gold_patches.py \
  --limit 5 \
  --output gold_5.json

bash data/swebench_pro/eval/run_local_docker.sh \
  gold_5.json \
  swebench_pro_eval_outputs/gold_5 \
  2
```

Do this before spending money on agent inference.

## 6. Running your Memory Agent

The benchmark itself does not dictate that your solver must be SWE-Agent.
For your project, the clean abstraction is:

```text
for task in tasks.jsonl:
    start task Docker/repository environment
    checkout base_commit
    give agent problem_statement
    allow shell/editor/test interactions
    run No-Memory or Memory scaffold
    save `git diff`
```

Your output should look like:

```json
{
  "instance_id": "...",
  "patch": "diff --git a/... b/...\n..."
}
```

one row per task.

If your agent saves a full response containing a diff, the normalizer also
accepts:

```json
{
  "instance_id": "...",
  "response": "```diff\n...\n```"
}
```

## 7. Convert agent output to official patch JSON

```bash
python data/swebench_pro/eval/prepare_patches.py \
  predictions.jsonl \
  --prefix memory_model_run1 \
  --output patches.json
```

For development on a subset:

```bash
python data/swebench_pro/eval/prepare_patches.py \
  predictions_subset.jsonl \
  --prefix dev \
  --output patches_dev.json \
  --allow-partial
```

Official patch JSON:

```json
[
  {
    "instance_id": "...",
    "patch": "diff --git ...",
    "prefix": "memory_model_run1"
  }
]
```

## 8. Evaluate patches locally

Small development run:

```bash
bash data/swebench_pro/eval/run_local_docker.sh \
  patches_dev.json \
  swebench_pro_eval_outputs/dev \
  2
```

Full public run:

```bash
bash data/swebench_pro/eval/run_local_docker.sh \
  patches.json \
  swebench_pro_eval_outputs/full \
  16
```

Choose workers according to CPU, RAM, disk and Docker capacity. Do not blindly
use the upstream example's 100 workers on a single machine.

The wrapper calls the official:

```text
external/SWE-bench_Pro-os/swe_bench_pro_eval.py
```

with:

```text
raw_sample_path = data/swebench_pro/raw.jsonl
scripts_dir     = external/SWE-bench_Pro-os/run_scripts
dockerhub       = jefzda
use_local_docker
block_network
```

## 9. Score semantics

For each instance, the official evaluator gets the test output and computes:

```text
passed_tests = tests with status PASSED

resolved =
    (fail_to_pass ∪ pass_to_pass)
    ⊆ passed_tests
```

So one instance is simply:

```text
resolved / not resolved
```

Primary metric:

```text
% Resolved
```

Summarize the official output:

```bash
python data/swebench_pro/eval/summarize.py \
  swebench_pro_eval_outputs/full/eval_results.json
```

This additionally reports resolution rate by repository and language.

## 10. Model generation through the official scaffold

If you want strict leaderboard-style generation instead of your own Memory
Agent, the official repository contains the SWE-Agent submodule and an example
Claude config. Scale reports that this setup reproduces its Sonnet 4.5 result.

For the Memory Encyclopedia, however, using your own scaffold is appropriate as
long as:

- task set is identical;
- repository/base commit is identical;
- evaluator is identical;
- tool/environment permissions are fixed;
- turn/token/cost limits are fixed;
- only memory differs between conditions.

## 11. Current benchmark-maintenance caveat

The official repo contains maintenance notes about outdated tests and states
that leaderboard issues have been under review.

Also:

```text
current HF public dataset = 731
current official leaderboard denominator may differ slightly
```

Therefore every result should archive:

```text
HF revision from MANIFEST.json
official evaluator commit from OFFICIAL_COMMIT.txt
Docker image/tag
agent scaffold commit
model version
turn/token/cost limit
network policy
```

Do not compare numbers from different benchmark revisions as if they were the
same test set.

## 12. Recommended memory experiment

Development:

```text
20-50 task stratified subset
local Docker
1 attempt/task
fixed agent
```

Main public experiment:

```text
731 public tasks
No Memory vs Memory
same agent scaffold
same tool policy
same Docker images
same turn/cost limit
metric = % Resolved
```

This is a high-value memory benchmark because tasks require long-horizon
repository navigation, repeated test feedback, cross-file reasoning and
persistent workspace state.

## Registry entry

```text
benchmark: SWE-bench Pro
category: Code / repository-level software engineering

deployment_status:
  public split: fully self-hostable
  held-out/commercial: private

public_tasks: 731
public_repos: 11
full_paper_tasks: 1865

ground_truth: yes
public_GT_for_public_split: yes
ground_truth_type:
  gold patch + programmatic regression tests

model_input:
  issue + repository at base_commit

output:
  repository patch / git diff

official_evaluator:
  scaleapi/SWE-bench_Pro-os

docker_required: yes
prebuilt_images: yes
third_party_task_repositories: yes
llm_judge: no

primary_metric:
  percent resolved
```
