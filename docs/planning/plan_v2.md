# Training Plan v2 — Notes → Expert-Grade MCAT MCQs (APPROVED)

> **Status:** Approved after validator loop ([`validator_feedback_v1.md`](validator_feedback_v1.md)).  
> Supersedes [`plan_v1.md`](plan_v1.md).  
> Inherits binding verdict from [`03_feasibility_assessment.md`](../03_feasibility_assessment.md).

```
┌─ PLAN AT A GLANCE ──────────────────────────────────────────────────────────┐
│ GOAL     Qwen3-4B-Instruct (QLoRA) → one expert-grade MCQ per note, 2 types   │
│ SCOPE    MECHANISM_PERTURBATION (enzyme/bioenergetics) + THEORY_PLUS_STUDY    │
│ DATA     Phased: D3 ~350 kept/arch → D4 ~750/arch (~2,100 total)              │
│ GATES    Litmus P1/P2 → Judge cal → Bulk gen → Train → Base-vs-tuned          │
│ WIN      Tuned ≥75% expert-grade, ≥+25 pts vs base, verifier key ≥98% prod   │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 0. Changes from plan_v1 (validator fixes)

| Issue | v2 resolution |
| :--- | :--- |
| MECH verifier ≠ 12-concept scope | **Narrow MECH v1** to 6 enzyme/bioenergetics concepts with Km/Vmax/feedback menus + truth table |
| THEORY SC5 unrealistic | Per-archetype targets; THEORY bulk gen kill if verifier pass <70% on first 500 raw |
| D3 volume impossible | **Midweek = 350 kept/arch**; full 750/arch by D4 |
| Litmus ≠ product eval | **Two instruments** (§4) |
| THEORY menu size contradiction | **5 items** everywhere (see §1) |
| Missing artifacts | **M0.5 blocking checklist** (Appendix A) |
| Brainlift deferred | **M0 draft** ([`brainlift_draft.md`](brainlift_draft.md)) |
| Contamination | OpenMCAT blocklist; dedup **0.85**; litmus notes disjoint from train |
| Litmus prompt “verbatim reuse” | Fork **`prompts/data_gen_prompt.md`** (delta documented) |

---

## 1. Behavior spec

Same falsifiable spec as plan_v1 (see [`brainlift_draft.md`](brainlift_draft.md)). Two closed menus:

### MECHANISM_PERTURBATION (enzyme/bioenergetics v1)

**Correct answer:** label from fingerprint → `{competitive, uncompetitive, noncompetitive/mixed, allosteric activation, dissociation/denaturation}` or feedback analog `{increased, decreased, unchanged, compensatory}`.

**v1 concepts (6):** enzyme-regulation, glycolysis, oxidative-phosphorylation, bioenergetics, acid-base-equilibria, kinetics-equilibrium-mech.

**Deterministic verifier:** `eval/truth_tables/mech_pert_enzyme.json` maps qualitative Km/Vmax/feedback fingerprints → label.

### THEORY_PLUS_STUDY

**Correct answer:** one of **5** evidential relations:

1. `supports`
2. `weakens (in-scope claim)`
3. `consistent-but-not-diagnostic`
4. `contradicts a different claim`
5. `requires bounded revision`

**v1 concepts (10):** evolution-ecology, associative-learning, social-psychology, theoretical-approaches, social-class, culture-socialization, developmental-psychology, personality, emotion-motivation, cognition-language, kinetics-equilibrium-theory.

**Verifier:** k=5 independent solve (≥4/5 margin) + double-correct probe; no symbolic rail (stricter than MECH).

---

## 2. Data generation

### 2.1 Models

| Role | Model | Notes |
| :--- | :--- | :--- |
| Teacher | Frontier (Claude/GPT class) | Generator |
| Judge | **Different family** from teacher | 7 checks + graded dims |
| Key verifier | **Third family** + rule-checker (MECH) | SC5 crux |

### 2.2 Seeds & firewall

**Frozen in `data/splits.json` before any generation:**

| Pool | Source | Count | Role |
| :--- | :--- | :--- | :--- |
| LITMUS | 15 FP `back` texts (disjoint uids) | 15 | P1/P2 only (`docs/02`) |
| EVAL-heldout | FP cards | 20 | Never train seeds |
| EVAL-paraphrase | In-scope paraphrase cards only | ~14 | Novelty probe |
| EVAL-adversarial | Teacher terse/multi-concept | 10 | Robustness (report-only v1) |
| TRAIN-human | Remaining FP cards | ~47 | Training seeds |
| TRAIN-synthetic | Teacher notes on in-scope concepts | ~200 | Diversity |

**Firewall rules:**

1. Blocklist uids: all LITMUS + EVAL-heldout + EVAL-paraphrase card_ids
2. Embedding dedup: cosine **< 0.85** vs any eval/litmus artifact (pre-registered)
3. OpenMCAT: blocklist all 169 stems when bank available
4. Near-dup within train: cosine < 0.92

### 2.3 Prompts

- **Litmus:** [`prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md) — unchanged
- **Data gen:** `prompts/data_gen_prompt.md` — fork of litmus SYSTEM with:
  - 2 archetypes only
  - 1 item per call
  - `answer_derivation` + menu self-labeling fields
  - Single JSON object (not array)

**Bootstraps required before bulk gen:** 10 hand-verified THEORY gold items in `data/gold/theory_plus_study_fewshots.json`.

### 2.4 Training example schema

Same as plan_v1 §2.4; `reasoning_hops` required ≥2 for both archetypes.

### 2.5 Phased volumes

| Phase | When | Raw/arch | Kept/arch | Kept total |
| :--- | :--- | :---: | :---: | :---: |
| **Smoke** | M2 | 50 | ~18 | ~36 |
| **Midweek (M3)** | D3 | ~1,000 | **~350** | **~700** |
| **Final (M4)** | D4 | +~1,500 | **~750** | **~1,500** |

Expected funnel: 80% programmatic → 58% judge → 78% verifier → **~36% end-to-end**.

Split kept: **650 train / 100 dev per archetype** at final scale (asymmetric OK: 750 MECH / 650 THEORY if THEORY yield lower).

---

## 3. Quality gate (three stages)

### 3.1 Programmatic (additions vs v1)

- `reasoning_hops >= 2` — **disqualifying**
- THEORY: exactly **5 distinct menu labels** represented across options (4 shown + 1 implicit)
- MECH: options ⊆ closed menu; fingerprint fields parseable
- Absolute-word tells (`always|never`) on distractors — **disqualifying**
- Concept-leak: ≤6-gram overlap with source note

### 3.2 LLM judge

Same rubric as plan_v1. **`expert_grade`** = all disqualifying pass + graded dims ≥1 + spec adherence = 2.

**M1.5 gate (blocking):** 100 items (50/arch) human-graded; judge–human agreement ≥0.8; 20% double-judge on ongoing batch.

### 3.3 Answer-key verification

| Archetype | Signals required |
| :--- | :--- |
| MECH | Rule-checker **AND** k=5 solve (≥4/5) **AND** double-correct probe |
| THEORY | k=5 solve (**≥5/5**) **AND** double-correct probe |

**Per-archetype SC5 targets (raw model, pre-inference verifier):**

| Archetype | Midweek (M3) | Final (M5) |
| :--- | :---: | :---: |
| MECH_PERT | ≥88% | ≥92% |
| THEORY_PLUS_STUDY | ≥75% | ≥82% |

**Production (with §6 inference verifier):** ≥98% both.

**THEORY kill-criterion:** If verifier pass <70% on first 500 raw THEORY items → pause THEORY bulk gen; fix gold few-shots / menu prompt; consider MECH-only ship.

---

## 4. Two eval instruments (do not conflate)

### 4A. Litmus run (M1 — BUILD gate)

Per [`02_litmus_test_prompt.md`](../02_litmus_test_prompt.md):

- 15 fixed notes × 6 items × 3 runs = 270 items/model
- Models: Qwen3-4B + frontier teacher
- **P1:** frontier ≥70% expert-grade on 2 archetypes
- **P2:** base 4B ≤45–55%
- **DON'T BUILD:** base ≥80%
- Output: `docs/02b_litmus_results.md`

### 4B. Product eval (M3+ — training success)

- 20 EVAL-heldout + 10 adversarial notes
- ~14 in-scope paraphrase cards (fidelity + novelty)
- 3 runs temp 0.7; report mean ± std + all-pass rate
- Bootstrap 95% CI on pass rate (≥30 scored outputs primary)

**Arms:** Base + maximal litmus prompt | Tuned + short production prompt | (optional) Tuned + maximal prompt

**Success targets (tuned vs base):**

| Metric | Base (expected) | Tuned target |
| :--- | :---: | :---: |
| Expert-grade pass rate | 35–50% | **≥75%** and **≥+25 pts** |
| Run-to-run std | 10–15 pts | **≤5 pts** |
| Paraphrase fidelity / novelty (in-scope) | — | **≥90% / ≥90%** |
| Per-archetype pass | — | **both ≥70%** |

---

## 5. Training config

Unchanged from plan_v1 §5: Unsloth QLoRA on `unsloth/Qwen3-4B-Instruct`, r=16, 3 epochs, `enable_thinking=False`, loss on assistant JSON only.

---

## 6. Inference verifier

Same reject-and-regenerate loop as plan_v1 §6; shared code with `eval/harness.py`.

---

## 7. Iteration strategy

Fix failures in **data**, not hyperparameters (spec rule). See plan_v1 §7 failure-mode table.

---

## 8. Stretch ladder

1. DPO from filter negatives (~1,500 pairs)
2. MMLU flat-recall items as explicit `rejected` anti-patterns
3. Adversarial eval promoted to graded rung
4. Composed behavior: numeric fingerprint as given data, never computed

---

## 9. Milestones (spec-aligned)

| M | When | Exit criterion |
| :--- | :--- | :--- |
| **M0** | D1 | Base Qwen3-4B inference works; [`brainlift_draft.md`](brainlift_draft.md); `data/splits.json` frozen |
| **M0.5** | D1 | Appendix A artifacts stubbed; THEORY 10 gold items; OpenMCAT blocklist |
| **M1** | D1–D2 | `eval/harness.py`; **litmus run** → P1/P2 documented |
| **M1.5** | D2 | Judge calibration ≥0.8 agreement |
| **M2** | D2 | 50-item smoke through generate→filter→train→eval |
| **M3** | D3 | **~700 kept** + first QLoRA + **midweek base-vs-tuned** |
| **M4** | D4 | Scale to ~1,500 kept; one data-fix iteration |
| **M5** | D5 | Final eval meets §4B targets; inference demo |
| **M6** | D5 | HF dataset + model; final brainlift; demo video |

---

## Appendix A — Blocking artifacts

| Artifact | Owner step | Blocks |
| :--- | :--- | :--- |
| `data/splits.json` | M0 | All generation |
| `data/gold/theory_plus_study_fewshots.json` | M0.5 | THEORY bulk gen |
| `eval/harness.py` | M1 | Litmus + training eval |
| `eval/truth_tables/mech_pert_enzyme.json` | M0.5 | MECH verifier |
| `prompts/data_gen_prompt.md` | M1 | Bulk gen |
| `docs/02b_litmus_results.md` | M1 | Training (P1/P2) |
| `data/mcat_slm_v1.{train,dev}.jsonl` | M3 | — |
| `results/base_vs_tuned.md` | M3+ | Final package |

## Appendix B — API budget (estimate)

| Stage | Calls | Notes |
| :--- | :---: | :--- |
| Litmus | ~600 | 270×2 models + judge |
| Judge calibration | ~200 | 100 items ×2 |
| Smoke | ~200 | 50 raw + filters |
| Midweek bulk | ~8,000 | 2k raw/arch × filter stack |
| Final bulk | ~12,000 | Additional 1.5k raw/arch |
| **Total** | **~21,000** | Parallelize; checkpoint JSONL |

## Appendix C — Spec compliance

| Non-negotiable | Section |
| :--- | :--- |
| Dataset is deliverable | §2, M6 |
| Eval before training | §4A M1 blocks M3 |
| Base-vs-tuned | §4B |
| QLoRA/Unsloth | §5 |
| No broad domains | §1 (2 archetypes, 16 concepts) |
| Data not hyperparams | §7 |
| Verifier precondition | §3.3, §6 |
