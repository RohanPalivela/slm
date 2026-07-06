# APUSH Notes/Source → Questions SLM — Process Index

> Master index for the research, feasibility, and training-planning pipeline.
> Each deliverable is a standalone markdown file in this repo.

## Project thesis

Fine-tune a **small language model (Qwen3-4B, QLoRA SFT + frontier distillation)**
so that a **provided historical source (+ optional study note)** reliably becomes an
**expert-grade AP U.S. History stimulus-based multiple-choice question** — not the
on-the-nose, obvious-distractor items LLMs default to.

The defensible win is **reliable, constrained behavior** (base-vs-tuned), not beating
a frontier model on raw capability. See
[`Train Your Own Small Learning Model.md`](../Train%20Your%20Own%20Small%20Learning%20Model.md).

---

## Deliverables (in order)

| # | Document | Status | One-line summary |
| :--- | :--- | :--- | :--- |
| 1 | [`01_apush_question_taxonomy.md`](01_apush_question_taxonomy.md) | ✅ Complete | Deep research: skills × reasoning × periods/themes × stimulus × stem → 5 families, 12 archetypes, closed stem menu, closed 4-trap distractor menu |
| 1b | [`01b_taxonomy_supplement.md`](01b_taxonomy_supplement.md) | ✅ Complete | FRQ (SAQ/DBQ/LEQ) mapping; text-only image handling; additive patterns |
| — | [`taxonomy/apush_question_archetypes.json`](../taxonomy/apush_question_archetypes.json) | ✅ Complete | Machine-readable catalog for agent iteration |
| — | [`sources.md`](sources.md) | ✅ Complete | CED + prep corpora + SLM feasibility evidence (citation keys) |
| 2 | [`02_litmus_test_prompt.md`](02_litmus_test_prompt.md) | ✅ Complete | Ceiling-test protocol, scoring (+`key_valid_rate`), BUILD / DON'T BUILD / RETHINK matrix |
| — | [`prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md) | ✅ Complete | Maximal base-model prompt (ceiling test) |
| 3 | [`03_feasibility_assessment.md`](03_feasibility_assessment.md) | ✅ Complete | **BUILD — narrow hard**: causation pair, Qwen3-4B, **~91% confidence** (conditional) |
| 4 | [`04_training_plan_final.md`](04_training_plan_final.md) | ✅ Approved | Executive summary → [`planning/plan_v2.md`](planning/plan_v2.md) |
| 5 | [`05_data_sourcing_and_legal.md`](05_data_sourcing_and_legal.md) | ✅ Complete | Legal sourcing (PD + CC-BY(-SA); no College Board); seed corpus + scraper |
| — | [`prompts/data_gen_prompt.md`](../prompts/data_gen_prompt.md) | ✅ Complete | Bulk data-gen prompt (candidate-set grounding + trap self-labeling) |
| — | [`planning/plan_v1.md`](planning/plan_v1.md) | Superseded | Brainstormer draft (validator found 4 critical + 7 major gaps) |
| — | [`planning/validator_feedback_v1.md`](planning/validator_feedback_v1.md) | ✅ Complete | Validator critique (REVISE major) → drove plan_v2 |
| — | [`planning/plan_v2.md`](planning/plan_v2.md) | ✅ **Approved** | Execution-ready training plan (all 12 fixes) |
| — | [`planning/validator_approval_v2.md`](planning/validator_approval_v2.md) | ✅ Complete | Validator approval pass on plan_v2 |
| — | [`planning/brainlift_draft.md`](planning/brainlift_draft.md) | ✅ Draft | Behavior thesis (spec Day-1 deliverable) |

---

## Agent workflow (what ran)

```
Research (taxonomy) → Litmus prompt → Feasibility agent (>90% gate)
   → Brainstormer (plan_v1) → Validator (REVISE major, 4 critical + 7 major)
   → Brainstormer (plan_v2, all 12 fixes) → Validator (APPROVE)
```

### Feasibility verdict (Deliverable 3)

| Field | Value |
| :--- | :--- |
| **Verdict** | BUILD — narrow hard |
| **Model** | Qwen3-4B-Instruct (QLoRA + distillation) |
| **Scope** | `CAUSE_OF_SOURCE` (anchor) + `EFFECT_OF_SOURCE` (share one deep skill) |
| **Confidence** | **~91%** that tuned beats prompted base on expert-grade items (conditional on grounding + verifier + confirmed teacher `key_valid_rate`) |
| **Crux** | SC-KEY — single-best HISTORICAL correctness (worse than a science domain) |
| **Excluded from v1** | `COMPETING_INTERPRETATIONS`, `EVIDENCE_UNDERMINES_CLAIM` (no usable verifier); `DEVELOPMENT_ILLUSTRATED` (DON'T-BUILD) |

### Litmus decision (pending empirical run)

Run [`prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md) per
[`02_litmus_test_prompt.md`](02_litmus_test_prompt.md) **before any training**, on the
causation-pair subset:

- Frontier teacher ≥70–75% expert-grade **and** `key_valid_rate` ≥70–75% → labels exist
- Prompted base 4B ≤45–55% → gap to close
- Prompted base ≥80% → **DON'T BUILD** (ship the prompt)

Results go in `docs/02b_litmus_results.md` (created at run time).

---

## Next execution steps (implementation)

1. **M0** — Base Qwen3-4B inference works; draft brainlift; freeze `data/splits.json` (primary-only); kick off A3 (corpus→~150 primary) + A6 (developments→~150–200).
2. **M1** — Build `eval/harness.py`; smoke test.
3. **M2** — **Litmus build-gate** on the causation subset → confirm P1/P2 + teacher `key_valid_rate`.
4. **M2.5 (BLOCKING)** — A3 + A4 (gold set) + A6 done; **G-cal** (judge/verifier ≥90% vs gold) + **G-yield** (measured filter yields) before any bulk spend.
5. **M3** — Bulk gen (grounded) → first QLoRA → **midweek base-vs-tuned** (source-cluster CI).
6. **M4** — Data iteration (fix failures in data, not hyperparameters).
7. **M5–M6** — Ship dataset + model + demo + final brainlift.

See [`planning/plan_v2.md`](planning/plan_v2.md) for full detail.

---

## Key assets (`data/`)

| File | Role |
| :--- | :--- |
| `seed_stimuli.jsonl` | 22 legally-sourced stimuli (14 primary + 8 secondary); note-seeds + eval sources |
| `apush_key_developments.json` | 167 date-tagged developments → anachronism verifier + grounding set + distractor pool |
| `apush_periods_themes.json` | 9 periods × 8 themes content vocabulary |
| `build_seed_corpus.py` | Legal-sourcing pipeline (OpenStax/Yawp/Wikisource) + provenance manifest |

Full audit: [`05_data_sourcing_and_legal.md`](05_data_sourcing_and_legal.md).
