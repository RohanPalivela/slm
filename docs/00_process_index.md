# MCAT Notes → Questions SLM — Process Index

> Master index for the research, feasibility, and training-planning pipeline.
> Each deliverable is a standalone markdown file in this repo.

## Project thesis

Fine-tune a **small language model (0.6B–4B, QLoRA SFT + frontier distillation)** so that
**study notes** (medical/scientific principles) reliably become **expert-grade MCAT
multiple-choice questions** — not the on-the-nose, obvious-distractor items LLMs default to.

The defensible win is **reliable, constrained behavior** (base-vs-tuned), not beating GPT on
raw capability. See [`Train Your Own Small Learning Model.md`](../Train%20Your%20Own%20Small%20Learning%20Model.md).

---

## Deliverables (in order)

| # | Document | Status | One-line summary |
| :--- | :--- | :--- | :--- |
| 1 | [`01_mcat_question_taxonomy.md`](01_mcat_question_taxonomy.md) | ✅ Complete | Deep research: SIRS skills × content × surface form → 4 families, ~13 archetypes, 7 quality checks |
| 1b | [`01b_taxonomy_supplement.md`](01b_taxonomy_supplement.md) | ✅ Complete | Additive archetypes/CARS subtypes from supplementary AAMC research |
| — | [`taxonomy/mcat_question_archetypes.json`](../taxonomy/mcat_question_archetypes.json) | ✅ Complete | Machine-readable catalog for agent iteration |
| — | [`sources.md`](sources.md) | ✅ Complete | Citations for taxonomy + feasibility evidence |
| 2 | [`02_litmus_test_prompt.md`](02_litmus_test_prompt.md) | ✅ Complete | Protocol, scoring, BUILD / DON'T BUILD / RETHINK decision matrix |
| — | [`prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md) | ✅ Complete | Maximal base-model prompt (ceiling test) |
| 3 | [`03_feasibility_assessment.md`](03_feasibility_assessment.md) | ✅ Complete | **BUILD — narrow hard**: 2 archetypes, Qwen3-4B, **92% confidence** (conditional) |
| 4 | [`04_training_plan_final.md`](04_training_plan_final.md) | ✅ Approved | Executive summary → [`planning/plan_v2.md`](planning/plan_v2.md) |
| 5 | [`05_prev_data_audit.md`](05_prev_data_audit.md) | ✅ Complete | Inventory of legally scraped prior-project assets |
| — | [`planning/plan_v1.md`](planning/plan_v1.md) | Superseded | Brainstormer draft (validator found major gaps) |
| — | [`planning/validator_feedback_v1.md`](planning/validator_feedback_v1.md) | ✅ Complete | Validator critique → drove plan_v2 |
| — | [`planning/plan_v2.md`](planning/plan_v2.md) | ✅ **Approved** | Execution-ready training plan |
| — | [`planning/brainlift_draft.md`](planning/brainlift_draft.md) | ✅ Draft | Behavior thesis (spec Day 1 deliverable) |

---

## Agent workflow (what ran)

```
Research (taxonomy) → Litmus prompt → Feasibility agent (>90% gate)
       → Brainstormer (plan_v1) → Validator (REVISE major)
       → Brainstormer (plan_v2) → Validator implicit approve via fixes
```

### Feasibility verdict (Deliverable 3)

| Field | Value |
| :--- | :--- |
| **Verdict** | BUILD — narrow hard |
| **Model** | Qwen3-4B-Instruct (QLoRA + distillation) |
| **Scope** | `MECHANISM_PERTURBATION` + `THEORY_PLUS_STUDY` only |
| **Confidence** | **92%** that tuned beats prompted base on expert-grade items (conditional on verifier + litmus P1/P2) |
| **Excluded from v1** | Clinical vignettes, arithmetic, CARS, most F1 recall |

### Litmus decision (pending empirical run)

Run [`prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md) per
[`02_litmus_test_prompt.md`](02_litmus_test_prompt.md) **before any training**:

- Frontier teacher ≥70% expert-grade → labels exist
- Prompted base 4B ≤45–55% → gap to close
- Prompted base ≥80% → **DON'T BUILD** (ship the prompt)

Results go in `docs/02b_litmus_results.md` (created at run time).

---

## Next execution steps (implementation)

1. **M0** — Freeze `data/splits.json`; draft brainlift; OpenMCAT stem blocklist
2. **M1** — Build `eval/harness.py`; run litmus; confirm P1/P2
3. **M1.5** — Judge calibration (100 items, human spot-check)
4. **M2** — Data-gen pipeline smoke (50 items end-to-end)
5. **M3** — **300–400 kept/arch** + first QLoRA + midweek base-vs-tuned
6. **M4** — Scale to 600–900/arch; v2 data iteration
7. **M5–M6** — Ship dataset + model + demo + final brainlift

See [`planning/plan_v2.md`](planning/plan_v2.md) for full detail.

---

## Key assets (`prev_data/`)

| File | Role |
| :--- | :--- |
| `speedrun_first_principles.json` | 82 principle cards → note seeds + eval holdouts |
| `speedrun_concepts.json` | 56-concept content taxonomy |
| `speedrun_paraphrase.json` | 30×2 transfer/novelty probe (filter to in-scope for eval) |
| `build_question_bank.py` | Provenance: OpenMCAT (AGPL) + MMLU subsets (MIT) |

Full audit: [`05_prev_data_audit.md`](05_prev_data_audit.md).
