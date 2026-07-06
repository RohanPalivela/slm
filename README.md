# APUSH Notes/Source → Expert Questions (SLM)

Fine-tune a small language model (**Qwen3-4B**, QLoRA) to turn a provided
**historical source (+ optional study note)** into **expert-grade AP U.S. History
stimulus-based multiple-choice questions** — the kind that feel human-written, not
the on-the-nose items LLMs usually produce (obvious wrong answers, testing the
source back to itself).

**Start here:** [`docs/00_process_index.md`](docs/00_process_index.md)

## The idea in one line

Expert APUSH questions hang on a **source**, require connecting it to an **outside
development**, and give **four true-but-wrong distractors**, each a *named trap*
(wrong-era, true-but-irrelevant, scope-mismatch, partially-true). That last part is
what LLMs get wrong — and what a narrow, grounded fine-tune can get right reliably.

## Verdict (feasibility)

**BUILD — but narrow hard.** Scope = the two **date-anchored causation archetypes**
(they share one deep skill):

- `CAUSE_OF_SOURCE` — "which development contributed *most directly* to the source?"
- `EFFECT_OF_SOURCE` — "the source most immediately *led to*…?"

Base model: **Qwen3-4B-Instruct**. **~91% confidence** on the required base-vs-tuned
bar, **conditional** on: the answer being **grounded** to a curated date-tagged
developments table (selection, not free-recall), an inference-time **verifier**, and
a confirmed frontier-teacher key-validity in the litmus run. Crux = **single-best
historical correctness (SC-KEY)**. Explicitly excluded from v1: argument-evidence /
competing-interpretation items (highest expert-feel but no usable verifier), and the
comprehension-only `DEVELOPMENT_ILLUSTRATED` (a prompted base likely already passes).

Full reasoning: [`docs/03_feasibility_assessment.md`](docs/03_feasibility_assessment.md).

## Status

| Phase | Status |
| :--- | :--- |
| APUSH question taxonomy | ✅ [`docs/01_apush_question_taxonomy.md`](docs/01_apush_question_taxonomy.md) + [`taxonomy/apush_question_archetypes.json`](taxonomy/apush_question_archetypes.json) |
| Litmus test protocol + prompt | ✅ [`docs/02_litmus_test_prompt.md`](docs/02_litmus_test_prompt.md) |
| Feasibility (BUILD-narrow, 91%) | ✅ [`docs/03_feasibility_assessment.md`](docs/03_feasibility_assessment.md) |
| Data sourcing & legal + seed corpus | ✅ [`docs/05_data_sourcing_and_legal.md`](docs/05_data_sourcing_and_legal.md) + [`data/`](data/) |
| Training plan (validator-approved) | ✅ [`docs/planning/plan_v2.md`](docs/planning/plan_v2.md) |
| Litmus empirical run | ⏳ Pending (blocks training) |
| Dataset + model | ⏳ Not started |

## How this was built (the pipeline)

```
Research (taxonomy) → Litmus prompt → Feasibility agent (>90% gate)
   → Brainstormer (plan_v1) → Validator (REVISE major, 12 fixes)
   → Brainstormer (plan_v2) → Validator (APPROVE)
```

Everything is documented as markdown. See
[`docs/00_process_index.md`](docs/00_process_index.md) for the full map.

## Spec

Follows [`Train Your Own Small Learning Model.md`](Train%20Your%20Own%20Small%20Learning%20Model.md):
the **dataset is the deliverable**; the **eval is built before training**; a
**base-vs-tuned** comparison is mandatory; QLoRA/Unsloth on a small open base; no
broad domains.

## Data (legally sourced)

No pre-existing question dataset. Training data is **distilled from a frontier
teacher**, grounded on **public-domain primary sources** (published ≤1930, plus
U.S. federal works and court opinions) and **CC-BY(-SA) open textbooks**. **No
College Board questions enter the pipeline** (their terms forbid AI training).
Legal analysis + provenance: [`docs/05_data_sourcing_and_legal.md`](docs/05_data_sourcing_and_legal.md).

## Repository layout

```
docs/            Research, feasibility, data-sourcing, and the process index
docs/planning/   Brainstormer plans + validator feedback + brainlift
taxonomy/        Machine-readable APUSH archetype catalog (agent-iterable)
prompts/         Litmus + bulk data-generation prompts
data/            Seed stimuli, periods/themes grid, date-tagged developments,
                 legal scraper (build_seed_corpus.py) + provenance manifest
```
