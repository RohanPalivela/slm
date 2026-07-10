# Build Log

Current state: **v3 data is ready for retraining**.

## v3 Training Data

Canonical artifacts:

| Path | Count / role |
| :--- | :--- |
| `data/generated/train_clean.jsonl` | 728 audited clean item records |
| `data/generated/train_sft_clean.jsonl` | 728 supervised fine-tuning chat records |
| `data/generated/train_quarantine.jsonl` | 88 rejected records for diagnosis |
| `data/generated/train_audit_report.json` | Reproducible audit summary |

Audit status:

```text
answers: A/B/C/D = 182 each
archetypes: CAUSE_OF_SOURCE = 367, EFFECT_OF_SOURCE = 361
train sources: 68
date-direction failures: 0
verifier-key mismatches: 0
readiness gate: RETRAIN_READY: yes
```

## Fixes Since v2

- Removed the stale pre-clean SFT file from the active repo.
- Aligned the prompt schema with the training targets: options are unlabeled
  strings, while `answer` carries `A|B|C|D`.
- Added `requires_outside_knowledge` to every clean target.
- Rebalanced answer positions and updated verifier metadata when keys moved.
- Added shared decade-aware date parsing for train/eval checks.
- Recovered legitimate `EFFECT_OF_SOURCE` rows that were previously flagged only
  because decade phrases like `late 1890s` were parsed too narrowly.
- Added `scripts/validate_retrain_ready.py` as the pre-training gate.
- Added `scripts/analyze_eval_failures.py` for post-eval failure buckets.
- Updated `notebooks/eval_hf_gpu.ipynb` so the base model is always included in
  the base-vs-tuned summary, even if it emits zero parseable items.

## Run Order

1. Validate:

   ```bash
   python3 scripts/validate_retrain_ready.py
   ```

2. Train:

   ```text
   train/qlora_qwen3_4b.ipynb
   ```

3. Evaluate:

   ```text
   notebooks/eval_hf_gpu.ipynb
   ```

The v3 adapter target is:

```text
rohanpalviela/qwen3-4b-apush-v3-clean-lora
```
