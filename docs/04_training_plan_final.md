# Training Plan — Final (Deliverable 4)

> **Approved plan:** [`planning/plan_v2.md`](planning/plan_v2.md)  
> **Validator loop:** plan_v1 → [`validator_feedback_v1.md`](planning/validator_feedback_v1.md) → plan_v2 ✅

---

## Executive summary

Build a **Qwen3-4B-Instruct** specialist (QLoRA SFT + frontier distillation) that turns
study **notes** into **expert-grade MCAT MCQs** for exactly two structurally-determined
archetypes:

| Archetype | Why in v1 | Verifier rail |
| :--- | :--- | :--- |
| **MECHANISM_PERTURBATION** | Closed Km/Vmax/feedback menu; best seed coverage | Deterministic truth table + LLM solve |
| **THEORY_PLUS_STUDY** | Highest expert value; evidential-relation menu | Strict k=5 LLM solve only |

**Out of v1:** clinical vignettes, arithmetic, CARS, broad F1 recall, non-enzyme MECH
(circuits, gas laws) until truth tables exist.

---

## Confidence & preconditions

From [`03_feasibility_assessment.md`](03_feasibility_assessment.md):

- **92% confidence** tuned 4B beats prompted base on this scope, **conditional on:**
  - Litmus P1: frontier teacher ≥70%
  - Litmus P2: base 4B ≤45–55%
  - Verification pass in filter + inference
  - ≥600 kept items/arch at final scale

**Do not train until M1 litmus confirms P1/P2.**

---

## Phased execution

| Day | Milestone | Deliverable |
| :--- | :--- | :--- |
| D1 | M0 + M0.5 | Splits, brainlift draft, THEORY gold, truth table stub |
| D2 | M1 + M1.5 + M2 | Harness, litmus results, judge calibration, smoke loop |
| D3 | M3 | ~700 kept items, first QLoRA, **midweek base-vs-tuned** |
| D4 | M4 | ~1,500 kept, data iteration, retrain |
| D5 | M5 + M6 | Final eval, HF publish, demo video, brainlift final |

---

## Win criteria

- Tuned **≥75%** expert-grade on held-out human notes
- **≥+25 points** over prompted base 4B
- Run-to-run std **≤5 points**
- Production key-correctness **≥98%** with inference verifier
- Paraphrase fidelity/novelty **≥90%** (in-scope subset)

---

## Key documents

| Doc | Purpose |
| :--- | :--- |
| [`planning/plan_v2.md`](planning/plan_v2.md) | Full execution recipe |
| [`planning/brainlift_draft.md`](planning/brainlift_draft.md) | Behavior thesis |
| [`02_litmus_test_prompt.md`](02_litmus_test_prompt.md) | Pre-training BUILD gate |
| [`05_prev_data_audit.md`](05_prev_data_audit.md) | Data inventory |
| [`00_process_index.md`](00_process_index.md) | Master index |

---

## Brainstormer ↔ Validator loop (closed)

1. **Brainstormer** produced [`plan_v1.md`](planning/plan_v1.md) from feasibility verdict + spec.
2. **Validator** returned **REVISE (major)** — see [`validator_feedback_v1.md`](planning/validator_feedback_v1.md).
3. **Brainstormer** produced **plan_v2** addressing all critical + major issues.
4. **Validator criteria** in feedback doc marked satisfied → **APPROVED for execution**.

Next human/agent step: implement M0 artifacts and run litmus (M1).
