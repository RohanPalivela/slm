# Training Plan — Final (Deliverable 4, executive summary)

> **Status:** Approved after the brainstormer↔validator loop. Full detail lives in
> [`planning/plan_v2.md`](planning/plan_v2.md) (execution-ready). This page is the
> one-screen summary. Binding inputs:
> [`03_feasibility_assessment.md`](03_feasibility_assessment.md) (verdict) and
> [`Train Your Own Small Learning Model.md`](../Train%20Your%20Own%20Small%20Learning%20Model.md) (spec).

---

## Verdict inherited

**BUILD — narrow hard.** Fine-tune **Qwen3-4B-Instruct** (QLoRA + frontier
distillation) on **two archetypes only** — `CAUSE_OF_SOURCE` (anchor) +
`EFFECT_OF_SOURCE` — which share one deep skill: *map a provided, dated source to
the single outside development that (a) is date-consistent with the stem direction
and (b) is the specific, not background, match; make the three distractors the four
named College Board traps.* **~91% confidence** on the base-vs-tuned bar,
conditional on grounding + verifier + a confirmed teacher `key_valid_rate`.

## The behavior spec (the one falsifiable boolean)

> Given a **provided text primary source** (`source_text + attribution +
> source_date`) and an optional steering note, emit **one valid JSON MCQ** where:
> (a) the key **requires an outside development not stated in the source**, selected
> **by `development_id`** from the date-tagged developments table; (b) the key is
> **date-consistent** with the stem direction and **uniquely most-direct**; (c) the
> three distractors are each one of `{wrong_era, true_but_irrelevant, scope_mismatch,
> partially_true}`, era-plausible, spanning ≥2 types; (d) homogeneous options, no
> all/none, stem answerable before options. **PASS iff all four hold.**

## Pipeline at a glance

| Stage | What | Gate |
| :--- | :--- | :--- |
| **Litmus (M2)** | Prompted base 4B vs frontier teacher on the causation subset | BUILD iff teacher ≥70–75% expert-grade **and** `key_valid_rate` ≥70–75%, base ≤45–55%; DON'T-BUILD if base ≥80% |
| **Calibrate (M2.5, BLOCKING)** | Corpus (A3→~150 primary) + developments table (A6→~150–200) + gold set; judge/verifier ≥90% vs gold (G-cal); measured filter yields (G-yield) | Blocks all bulk generation |
| **Generate (M3)** | Teacher distillation with **candidate-set grounding**; 3-stage filter (programmatic date-check → judge → key-verifier) | ~600 kept/archetype (P3 floor); ≤6 items/(stimulus,archetype) |
| **Train (M3)** | Unsloth QLoRA on `Qwen3-4B-Instruct`; loss on JSON only | first midweek base-vs-tuned |
| **Iterate (M4)** | Fix failures in **data**, not hyperparameters | one failure mode resolved |
| **Ship (M5–M6)** | HF dataset + model + inference demo (with the verifier) + final brainlift + demo video | meets §5B targets |

## Success criteria (base-vs-tuned, held-out sources)

- Tuned **≥80% expert-grade**, and **≥ +25 pts** over the prompted base with a
  **source-level cluster bootstrap** 95% CI lower-bound **> 0**;
- **lower run-to-run variance** than the base;
- both archetypes **≥78%**; **production key-validity ≥90%** (verifier-on).

## Kill-criteria

- Prompted base 4B **≥80%** on the scope → **DON'T BUILD** (ship a prompt).
- Frontier teacher **`key_valid_rate` <70%** → **RETHINK** (no clean labels).
- Tuned **production (verifier-on) SC-KEY <85%** after v2 iteration → **RETHINK scope**
  (drop to one archetype, tighten grounding to a candidate set, or switch the output
  unit to "repair/grade an item").

## Loop provenance

[`plan_v1.md`](planning/plan_v1.md) → [`validator_feedback_v1.md`](planning/validator_feedback_v1.md)
(REVISE major; 4 critical + 7 major) → [`plan_v2.md`](planning/plan_v2.md) (all 12
fixes) → [`validator_approval_v2.md`](planning/validator_approval_v2.md) (APPROVE).
