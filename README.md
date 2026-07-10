# APUSH SLM

Notebook-first workflow for training and evaluating a Qwen3-4B AP U.S. History item writer.

The evaluated baseline is `rohanpalviela/qwen3-4b-apush-v3-clean-lora`.
The next experimental candidate is `rohanpalviela/qwen3-4b-apush-v4-semantic-lora`.

## Current Workflow

1. Rebuild and validate the v4 artifacts.

   ```bash
   python3 train/build_v4_dataset.py
   python3 train/format_dataset.py
   python3 scripts/validate_retrain_ready.py
   ```

   The committed v4 artifact passes all deterministic gates and reports the remaining semantic-audit limitations explicitly.

   ```text
   RETRAIN_READY: yes_with_warnings
   ```

   To remove those warnings before training, run the complete third-family audit, apply its quarantine, reformat the audited output, and validate the resulting files.
   The audit refuses correlated fallback models and saves a metadata sidecar with the exact dataset, source, rubric, and auditor hashes.

   ```bash
   python3 scripts/rejudge_training_sample.py --n 0
   python3 scripts/apply_training_semantic_audit.py
   python3 train/format_dataset.py \
     --in data/generated/train_v4_audited_clean.jsonl \
     --out data/generated/train_sft_v4_audited.jsonl
   python3 scripts/validate_retrain_ready.py \
     --clean data/generated/train_v4_audited_clean.jsonl \
     --sft data/generated/train_sft_v4_audited.jsonl
   ```

2. Train in Colab with `train/qlora_qwen3_4b.ipynb`.

   The notebook reads `data/generated/train_sft_v4.jsonl` and publishes `rohanpalviela/qwen3-4b-apush-v4-semantic-lora`.
   Set `USE_AUDITED_DATA = True` only when the audited artifacts above exist; the notebook then uses a separate `-audited` run name so checkpoints cannot mix.
   The provisional path refreshes the repository, verifies the exact SFT SHA-256, and namespaces checkpoints by dataset hash before training.
   It trains for four lower-learning-rate epochs at `8e-5` with an effective batch size of eight so the compact dataset receives enough updates without aggressively overriding base-model historical knowledge.

3. Evaluate from Hugging Face with `notebooks/eval_hf_gpu.ipynb`.

   The notebook runs three matched low-temperature repetitions over the unchanged 28-source held-out split.
   This produces 168 attempted prompts per model and reports attempted, parsed, and successfully judged denominators separately.
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

## v4 Training Decision

The v3 adapter learned schema and distractor packaging but did not show a statistically significant semantic gain.
The v4 iteration therefore changes supervision quality and exposure rather than increasing adapter capacity.

- The active clean set has 122 unique examples across 64 heldout-disjoint training sources.
- It retains 57 manually selected v3 survivors and adds 65 curated cause-and-effect anchors.
- Training coverage now includes 10 court opinions, 18 laws or constitutional texts, 5 treaties or compacts, and 2 executive actions.
- Generic speeches no longer provide effect supervision unless they announce a concrete policy or official action with a defensible downstream consequence.
- The SFT artifact contains 62 cause and 62 effect examples.
- SFT answer positions are exactly balanced at 31 examples each.
- The prompt now requires a concrete causal chain and an adversarial unique-key check.
- The SFT and inference paths use the same empty-think handling and strict JSON-array contract.

The readiness warning is intentional.
The 57 legacy survivors contain the older partial judge record and used the same model as judge and verifier.
Their outside-knowledge field is normalized from the keyed development while the original value remains preserved for traceability.
The 65 curated anchors also need an independent current-rubric semantic audit before any production decision.
The next evaluation remains useful as an experimental test of the v4 hypothesis, but these limitations must stay visible.

## Canonical Data

| Path | Role |
| :--- | :--- |
| `data/generated/train_v4_clean.jsonl` | 122 unique deterministically screened v4 item records |
| `data/generated/train_sft_v4.jsonl` | 124 balanced supervised fine-tuning examples |
| `data/generated/train_v4_build_report.json` | Reproducible v4 selection and coverage report |
| `data/curated/v4_causal_claims.json` | Traceable court, law, treaty, compact, executive, and policy causal anchors |
| `data/training_archetype_policy.json` | Training-only source and archetype eligibility policy |
| `data/generated/train_clean.jsonl` | Preserved 728-record v3 clean set |
| `data/generated/train_quarantine.jsonl` | Preserved v3 rejects for diagnosis |
| `data/seed_stimuli.jsonl` | Source corpus |
| `data/splits.json` | Train, litmus, and evaluation contamination firewall |

## Evaluation History

- [`docs/07_v3_evaluation_postmortem.md`](docs/07_v3_evaluation_postmortem.md) records the July 10, 2026 full-run results, evaluator limitations, decision, and next actions.
- [`AGENTS.md`](AGENTS.md) records the durable iteration cycle, project instructions, and current verified baseline.

## Local Ollama Export

After training uploads v4, register the Hugging Face artifact locally only if a Mac or Ollama smoke test is needed.

```bash
python3 scripts/register_ollama_from_hf.py \
  --repo rohanpalviela/qwen3-4b-apush-v4-semantic-lora \
  --local-dir models/qwen3-apush-v4-semantic \
  --model-name qwen3-apush-v4-semantic:latest
```
