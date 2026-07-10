# v3 APUSH Evaluation Postmortem

Date: July 10, 2026.

## Executive summary

The v3 adapter is a useful first iteration, but this run does not establish a meaningful improvement in end-to-end APUSH question quality over the base model.
The adapter learned structural compliance well, reducing programmatic craft failures from 45% to 10% and schema failures from 29% to 6%.
Historical correctness and unique answer selection did not improve reliably.
The teacher reached 75% near-miss quality with 100% valid keys, which confirms that the task is feasible and supports continued distillation work.

The run also exposed evaluation-system problems that weaken the semantic comparison.
Six tuned generations were rejected because of malformed top-level JSON, and ten tuned items received unparseable judge responses that were automatically converted into failures.
The next iteration should repair the evaluator and rejudge affected items before making large training changes.

## Run configuration

| Setting | Value |
| :--- | :--- |
| Split | `EVAL_HELDOUT` |
| Sources | 28 |
| Archetypes | `CAUSE_OF_SOURCE`, `EFFECT_OF_SOURCE` |
| Attempted prompts | 56 per model |
| Runs | 1 |
| Temperature | 0.0 |
| Maximum new tokens | 768 |
| Base model | `unsloth/Qwen3-4B` |
| Base revision | `64033659d5caf1b8ed7f929b29de705e93a4d468` |
| Adapter | `rohanpalviela/qwen3-4b-apush-v3-clean-lora` |
| Teacher | `claude-group/claude-opus-4-8` |
| Judge | `openai-group/gpt-5.5` |

The raw artifacts are stored under `APUSH Evaluation Results/`.

## Factual correction from strict format reanalysis

The original notebook used tolerant item extraction, so its 50 parsed tuned items did not imply 50 contract-valid responses.
A later strict reanalysis of the preserved raw generations found 12 strict top-level arrays, 7 strict single objects, 31 unclosed arrays that contained at least one complete item before repeated or truncated output, and 6 single objects with an unmatched trailing array bracket.
The 56 base and 56 teacher generations were all strict top-level arrays.
The original parsed-item quality tables remain reproducible diagnostics, but strict array reliability for the tuned model was 12 of 56 attempts, or 21.4%.
This correction strengthens the decision to align the training and inference prefix and stop generation after the first complete top-level array.

## Results

The official quality percentages use parsed items as their denominator.

| Model | Calls | Parsed items | Expert-grade | Near-miss | Key valid | Distillable | Craft fail | Schema fail |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3-4B base | 56 | 56 | 25% | 30% | 59% | 32% | 45% | 29% |
| Qwen3 APUSH v3 | 56 | 50 | 30% | 32% | 48% | 42% | 10% | 6% |
| Teacher | 56 | 56 | 73% | 75% | 100% | 77% | 23% | 0% |

The tuned model had 16 near-miss passes among 50 parsed items.
When all 56 attempted prompts are treated as the end-to-end denominator, its near-miss success rate is 28.6%.
The base model had 17 near-miss passes among 56 attempts, or 30.4%.

## Paired comparison

The official paired tests used the 50 prompts for which both base and tuned output was parsed.

| Metric | Base failed, tuned passed | Base passed, tuned failed | Exact McNemar p-value |
| :--- | ---: | ---: | ---: |
| Near-miss | 11 | 11 | 1.00 |
| Key valid | 9 | 16 | 0.23 |
| Distillable | 14 | 10 | 0.54 |

None of these results is statistically significant at the conventional 0.05 threshold.
The near-miss comparison is exactly balanced between improvements and regressions.
The positive distillable-item movement is promising but too uncertain to claim as a real gain.

## What went well

### Structural learning

The strongest verified improvement is structural compliance.
The tuned model generated complete rationales and valid trap metadata much more reliably than the base model.
Its craft failure rate fell by 35 percentage points, and its schema failure rate fell by 23 percentage points.

### Training-data usability

The tuned model increased parsed-item distillability from 32% to 42%.
This suggests that the adapter learned important parts of the target representation even though the paired result remains inconclusive.

### Task feasibility

The teacher produced 42 near-miss items, 41 strict expert-grade items, 56 valid keys, and 43 distillable items.
These results clear the project's teacher-quality gate and show that the held-out prompts are answerable at a high level.

### Data isolation and traceability

The run used the held-out split and recorded the base revision, adapter ID, teacher, judge, generation attempts, item judgments, and summary metrics.
Those artifacts make prompt-level regression analysis possible.

## What went wrong

### Semantic quality did not improve reliably

The tuned near-miss rate increased by only 1.6 percentage points on parsed items.
The tuned model produced one fewer near-miss item than the base model over the same 56 attempted prompts.
Valid keys fell from 59% to 48% in the official summary.

The recurring semantic problems were incorrect keys, non-unique keys, weak cause-and-effect links, skill mismatch, and implausible distractors.
Effect questions remained particularly difficult, with 25% tuned near-miss quality compared with 38% for cause questions.

### Tuned JSON reliability regressed

Six tuned calls produced no parsed item.
Every affected generation began as a JSON object but ended with an unmatched array-closing bracket.
The training completions consistently use a JSON array, while some tuned generations omitted the opening array bracket and retained the closing bracket.

This is an end-to-end product failure even when the underlying question content appears recoverable.
The evaluator should report it separately from semantic quality and may offer a secondary repaired-output diagnostic without hiding the primary format failure.

### Judge failures contaminated model scores

The judge returned an unparseable response for ten of the 50 parsed tuned items, one of the 56 base items, and none of the teacher items.
The scoring path normalized every missing judge field to false, which caused these cases to fail near-miss, expert-grade, and key-valid checks.

The raw judge responses were not saved, so this result cannot distinguish malformed judge output from a parser defect or another response-path problem.
After excluding unparseable judge cases, the remaining paired results still do not reach statistical significance, but the tuned semantic rates look materially better.
The appropriate conclusion is that semantic performance remains unresolved rather than proven worse.

### Denominators obscure generation failures

The official aggregate quality metrics divide by parsed items.
That makes the tuned model's 32% near-miss rate look slightly better than its 28.6% end-to-end success rate over attempted prompts.
Both views are useful, but the attempted-prompt rate should be the primary product metric.

### The run cannot measure stability

The evaluation used one deterministic run.
It provides a matched snapshot but no estimate of run-to-run consistency.
Several source-genre slices also contain too few items for reliable conclusions.

## Root-cause assessment

Confirmed observations:

- The adapter substantially improved schema and craft compliance.
- The adapter sometimes mixed object and array boundaries in its output.
- The official base-versus-tuned quality differences were not statistically significant.
- The scoring path treated judge parse failures as model failures.
- The teacher demonstrated a large and usable quality gap over both small-model variants.

Working hypotheses:

- The clean SFT data teaches representation and rationale structure more effectively than historical discrimination.
- Training examples do not provide enough hard contrast between a plausible answer and a uniquely best answer.
- Direct causality and downstream-effect examples need stronger independent review.
- The output contract needs more consistent alignment between training targets, inference prompts, and parsing expectations.

These hypotheses require controlled data inspection and reruns before they are promoted to conclusions.

## Decision

Continue the distillation program.
Do not treat the v3 adapter as a production candidate based on this run.
Use the v3 results as the baseline for the next controlled iteration.

The teacher clears the target regime while both prompted small-model variants remain below 55% near-miss quality.
That pattern supports additional fine-tuning, provided the next cycle improves semantic supervision and repairs the evaluation path.

## Action items for the next iteration

### Evaluation reliability

1. Save raw judge responses beside every item.
2. Retry judge calls or parsing before scoring a judgment as unavailable.
3. Represent unresolved judge results as inconclusive and exclude them from semantic denominators while reporting their rate.
4. Report attempted-prompt, parsed-item, and successfully judged denominators together.
5. Add explicit format buckets for top-level arrays, single objects, trailing brackets, truncation, and empty output.
6. Add a secondary tolerant-parse diagnostic while preserving strict parse success as the product metric.
7. Run multiple repetitions for the next production decision.

### Training data

1. Independently rejudge a stratified sample of the current clean training set.
2. Add or upweight examples that distinguish plausible answers from uniquely best answers.
3. Add reviewed hard examples for direct causes, immediate effects, and long-term effects.
4. Increase coverage of court opinions and other weak source genres.
5. Quarantine examples with debatable causality or overlapping answer choices.

### Training and inference

1. Verify that the training completion shape and inference output contract are identical.
2. Test strict array-only decoding against a single-object contract and choose one canonical representation.
3. Record prompt, tokenizer, chat-template, no-think, and generation settings with every adapter evaluation.
4. Change one major variable at a time when practical so improvements remain attributable.

## Repeatable process

The durable evaluation and training cycle is recorded in `AGENTS.md`.
Every future full run should create a new dated postmortem and update the current baseline without deleting this history.
