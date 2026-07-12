# APUSH SLM Project Instructions and Memory

This file is the durable, human-maintained memory and instruction source for the APUSH SLM project.
Generated Codex memories may provide helpful recall, but this file and the checked-in documentation are authoritative.

## Project objective

Fine-tune Qwen3-4B to generate historically correct, uniquely keyed, stimulus-based AP U.S. History multiple-choice questions.
The desired output must be structurally valid, use genuine outside knowledge, test the requested historical reasoning skill, and contain plausible distractors.

## Canonical workflow

- Validate training artifacts with `python3 scripts/validate_retrain_ready.py`.
- Train with `train/qlora_qwen3_4b.ipynb`.
- Evaluate with `notebooks/eval_hf_gpu.ipynb` on the held-out split.
- Analyze saved `items.jsonl`, `generation_attempts.json`, and `summary.json` artifacts.
- Preserve every full-run result set so later runs can be compared against the same baseline.

## Iterative improvement cycle

Repeat this cycle until the tuned model clears the quality target with stable results.

1. Receive and preserve the complete evaluation artifacts.
2. Validate the evaluation itself, including expected prompt count, parse failures, judge failures, denominators, and model revisions.
3. Reproduce important failures from the raw generation through final scoring.
4. Compare base, tuned, and teacher results on matched prompts.
5. Inspect representative successes, regressions, and failures instead of relying only on aggregate buckets.
6. Separate confirmed observations from hypotheses about training data, training method, inference settings, and evaluation code.
7. Brainstorm candidate fixes and rank them by expected quality, robustness, scalability, and long-term maintainability.
8. Make a traceable set of changes to the training data, training method, inference path, or evaluator.
9. Validate the revised dataset and evaluation path before spending resources on training.
10. Train a versioned adapter and record the exact base revision, data revision, method, and inference configuration.
11. Rerun the same held-out evaluation, preferably with multiple runs or enough samples to quantify uncertainty.
12. Write a dated postmortem, update this file with verified conclusions and next priorities, and repeat.

## Evaluation expectations

- Report generation reliability over all attempted prompts, not only parsed items.
- Compare base and tuned models on matched prompts and report paired statistical tests.
- Treat judge or parser failures as evaluation-system failures that must be reported separately from model-quality failures.
- Inspect representative items before changing the training data or method.
- Run `python3 scripts/validate_retrain_ready.py` before declaring a training artifact ready.

## Current baseline

The first full v3 evaluation ran on July 10, 2026.
It used 28 held-out sources, two archetypes per source, one deterministic run, and 56 attempted prompts per model.
The evaluated adapter was `rohanpalviela/qwen3-4b-apush-v3-clean-lora` on base revision `64033659d5caf1b8ed7f929b29de705e93a4d468`.
The teacher was `claude-group/claude-opus-4-8`, and the judge was `openai-group/gpt-5.5`.

Observed parsed-item results:

| Model | Generated | Expert-grade | Near-miss | Key valid | Distillable |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-4B base | 56/56 | 25% | 30% | 59% | 32% |
| Qwen3 APUSH v3 | 50/56 | 30% | 32% | 48% | 42% |
| Teacher | 56/56 | 73% | 75% | 100% | 77% |

The tuned model sharply improved programmatic structure.
Craft failures fell from 45% to 10%, and schema failures fell from 29% to 6%.
The run did not demonstrate a statistically significant improvement in expert quality, key validity, or distillability.
The teacher result confirms that the task is feasible and remains a good distillation target.

The full analysis is in `docs/07_v3_evaluation_postmortem.md`.

## Verified lessons from the first run

- The current adapter learned the output schema and distractor packaging better than the base model.
- Historical correctness, unique answer keys, and direct cause-and-effect relationships remain the main model-quality problems.
- `EFFECT_OF_SOURCE` remains harder than `CAUSE_OF_SOURCE` for both the tuned model and the teacher.
- Only 12 of 56 tuned responses were strict top-level JSON arrays.
- Thirty-one tuned responses contained at least one complete item followed by repeated or truncated output, seven were strict single objects, and six were single objects with an unmatched trailing array bracket.
- Ten tuned items received unparseable judge responses and were automatically scored as failures.
- Judge parse failures are disproportionately concentrated in the tuned set, so semantic conclusions must remain provisional until those items are rejudged.
- Quality metrics need an attempted-prompt denominator alongside the parsed-item denominator.
- A single deterministic run is insufficient for a confident production decision.

## Evaluation runtime lesson

- The standalone GPU evaluator originally ran 504 generations and every judge call serially at batch size one, which underused the L4 and made long runs fragile.
- Keep candidate repetitions batched, use a separately counted teacher reference pass, bound API concurrency, and preserve append-only checkpoints on persistent storage.
- After installing or repairing GPU dependencies in Colab, restart the Python runtime before importing Transformers; otherwise stale `huggingface_hub` modules can mix with newly installed package files.

## Next iteration priorities

1. Preserve the complete corrected audited-v4 result archive before beginning the v5 run.
2. Train the versioned v5 semantic-preservation adapter from the immutable base revision and pinned v5 dataset hash.
3. Run the unchanged two-repetition evaluation over the frozen 14-source representative subset.
4. Require v5 to avoid regressions against base on near-miss, key validity, and label cleanliness while retaining the contract improvement.
5. Report all-logical-prompt mechanical rates separately from shared-exclusion semantic rates.
6. Inspect every base-pass and v5-fail pair before accepting or redesigning v5.
7. Write a new dated postmortem after the complete v5 artifacts arrive.

## Current v4 experiment

The v4 training artifacts were built on July 10, 2026 in response to the first full evaluation.
The active clean set contains 122 unique examples across 64 heldout-disjoint training sources.
It retains 57 manually selected v3 survivors and adds 65 curated causal anchors across 33 public-domain laws, court opinions, treaties, compacts, executive actions, and policy texts.
The formatted SFT artifact contains 62 cause and 62 effect examples with 31 examples at each answer position.
Generic speeches no longer supply effect supervision unless they announce a concrete policy or official action with a defensible downstream consequence.
Future bulk data generation requires a separately configured third-family key verifier by default.
The default three-solve key gate requires unanimous agreement, and every generation run preserves raw attempts, stage decisions, rejection reasons, and revision hashes.

The v4 QLoRA notebook uses a lower `8e-5` learning rate, an effective batch size of eight, and four epochs.
The intent is to preserve base-model historical knowledge while teaching the stricter output and causality contract.
The notebook refreshes and hash-checks the exact SFT artifact, isolates checkpoints by dataset hash, and evaluates once per epoch before selecting the best checkpoint.
The training and inference paths now share the same empty-think handling and strict JSON-array prefix.

The evaluator now saves raw judge responses, retries parse failures, marks unresolved judgments inconclusive, reports attempted-prompt success, and buckets malformed generation shapes explicitly.
It also uses deterministic per-prompt HF seeds and source-clustered paired tests for parsed quality and end-to-end attempt outcomes.
These are verified implementation changes, not model-quality results.

The v4 readiness gate currently returns `yes_with_warnings`.
The 57 legacy rows have only the older partial judge record and correlated judge/verifier provenance.
Their outside-knowledge field is normalized from the keyed development, and the original generated value remains preserved on each row.
The 65 curated anchors still need independent current-rubric review before any production decision.
The semantic-audit command must use an auditor family absent from the legacy provenance and preserve its metadata sidecar with the reviewed JSONL.

## Evaluator protocol correction

The July 11 base-versus-tuned run is not a valid semantic comparison because the base generation path stripped Qwen's native no-thinking prefill, forced an opening array token, and failed to reject the resulting thinking output.
Use the pinned base tokenizer for both adapter states, retain the native no-thinking prefill, leave the forced array prefix off, and require the full generation-only LITMUS execution/protocol preflight to pass before teacher or judge calls.
The semantic evaluation notebook hardcodes this production generation protocol; run protocol ablations in a separate generation-only notebook.
The default semantic run uses a frozen 14-source representative subset of `EVAL_HELDOUT`, retaining all six source genres and two matched candidate repetitions for 140 scored generation attempts.
The default comparison conditions expert quality on the first mechanically contract-valid output from a shared bounded retry policy; preserve and report every raw trial, first-pass validity, and retry burden separately for base and tuned.
If either candidate exhausts the retry budget, exclude that exact matched run-source-archetype prompt from judging for both candidates, preserve the failed trials, report the exclusion, and continue the run.
Treat the tuned malformed-suffix cause as unresolved until the separate GPU inference ablation is complete.

## Corrected audited-v4 result and v5 decision

The corrected audited-v4 evaluation completed on July 12, 2026 over the frozen 14-source cohort with two matched candidate repetitions.
The base model exhausted the bounded contract retry policy on 12 of 56 prompts, while the tuned model exhausted none.
Those 12 prompts were excluded from semantic judging for both candidates, leaving 44 matched judged prompts per candidate and no judge outages.
Audited v4 improved first-pass contract validity from 39% to 82% and improved all-prompt product-contract validity by 21 percentage points.
It regressed from 50% to 27% on matched near-miss quality and from 45% to 23% on expert-grade quality.
The paired near-miss result had 5 improvements and 15 regressions with exact McNemar `p = 0.041`.
The source-clustered near-miss mean delta was -20.8 percentage points with a 95% bootstrap interval from -39.9 to -2.4 points and a marginal sign-flip `p = 0.066` across 14 sources.
Reject the audited-v4 checkpoint for promotion.

V5 uses only the 64 independently audited expert-grade curated causal anchors.
It removes all legacy model-generated survivors, repeated target exposure, and the one audited record that failed a strict expert gate.
The v5 set contains 32 cause and 32 effect examples, 16 examples at each answer position, and one exposure per target.
The v5 notebook uses LoRA rank 8, alpha 16, an effective batch size of four, one epoch, and a `4e-5` learning rate to reduce cumulative update pressure after the v4 semantic regression.
The evaluator now treats `trap_types` order and wrong-option rationale prefixes as a mechanical schema contract.
It also labels all-prompt lower bounds and shared-exclusion semantic rates separately so excluded prompts cannot silently change the denominator behind an attempted-prompt column.

## Memory maintenance rules

- Preserve raw evaluation artifacts and distinguish observed facts from hypotheses.
- Keep historical postmortems immutable except for factual corrections.
- Add a new dated postmortem under `docs/` for every full evaluation run.
- Record exact model, adapter, dataset, prompt, evaluator, and inference revisions.
- Update this file only with verified results, accepted decisions, and the next iteration priorities.
- Keep hypotheses labeled until a controlled rerun supports them.
- Never place API keys, access tokens, private source text, or other secrets in this file.
