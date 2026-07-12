# APUSH SLM

Notebook-first workflow for training and evaluating a Qwen3-4B AP U.S. History item writer.

The matched baseline is the immutable `unsloth/Qwen3-4B` revision recorded in `AGENTS.md`.
The next experimental candidate is `rohanpalviela/qwen3-4b-apush-v5-semantic-preservation-lora`.

## Current Workflow

1. Rebuild and validate the v5 artifacts.

   ```bash
   python3 train/build_v5_dataset.py
   python3 train/format_dataset.py
   python3 scripts/validate_retrain_ready.py
   ```

   The committed v5 artifact passes all deterministic gates and contains only independently audited expert-grade curated anchors.

   ```text
   RETRAIN_READY: yes
   ```

2. Train in Colab with `train/qlora_qwen3_4b.ipynb`.

   The notebook reads `data/generated/train_sft_v5.jsonl` and publishes `rohanpalviela/qwen3-4b-apush-v5-semantic-preservation-lora`.
   It refreshes the repository, verifies the exact SFT SHA-256, and namespaces checkpoints by dataset hash before training.
   It uses LoRA rank 8, alpha 16, an effective batch size of four, one epoch, and a `4e-5` learning rate to reduce semantic drift.

3. Evaluate from Hugging Face with `notebooks/eval_hf_gpu.ipynb`.

   The notebook runs two matched low-temperature repetitions over a frozen 14-source representative subset of the unchanged held-out split.
   This produces 56 logical prompts per candidate and counts failure to produce a valid output within four total attempts as a model failure.
   It uses deterministic per-prompt HF seeds and reports source-clustered paired tests for parsed-item quality and end-to-end attempt outcomes.
   Judge responses are retried, saved raw, and treated as inconclusive if parsing still fails.

4. Inspect failures.

   ```bash
   python3 scripts/analyze_eval_failures.py \
     --items <items.jsonl> \
     --attempts <generation_attempts.json> \
     --out <summary.json>
   ```

5. Rejudge any unavailable evaluations without modifying the original artifacts.

   ```bash
   python3 scripts/rejudge_eval_items.py \
     --items <items.jsonl> \
     --out <items_rejudged.jsonl>
   ```

   The rejudge command also writes a metadata sidecar with input, output, source, rubric, code, and judge-configuration hashes.

## v5 Training Decision

The corrected audited-v4 adapter learned the product contract but regressed from 50% to 27% on matched near-miss quality and from 45% to 23% on expert-grade quality.
V5 preserves the independently reviewed portion of the data while sharply reducing content exposure and adapter update pressure.

- The active clean set has 64 examples across 33 heldout-disjoint training sources.
- Every retained target passed all independent current-rubric expert gates.
- Legacy model-generated survivors and repeated source exposures are excluded.
- The SFT artifact contains 32 cause and 32 effect examples.
- SFT answer positions are exactly balanced at 16 examples each.
- The prompt requires pairwise key uniqueness and exact trap-to-rationale alignment.
- The SFT and inference paths use the same empty-think handling and strict JSON-array contract.

## Canonical Data

| Path | Role |
| :--- | :--- |
| `data/generated/train_v5_clean.jsonl` | 64 independently audited expert-grade v5 item records |
| `data/generated/train_sft_v5.jsonl` | 64 balanced supervised fine-tuning examples |
| `data/generated/train_v5_build_report.json` | Reproducible v5 selection and coverage report |
| `data/generated/train_v4_audited_clean.jsonl` | Preserved audited-v4 input to the v5 selector |
| `data/curated/v4_causal_claims.json` | Traceable court, law, treaty, compact, executive, and policy causal anchors |
| `data/training_archetype_policy.json` | Training-only source and archetype eligibility policy |
| `data/generated/train_clean.jsonl` | Preserved 728-record v3 clean set |
| `data/generated/train_quarantine.jsonl` | Preserved v3 rejects for diagnosis |
| `data/seed_stimuli.jsonl` | Source corpus |
| `data/splits.json` | Train, litmus, and evaluation contamination firewall |

## Evaluation History

- [`docs/07_v3_evaluation_postmortem.md`](docs/07_v3_evaluation_postmortem.md) records the July 10, 2026 full-run results, evaluator limitations, decision, and next actions.
- [`docs/evaluation_results_history.md`](docs/evaluation_results_history.md) consolidates the historical runs and the corrected audited-v4 result.
- [`AGENTS.md`](AGENTS.md) records the durable iteration cycle, project instructions, and current verified baseline.

## Local Ollama Export

After training uploads v5, register the Hugging Face artifact locally only if a Mac or Ollama smoke test is needed.

```bash
python3 scripts/register_ollama_from_hf.py \
  --repo rohanpalviela/qwen3-4b-apush-v5-semantic-preservation-lora \
  --local-dir models/qwen3-apush-v5-semantic-preservation \
  --model-name qwen3-apush-v5-semantic-preservation:latest
```
