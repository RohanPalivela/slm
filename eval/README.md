# Eval Tools

The primary eval path is now the standalone GPU notebook:

```text
notebooks/eval_hf_gpu.ipynb
```

Use the CLI harness only for local smoke tests, local Ollama checks, or rescoring saved generations.

## Local Harness

```bash
python3 eval/harness.py --dry-run
python3 eval/harness.py --split EVAL_HELDOUT --runs 1 --limit 2 --n 2 --no-judge
python3 eval/harness.py --split EVAL_HELDOUT --runs 3 --n 2
```

Outputs are written to `results/`, which is ignored because these files are regenerable.
Each run writes:

```text
litmus_results.md
litmus_results.json
litmus_items.jsonl
generation_attempts.json
```

`generation_attempts.json` preserves every raw generation and its strict-format diagnostic bucket.
The report distinguishes attempted prompts, parsed items, and successfully judged items.
Raw judge responses are stored on each item, parse failures are retried, and unresolved judgments remain inconclusive.
Rejudged artifacts receive a separate metadata sidecar and never overwrite the original item JSONL.

## Model Config

Copy and edit the example config when using the local harness:

```bash
cp eval/models.example.json eval/models.json
```

`eval/models.json` is ignored because local model slugs and endpoints vary by machine.
API keys should stay in environment variables.
Bulk training-data generation requires generator, judge, and verifier entries from three separate model families.
The verifier must unanimously select the keyed answer across its three default solves.
The full training semantic audit should use the separate `training_auditor` entry and refuses a model family found in the legacy generation provenance.

## Bulk Training-Data Generation

```bash
python3 eval/generate.py \
  --split TRAIN \
  --target 6 \
  --repair \
  --out data/generated/train_candidates.jsonl
```

The generator writes a metadata sidecar and a separate `_attempts.json` artifact beside the kept JSONL.
The attempts artifact preserves each rendered request, raw generator and repair response, judge response, verifier response, programmatic result, stage decision, and rejection reason.
Its metadata records sanitized model configurations and SHA-256 revisions for the model configs, prompt, archetype policy, source corpus, split manifest, and selected sources.
Keep the attempt artifact with every generated candidate set, including runs that produce no accepted records.

## Core Files

| File | Role |
| :--- | :--- |
| `harness.py` | Local generation, scoring, aggregation, and report writing |
| `checks.py` / `date_utils.py` | Programmatic schema, craft, leak, and date-direction checks |
| `prompt_loader.py` | Prompt parsing, tolerant JSON extraction, and strict generation-format diagnostics |
| `providers.py` | OpenAI-compatible, Ollama, Anthropic, and mock providers |
| `judge.py` | LLM judge rubric, parse retries, raw-response capture, and inconclusive scoring |
| `generate.py` | Quality-filtered training candidate generation with complete attempt provenance |
| `rescore_results.py` | Recompute reports from saved item outputs |
