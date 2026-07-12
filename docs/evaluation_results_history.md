# APUSH Evaluation Results History

Last updated: July 12, 2026.

This document consolidates every evaluation result currently recoverable from the repository and its Git history.
Percentages are rounded to one decimal place.
The July 10 v3 run remains the full-split historical baseline, and the July 12 corrected audited-v4 run is the first valid comparison under the current matched protocol.

## How to read the metrics

- **Parse success** is the percentage of attempted prompts that produced at least one parsed item.
- **Expert-grade** is the strict all-around quality pass rate among parsed and judged items.
- **Near-miss** is the more permissive quality pass rate among parsed and judged items.
- **Key valid** means the keyed answer was historically correct and uniquely best.
- **Distillable** means the item cleared the evaluator's threshold for use as a strong training target.
- **Craft fail**, **schema fail**, and **date fail** are failure rates, so lower is better.
- **End-to-end** rates use every attempted prompt as the denominator, including malformed or empty generations.

Metrics from different evaluator versions are preserved as originally reported.
They should not be treated as perfectly interchangeable across runs.

## Run inventory

| Date | Run | Scope | Data status | Comparison status |
| :--- | :--- | :--- | :--- | :--- |
| July 7, 2026 | Early litmus Run 1 | Base candidate and teacher on 10 litmus sources | Summary report only; raw item artifacts are unavailable | Exploratory build-gate |
| July 10, 2026 | v3 full evaluation | Base, v3 adapter, and teacher on 28 held-out sources | Complete raw attempts, items, and summary recoverable from Git | Authoritative historical baseline with evaluator caveats |
| July 11, 2026 | v4 full evaluation attempt | Base, v4 adapter, and teacher on 28 held-out sources | Complete raw attempts, items, and summary recoverable from Git | Invalid base-versus-tuned semantic comparison |
| July 12, 2026 | Corrected audited-v4 evaluation | Frozen 14-source representative subset, two candidate repetitions | Complete notebook summary supplied; raw result archive not yet checked into the repository | Valid matched comparison with 12 shared semantic exclusions |

## July 7, 2026: early litmus Run 1

This was an exploratory build-gate using the original rubric.
The run covered 10 `LITMUS` sources and evaluated the local Qwen3-4B candidate against the teacher.
Only the written diagnosis is recoverable, so prompt-level results cannot currently be reanalyzed.

### Reported item-level percentages

| Model | Scored items | Expert-grade | Key valid | Date fail | Source leak |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-4B candidate | 30 | 13.0% | 43.0% | 10.0% | 0.0% |
| Claude Opus 4.8 teacher | 180 | 28.0% | 98.0% | 1.0% | 0.0% |

### Expert-grade rate by archetype

| Model | `CAUSE_OF_SOURCE` | `EFFECT_OF_SOURCE` |
| :--- | ---: | ---: |
| Qwen3-4B candidate | 13.0% | Not reported |
| Claude Opus 4.8 teacher | 29.0% | 27.0% |

The teacher's low expert-grade rate was driven primarily by implausibly easy wrong-era distractors.
Its answer keys were still valid on 98.0% of scored items.
The resulting decision was `RETHINK`, followed by a tighter distractor-subtlety rule.
No completed Run 2 results were found in the current repository or its tracked history.

## July 10, 2026: v3 full evaluation

This run used all 28 held-out sources, two archetypes per source, and one deterministic attempt per prompt.
Each model received 56 attempted prompts.
The adapter was `rohanpalviela/qwen3-4b-apush-v3-clean-lora` on base revision `64033659d5caf1b8ed7f929b29de705e93a4d468`.

### Parsed-item percentages

| Model | Parsed / attempted | Parse success | Expert-grade | Near-miss | Key valid | Distillable | Craft fail | Schema fail | Date fail |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-4B base | 56 / 56 | 100.0% | 25.0% | 30.4% | 58.9% | 32.1% | 44.6% | 28.6% | 0.0% |
| Qwen3 APUSH v3 | 50 / 56 | 89.3% | 30.0% | 32.0% | 48.0% | 42.0% | 10.0% | 6.0% | 4.0% |
| Claude Opus 4.8 teacher | 56 / 56 | 100.0% | 73.2% | 75.0% | 100.0% | 76.8% | 23.2% | 0.0% | 0.0% |

### Generation reliability and end-to-end quality

| Model | Strict top-level JSON array | End-to-end near-miss |
| :--- | ---: | ---: |
| Qwen3-4B base | 100.0% | 30.4% |
| Qwen3 APUSH v3 | 21.4% | 28.6% |
| Claude Opus 4.8 teacher | 100.0% | 75.0% |

The v3 adapter improved craft and schema compliance substantially.
It did not establish a statistically significant improvement in expert quality, key validity, or distillability.
Ten of the 50 parsed tuned items, or 20.0%, received unparseable judge responses that the old evaluator automatically converted into failures.
The semantic comparison therefore remains qualified by judge-system failures.

### Matched base-versus-tuned changes

The paired analysis used the 50 prompts for which both base and tuned generations produced parsed items.

| Metric | Base failed, tuned passed | Base passed, tuned failed | Exact McNemar p-value |
| :--- | ---: | ---: | ---: |
| Near-miss | 11 / 50, or 22.0% | 11 / 50, or 22.0% | 1.000 |
| Key valid | 9 / 50, or 18.0% | 16 / 50, or 32.0% | 0.230 |
| Distillable | 14 / 50, or 28.0% | 10 / 50, or 20.0% | 0.541 |

None of the paired results reached the conventional `p < 0.05` threshold.
The complete interpretation is preserved in [`07_v3_evaluation_postmortem.md`](07_v3_evaluation_postmortem.md).

## July 11, 2026: invalid v4 full evaluation attempt

This run attempted three repetitions for the base and v4 adapter over 28 held-out sources, plus one teacher pass.
It produced 168 attempted prompts per candidate and 56 teacher prompts.
The adapter was `rohanpalviela/qwen3-4b-apush-v4-semantic-lora` at revision `7a42984265f971b3e8bcec3678c2108a512679ee`.

The base path removed Qwen's native no-thinking prefill, forced an opening JSON-array token, and failed to reject the resulting thinking output.
This caused 167 of 168 base generations to produce no parsed item.
The run cannot support a semantic base-versus-v4 quality conclusion.
Its percentages remain useful for documenting the protocol failure and the tuned model's standalone behavior under that specific inference setup.

### Parsed-item percentages as originally recorded

| Model | Parsed / attempted | Parse success | Expert-grade | Near-miss | Key valid | Distillable | Craft fail | Schema fail | Date fail |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-4B base | 1 / 168 | 0.6% | 100.0%* | 100.0%* | 100.0%* | 100.0%* | 0.0%* | 0.0%* | 0.0%* |
| Qwen3 APUSH v4 | 135 / 168 | 80.4% | 26.7% | 34.8% | 53.3% | 47.4% | 14.1% | 0.0% | 6.7% |
| Claude Opus 4.8 teacher | 56 / 56 | 100.0% | 66.1% | 66.1% | 98.2% | 69.6% | 28.6% | 0.0% | 0.0% |

`*` The base percentages use a denominator of one parsed item and have no meaningful comparative value.

### Attempt-level percentages

| Model | Parse success | Strict JSON array | End-to-end near-miss | End-to-end key valid | End-to-end distillable |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-4B base | 0.6% | 0.0% | 0.6% | 0.6% | 0.6% |
| Qwen3 APUSH v4 | 80.4% | 81.0% | 28.0% | 42.9% | 38.1% |
| Claude Opus 4.8 teacher | 100.0% | 100.0% | 66.1% | 98.2% | 69.6% |

The preserved summary records 136 tuned strict arrays but 135 parsed and scored tuned items.
This one-record difference is reported directly rather than silently reconciled.

## July 12, 2026: corrected audited-v4 evaluation

This run used the corrected production generation protocol on the frozen 14-source representative subset.
It used two matched low-temperature repetitions for each candidate and one teacher pass.
Each candidate received 56 logical prompts, and the teacher received 28 logical prompts.

The base model exhausted the eight-attempt mechanical retry budget on 12 prompts.
The tuned model exhausted no prompts.
The shared policy excluded those same 12 prompts from semantic judging for both candidates, leaving 44 matched and judged candidate prompts.
There were no judge outages.

### Eligible semantic quality

| Model | Eligible / logical | Expert-grade | Near-miss | Key valid | Label clean | Craft fail | Date fail |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-4B base | 44 / 56 | 45.5% | 50.0% | 65.9% | 61.4% | 11.4% | 9.1% |
| Qwen3 APUSH audited v4 | 44 / 56 | 22.7% | 27.3% | 56.8% | 45.5% | 11.4% | 2.3% |
| Claude Opus 4.8 teacher | 28 / 28 | 67.9% | 67.9% | 96.4% | 67.9% | 28.6% | 0.0% |

### Mechanical reliability

| Model | First-pass contract valid | Raw generations | Retried prompts | Mean generations per valid output | Retry exhausted |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Qwen3-4B base | 39.3% | 197 | 34 | 4.48 | 12 |
| Qwen3 APUSH audited v4 | 82.1% | 67 | 10 | 1.20 | 0 |
| Claude Opus 4.8 teacher | 92.9% | 30 | 2 | 1.07 | 0 |

The adapter produced a large and statistically clear product-contract improvement.
At the logical-prompt level, tuned passed schema and product contract on 12 prompts where base failed, with no reverse cases and exact McNemar `p = 0.00049`.

### Matched semantic changes

| Metric | Tuned minus base | Base failed, tuned passed | Base passed, tuned failed | Exact McNemar p-value | Source-clustered mean delta | Source-clustered 95% bootstrap interval |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Near-miss | -22.7 points | 5 | 15 | 0.041 | -20.8 points | -39.9 to -2.4 points |
| Key valid | -9.1 points | 5 | 9 | 0.424 | -6.0 points | -22.6 to 11.9 points |
| Label clean | -15.9 points | 7 | 14 | 0.189 | -14.9 points | -34.5 to 5.4 points |

The near-miss regression reached the paired-prompt threshold, while the source-cluster sign-flip test remained marginal at `p = 0.066` with only 14 source clusters.
The practical effect is still large enough to reject this checkpoint for promotion.

The largest genre regressions were court opinions, where near-miss fell from 87.5% to 25.0%, and laws or constitutions, where it fell from 60.0% to 35.0%.
The tuned failure set also contained more non-unique keys, invalid distractor traps, non-single-best answers, and period-implausible distractors.

### Qualified v3 versus v4 comparison

| Run | Expert-grade | Near-miss | Key valid | Main mechanical result |
| :--- | ---: | ---: | ---: | :--- |
| July 10 v3 | 30.0% | 32.0% | 48.0% | 50 of 56 prompts parsed; 21.4% strict arrays |
| July 12 audited v4 | 22.7% | 27.3% | 56.8% | 82.1% first-pass contract validity; no tuned retry exhaustion |

V3 was descriptively better on expert-grade and near-miss quality.
V4 was better on key validity and mechanical reliability.
The comparison is not controlled because v3 used a different source cohort, inference protocol, retry policy, and evaluator behavior, and ten v3 tuned judgments were unavailable and automatically treated as failures.
The evidence does not support a statistically validated claim that v3 was the better model overall.

### Decision and v5 response

The audited-v4 checkpoint is rejected for promotion because its contract gain came with a large semantic regression.
V5 removes legacy model-generated survivors and repeated target exposures, retains only independently audited expert-grade curated anchors, and reduces LoRA capacity and cumulative training pressure.
The v5 evaluator reports all-logical-prompt mechanical rates separately from shared-exclusion semantic rates and applies an explicit no-semantic-regression acceptance gate.

## Bottom line

- The July 10 v3 run remains the historical full-split semantic baseline.
- The July 7 litmus run is useful for understanding the original build decision, but its raw outputs are unavailable.
- The July 11 v4 run documents a severe base-generation protocol failure and must not be used to claim that v4 beat the base model.
- The July 12 corrected run validly shows that audited v4 improved contract reliability while regressing on semantic quality.
- The corrected run's raw ZIP should be preserved in a versioned result directory before the v5 run begins.

## Artifact locations and recovery

The complete v3 raw artifacts are recoverable from commit `a9449c5` under `APUSH Evaluation Results/`:

- `generation_attempts.json`: 168 raw generation attempts.
- `items.jsonl`: 162 parsed item records.
- `summary.json`: aggregate metrics and matched tests.

The invalid July 11 v4 artifacts are recoverable from commit `75422a6` under `APUSH Evaluation Results /`:

- `generation_attempts.json`: 392 raw generation attempts.
- `items.jsonl`: 192 parsed item records.
- `summary.json`: aggregate metrics and paired tests.

The July 11 directory name contains a trailing space before the slash.
The early litmus summary can be viewed from commit `7177f01` at `docs/02b_litmus_results.md`.
