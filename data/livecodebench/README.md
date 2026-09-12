# LiveCodeBench deployment

This deploys **standard LiveCodeBench**, not LiveCodeBench-Pro.

Pinned benchmark choice:

- scenario: `codegeneration`
- dataset: `livecodebench/code_generation_lite`
- formal release: `release_v6`
- formal size: 1055 cumulative problems
- primary metric for a one-candidate memory system: `pass@1`

## Why standard LCB is suitable here

The official code-generation evaluator uses a modified APPS-style Python checker.
It does not require LightCPVerifier, go-judge, privileged Docker, or benchmark-wide
cgroup support. This avoids the blocker encountered with LiveCodeBench-Pro.

## Memory-system interface

Your memory system does not have to be registered as a built-in LiveCodeBench
`--model`. Recommended flow:

1. Read `tasks.jsonl`.
2. For each task, let the entire memory system generate one executable Python solution.
3. Write one JSONL row:
   `{"question_id":"...","code":"..."}`
4. Convert to official custom-evaluator format.
5. Run the official evaluator.

The `code` field should be executable source code, not an explanation. Markdown
fences can optionally be stripped by the converter.

## Ground truth separation

- `tasks.jsonl`: model-safe input. No public/private test cases.
- `gold.jsonl`: evaluator/provenance view. Public tests are included; private-test
  bodies are not duplicated, but SHA256 hashes and the upstream dataset reference are
  recorded. The official evaluator reads full GT from the HF dataset cache.
- `data.jsonl`: convenience view, not model input.
- `metadata.jsonl`: analysis fields only.

The full private test payload is several GB; duplicating it into `gold.jsonl` would
waste storage, so the canonical GT remains in the pinned HF dataset snapshot.

## Recommended sequence

Create/activate a clean Python 3.11 environment, then:

```bash
source data/livecodebench/eval/env.sh
bash data/livecodebench/eval/setup_livecodebench.sh

# Small infrastructure smoke: fine-grained v6 slice
bash data/livecodebench/eval/run_dummy_smoke.sh

# Formal cumulative release_v6
python data/livecodebench/eval/download_release.py --config release_v6
python data/livecodebench/build.py
python data/livecodebench/validate.py
python data/livecodebench/eval/doctor.py
```

For your memory system:

```bash
# produce data/livecodebench/predictions/predictions.jsonl
python data/livecodebench/eval/convert_predictions.py \
  --input data/livecodebench/predictions/predictions.jsonl \
  --output data/livecodebench/predictions/custom_outputs.json \
  --strip-fences

bash data/livecodebench/eval/run_custom_eval.sh \
  data/livecodebench/predictions/custom_outputs.json
```

## Security

The official evaluator executes generated code locally. It is not a hardened
security sandbox. Run model-generated code in an isolated evaluation account,
container, or VM with no secrets and restricted filesystem/network access.
