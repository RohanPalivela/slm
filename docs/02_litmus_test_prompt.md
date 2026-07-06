# Litmus Test — Protocol, Scoring & Decision (Deliverable 2)

> **The one question this answers:** *Should this SLM be built at all?*
>
> Per the project spec, fine-tuning is justified **only if a well-prompted base
> model can't already do the behavior reliably.** So we take the strongest
> reasonable prompt ([`prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md))
> and measure how reliably models produce **expert-grade** MCAT questions from
> notes. The result routes us to one of three doors: **BUILD**, **DON'T BUILD**,
> or **RETHINK**.

---

## 1. What "reliably" and "expert-grade" mean here

- **Expert-grade** = an item passes **all disqualifying quality checks** from the
  taxonomy (§7 of `01_...`): familiar-concept/unfamiliar-scenario,
  cover-the-options, every-distractor-named-error, single-best-answer,
  no-all/none, homogeneous options. These are booleans; an item either clears
  the bar or it doesn't.
- **Reliably** = expert-grade **≥ 80% of the time**, across varied notes and
  archetypes, *and* stable across repeated runs (low variance). Reliability, not
  peak quality, is the whole point — a prompt can get lucky once; a trained model
  must do it every time.

This mirrors the spec's eval rubric (Spec adherence, Robustness, Task quality,
Consistency), specialized to question-writing.

---

## 2. The instrument

`prompts/litmus_generation_prompt.md` — a maximal prompt encoding the full
behavior spec, all archetype definitions, and two gold few-shot exemplars, with
strict JSON output so grading is automatic. It is intentionally the *best* prompt
we can write, because the litmus is a **ceiling test**: we are asking "even when
told exactly how, can the model do it?"

---

## 3. Fixed test inputs (held constant across all models)

Draw **15 note inputs** so results are comparable and representative. Sources are
already in-repo:

- **10 principle notes** — the `back` field of 10 `speedrun_first_principles.json`
  cards, one per topic family (physics, gen-chem, o-chem, biochem, biology ×2,
  psychology ×2, sociology, + one cross-topic). These are exactly the
  "notes → concept" front-half the SLM must expand from.
- **3 raw/messy notes** — lecture-style bullet fragments (adversarial: terse,
  abbreviation-heavy) to probe robustness.
- **2 multi-concept notes** — a paragraph mixing 2–3 concepts, to test whether
  the model picks a coherent single target.

For each note, request **6 items** cycling the in-scope archetypes, at
operational difficulty. Total = **90 items per model per run**; do **3 runs** per
model (different seeds/temperature 0.7) to measure consistency → 270 items/model.

> The exact note list and a runnable harness stub belong to Day-2 of the build
> (the spec wants the eval built before training). This doc specifies *what* to
> run and *how to decide*; the harness is scaffolded in the training plan
> (Deliverable 4).

---

## 4. Scoring

### 4a. Programmatic gates (cheap, run first)

- valid JSON, 4 options, exactly one answer key
- regex reject `all of the above|none of the above`
- option-length variance within bound (correct answer not the longest by >X%)
- answer-key position roughly balanced across a run (detects "always C" collapse)
- concept-leak check: the answer phrase does not appear verbatim in the stem

### 4b. LLM-as-judge (a strong frontier model, NOT the model under test)

Per item, score each **disqualifying** check as pass/fail, plus three graded
dimensions on **0 / 1 / 2** (from the spec's rubric):

| Dimension | 0 | 1 | 2 |
| :--- | :--- | :--- | :--- |
| **Spec adherence** | violates ≥1 disqualifying check | minor wobble | fully expert-grade |
| **Distractor craft** | ≥1 filler/implausible option | mixed | every distractor a named error |
| **Scenario novelty** | asks the note back to itself | partial reframe | genuinely new scenario |

- **`expert_grade(item)`** = all disqualifying checks pass **and** every graded
  dimension ≥ 1 **and** Spec adherence = 2.
- Judge reliability is itself checked: 20% of items get a second independent
  judge pass; report agreement.

### 4c. Metrics per model

- **Pass rate** = fraction of items that are `expert_grade` (primary metric).
- **Mean rubric** per dimension.
- **Consistency** = std of pass rate across the 3 runs (lower = better).
- **Archetype breakdown** = pass rate per archetype (reveals which archetypes are
  the real bottleneck — expected: F1 easy, F3/F4 hard).

---

## 5. Models to run (the comparison that makes the decision)

| Tier | Model(s) | Role |
| :--- | :--- | :--- |
| **SLM candidates** | Qwen3-0.6B / 1.7B / 4B **Instruct** (+ optionally Llama-3.2-1B/3B) | The would-be base. This is what an SLM must beat. |
| **Frontier ceiling** | a top frontier model (GPT/Claude class) | The distillation *teacher*. Establishes whether the behavior is achievable at all. |

Run the **identical** prompt + inputs through both tiers.

---

## 6. Decision matrix

Let `S_small` = best small-candidate pass rate, `S_frontier` = frontier pass rate.

| Condition | Door | Reasoning |
| :--- | :--- | :--- |
| `S_small ≥ 80%` (reliable) | **DON'T BUILD** | A prompt already does it — the spec's litmus fails; ship a prompt, not a fine-tune. |
| `S_frontier ≥ 70%` **and** `S_small ≤ 45%` | **BUILD (distill)** | The behavior is achievable (teacher exists) but small models can't reach it by prompting — the exact gap SFT/QLoRA closes. This is the target regime. |
| `45% < S_small < 80%` | **BUILD (narrow first)** | Promising but shaky; scope down to the highest-gap archetypes and distill. |
| `S_frontier < 50%` even with few-shot | **RETHINK** | If the *teacher* can't do it reliably, we have no clean labels to distill; the behavior is underspecified or too hard → brainstorm a reframing (e.g. constrain archetypes, add retrieved context, change the unit of output). |

**Expected prior (to be confirmed by the run, not assumed):** F1/simple-F2
archetypes fall in the DON'T-BUILD zone even for small models; F3/F4 crown-jewel
archetypes (`EXPERIMENTAL_FIX_OR_FLAW`, `THEORY_PLUS_STUDY`) fall in the BUILD
zone (frontier can, small can't). This is the empirical basis for the scope
decision in Deliverable 3.

---

## 7. A note on evidence we already have

`prev_data`'s OpenMCAT items are themselves AI-generated (per the build script
header) yet are genuinely strong (e.g. the LDH-R kinetics passage). That is
weak-but-real evidence that a **capable** model *can* produce expert-grade items
— i.e. the ceiling is non-zero, pushing us away from the RETHINK door for at
least F2/F3. It says **nothing** about whether a **0.6–4B** model can, which is
exactly what the litmus run must measure. Do not skip the run on the strength of
this prior.

---

## 8. Output of this stage

A results table (`docs/02b_litmus_results.md`, produced when the harness runs)
with pass rates by model × archetype, the door selected, and the archetype-level
gap profile. That profile is the direct input to the **feasibility agent**
(Deliverable 3), which converts "there is a gap" into "here is the exact scope an
SLM can win, at >90% confidence."
