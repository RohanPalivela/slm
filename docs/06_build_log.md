# Build Log

Current state: **v5 semantic-preservation artifacts pass the retraining gate without warnings**.

The July 10, 2026 full-run analysis is recorded in [`07_v3_evaluation_postmortem.md`](07_v3_evaluation_postmortem.md).
The v3 artifacts remain preserved as the evaluated baseline.

## v5 Training Data

Canonical artifacts:

| Path | Count / role |
| :--- | :--- |
| `data/generated/train_v5_clean.jsonl` | 64 independently audited expert-grade curated targets |
| `data/generated/train_sft_v5.jsonl` | 64 balanced supervised fine-tuning examples |
| `data/generated/train_v5_build_report.json` | Reproducible v5 selection and coverage report |

Verified build status:

```text
answers: A/B/C/D = 16/16/16/16
archetypes: CAUSE_OF_SOURCE = 32, EFFECT_OF_SOURCE = 32
train sources represented: 33
source genres: law 14, court 10, treaty or compact 5, speech or argument 2, executive 2
date direction: pass 62, unknown 2, fail 0
programmatic craft failures: 0
readiness gate: RETRAIN_READY: yes
```

The corrected audited-v4 run established that v4 improved contract reliability while substantially reducing semantic quality.
V5 retains only curated targets that passed every independent current-rubric expert gate.
It excludes the 57 legacy model-generated survivors, removes repeated target exposures, and reduces the adapter from rank 16 to rank 8.
The training schedule changes from four epochs at `8e-5` with effective batch eight to one epoch at `4e-5` with effective batch four.

## v4 Training Data

Canonical artifacts:

| Path | Count / role |
| :--- | :--- |
| `data/generated/train_v4_clean.jsonl` | 122 unique causally screened item records |
| `data/generated/train_sft_v4.jsonl` | 124 balanced supervised fine-tuning examples |
| `data/generated/train_v4_build_report.json` | Reproducible selection and coverage report |
| `data/curated/v4_causal_claims.json` | 65 traceable genre-balancing causal anchors |
| `data/training_archetype_policy.json` | Training-only archetype eligibility policy |

Verified build status:

```text
clean answers: A/B/C/D = 31/31/30/30
effective SFT answers: A/B/C/D = 31/31/31/31
clean archetypes: CAUSE_OF_SOURCE = 62, EFFECT_OF_SOURCE = 60
effective SFT archetypes: CAUSE_OF_SOURCE = 62, EFFECT_OF_SOURCE = 62
train sources represented: 64
source genres: speech 23, law 18, court 10, other 6, treaty or compact 5, executive 2
date direction: pass 118, unknown 4, fail 0
programmatic craft failures: 0
readiness gate: RETRAIN_READY: yes_with_warnings
```

The warnings are part of the artifact, not hidden exceptions.
The 57 retained v3 rows have the older partial judge record and correlated judge/verifier provenance.
Their outside-knowledge field is normalized from the keyed development, with the original generated value preserved on each record.
The 65 curated anchors have not yet received an independent current-rubric semantic audit.

## v4 Decisions

- Replaced automatic legacy selection with manually reviewed allowlists of 29 direct causes and 28 direct effects.
- Added two deterministic repeat exposures to balance the harder effect archetype without retaining weaker labels.
- Excluded generic introductions, biographical trivia, source paraphrases, disputed causal claims, and thematically related but indirect effects.
- Replaced the legacy answer-plus-date outside-knowledge target with the concise keyed development while preserving the original field.
- Removed effect supervision from generic speeches unless the source announced a concrete policy or official action.
- Added 30 public-domain sources and built 65 cause-and-effect anchors across 33 heldout-disjoint laws, court opinions, treaties, compacts, executive actions, and policy texts.
- Added a direct-causality test and adversarial unique-key check to the canonical prompt.
- Made a separately configured third-family key verifier mandatory for future bulk data generation.
- Made the default three-vote key-verification gate unanimous.
- Added complete bulk-generation attempt artifacts with raw responses, stage decisions, rejection reasons, and revision hashes.
- Made the semantic-audit path reject correlated model families and save a complete provenance sidecar.
- Lowered the QLoRA learning rate from `2e-4` to `8e-5`, reduced the effective batch from 16 to 8, and used four epochs on the smaller high-diversity set.
- Made the training notebook refresh and hash-check its dataset, isolate checkpoints by dataset hash, and evaluate one checkpoint per epoch.
- Aligned SFT and inference by stripping the empty Qwen think block and prefilling the required opening JSON-array token.
- Added judge parsing retries, raw judge-response preservation, inconclusive scoring, attempted-prompt metrics, and explicit generation-format buckets.
- Added deterministic per-prompt HF sampling and source-clustered paired tests over both parsed items and end-to-end attempts.

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

1. Rebuild and validate v5:

   ```bash
   python3 train/build_v5_dataset.py
   python3 train/format_dataset.py
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

The v5 adapter target is:

```text
rohanpalviela/qwen3-4b-apush-v5-semantic-preservation-lora
```
