# MCAT Notes → Questions SLM

Fine-tune a small language model (Qwen3-4B, QLoRA) to turn medical/scientific **study notes** into **expert-grade MCAT multiple-choice questions** — the kind that feel human-written, not the on-the-nose items LLMs usually produce.

## Status

| Phase | Status |
| :--- | :--- |
| MCAT question taxonomy | ✅ [`docs/01_mcat_question_taxonomy.md`](docs/01_mcat_question_taxonomy.md) |
| Litmus test prompt | ✅ [`prompts/litmus_generation_prompt.md`](prompts/litmus_generation_prompt.md) |
| Feasibility (92% confidence, narrow scope) | ✅ [`docs/03_feasibility_assessment.md`](docs/03_feasibility_assessment.md) |
| Training plan (validator-approved) | ✅ [`docs/planning/plan_v2.md`](docs/planning/plan_v2.md) |
| Litmus empirical run | ⏳ Pending (blocks training) |
| Dataset + model | ⏳ Not started |

**Start here:** [`docs/00_process_index.md`](docs/00_process_index.md)

## Verdict (feasibility)

**BUILD — but narrow hard.** Scope = two archetypes only:

- `MECHANISM_PERTURBATION` (enzyme/bioenergetics; closed Km/Vmax menu)
- `THEORY_PLUS_STUDY` (theory + follow-up finding; closed evidential-relation menu)

Base model: **Qwen3-4B-Instruct**. Excluded from v1: clinical vignettes, arithmetic, CARS.

## Spec

Follows [`Train Your Own Small Learning Model.md`](Train%20Your%20Own%20Small%20Learning%20Model.md) — dataset is the deliverable; eval before training; base-vs-tuned is mandatory.

## Prior data

Legally scraped assets in [`prev_data/`](prev_data/) — see [`docs/05_prev_data_audit.md`](docs/05_prev_data_audit.md).

## Repository layout

```
docs/           Research, feasibility, training plan
taxonomy/       Machine-readable MCAT archetype catalog (agent-iterable)
prompts/        Litmus + (future) data-gen prompts
prev_data/      First-principles cards, concepts, paraphrase eval set
```
