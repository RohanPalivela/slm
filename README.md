# APUSH SLM

Notebook-first workflow for training and evaluating a Qwen3-4B AP U.S. History
item writer.

The current production candidate is the v3 clean LoRA:

```text
rohanpalviela/qwen3-4b-apush-v3-clean-lora
```

## Current Workflow

1. Validate the training artifacts:

   ```bash
   python3 scripts/validate_retrain_ready.py
   ```

   The current v3 artifact passes mechanical gates but now reports known semantic warnings:

   ```text
   RETRAIN_READY: yes_with_warnings
   ```

2. Train in Colab with:

   ```text
   train/qlora_qwen3_4b.ipynb
   ```

   The notebook reads `data/generated/train_sft_clean.jsonl` and publishes the
   adapter as `rohanpalviela/qwen3-4b-apush-v3-clean-lora`.

3. Evaluate from Hugging Face with:

   ```text
   notebooks/eval_hf_gpu.ipynb
   ```

   Start with the one-prompt smoke cell. The committed full-run configuration is:

   ```python
   RUNS = 1
   LIMIT = 0
   N = 2
   ```

   This evaluates all 28 held-out sources × 2 archetypes = 56 paired prompts per
   model. The notebook downloads `apush_eval_results.zip` when it finishes.

4. Inspect failures:

   ```bash
   python3 scripts/analyze_eval_failures.py \
     --items <items.jsonl> \
     --attempts <generation_attempts.json> \
     --out <summary.json>
   ```

5. Before another bulk training run, semantically rejudge a stratified sample:

   ```bash
   python3 scripts/rejudge_training_sample.py --n 100
   ```

   The existing v3 set is heavily speech-weighted and used the same model for its
   judge and verifier. Expand it with independently sourced laws, court opinions,
   treaties, and executive actions before treating a new adapter as a production
   candidate.

## Canonical Data

Use these files for v3:

| Path | Role |
| :--- | :--- |
| `data/generated/train_clean.jsonl` | Audited item records with judge/verifier metadata |
| `data/generated/train_sft_clean.jsonl` | Supervised fine-tuning chat triples |
| `data/generated/train_quarantine.jsonl` | Rejected records kept for diagnosis |
| `data/generated/train_audit_report.json` | Reproducible audit counts |
| `data/seed_stimuli.jsonl` | Source corpus |
| `data/splits.json` | Train/litmus/eval split firewall |

The stale pre-clean SFT artifact is intentionally not kept. If you need to rebuild
the SFT file, run:

```bash
python3 train/audit_dataset.py --in data/generated/train.jsonl --write-clean --backfill-outside-knowledge
python3 train/format_dataset.py
```

The backfill flag is legacy-only for the existing v3 raw artifact. New generation
runs preserve the model's original outside-knowledge explanation and should omit it.

## Repo Layout

```text
train/       Colab training notebook and clean-data formatting/audit scripts
notebooks/   Standalone HF GPU eval notebook
eval/        Shared prompt loading, checks, providers, judge, and local harness
scripts/     Readiness and failure-analysis utilities
prompts/     Current generation prompt used for train/eval formatting
data/        Source corpus, split definitions, and generated training artifacts
docs/        Short build log and retained project notes
```

## Local Ollama Export

After training uploads v3, register the HF artifact locally only if you need a Mac
or Ollama smoke test:

```bash
python3 scripts/register_ollama_from_hf.py \
  --repo rohanpalviela/qwen3-4b-apush-v3-clean-lora \
  --local-dir models/qwen3-apush-v3-clean \
  --model-name qwen3-apush-v3-clean:latest
```
