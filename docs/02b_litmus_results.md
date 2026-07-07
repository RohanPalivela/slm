# Litmus Results & Diagnosis (Deliverable 2b)

> Empirical build-gate record. Produced by `eval/harness.py` per
> [`02_litmus_test_prompt.md`](02_litmus_test_prompt.md), scope = the causation
> pair (`CAUSE_OF_SOURCE` + `EFFECT_OF_SOURCE`) on the 10 `LITMUS` sources.
> Models: local **Qwen3-4B** (candidate) vs **Claude Opus 4.8** (teacher) via an
> OpenAI-compatible gateway; judge = **GPT-5.5** (different family).

---

## Run 1 — 2026-07-07 (10 sources × up to 6 items × 3 runs)

| Model | Role | Items | Expert-grade | key_valid | Consistency (std) | date-fail | leak |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen3-4b | candidate | 30 | **13%** | 43% | 0.094 | 10% | 0% |
| claude-opus-4-8 | teacher | 180 | **28%** | **98%** | 0.028 | 1% | 0% |

Per-archetype (expert-grade): teacher CAUSE 29% / EFFECT 27%; candidate CAUSE 13%.

**Harness door: RETHINK** (rule: teacher expert-grade < 50% → "no clean labels").

### Why the door is misleading on Run 1 (root-cause analysis)

The RETHINK is driven **entirely by one fixable failure mode**, not by an inability
to do the task. Evidence from `results/litmus_items.jsonl` (teacher, n=180):

| Judge dimension / check | Result | Read |
| :--- | :--- | :--- |
| `key_historically_correct` / `key_uniquely_best` | 98% valid | keys are correct & unique ✅ |
| `outside_knowledge_skill_fit` | 169/180 = 2 | genuinely needs outside knowledge, right skill ✅ |
| **`distractors_period_plausible`** | **FALSE on 121/180 (67%)** | **the sole bottleneck** ❌ |
| `spec_adherence` | 8×0, 121×1, 51×2 | that one failing check caps spec at 1 → fails expert-grade |

**126 of 180 teacher items had a valid key AND passed every programmatic check, yet
failed expert-grade solely on distractor quality.** Judge notes name the exact
problem:

- *"Social Darwinism is an overly obvious wrong-era distractor for a 1776 question."*
- *"the headright system distractor is an obvious wrong-era option rather than a
  plausible later development."*

**Diagnosis.** With the original maximal prompt, even Opus wrote `WRONG_ERA`
distractors that are *giveaways* — real developments, but from a century away, so a
student eliminates them instantly. A wrong-era trap only works when it is from a
**neighboring / plausibly-confusable era**. This is precisely the "on-the-nose
wrong answers" failure the whole project targets — so the judge is right to
penalize it, and the litmus correctly surfaced that **distractor subtlety is the
hard part**.

Candidate contrast: 13% expert-grade and **key_valid only 43%** (the base model
fabricates / double-keys answers), spec mostly 0 → the base is far worse, so the
base-vs-teacher gap that a fine-tune would close clearly exists.

---

## Action taken (before Run 2)

Tightened the **distractor rule** in
[`../prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md)
(rules 4–5), the "tempting, not a giveaway" fix:

- `WRONG_ERA` distractors must come from a **neighboring / plausibly-confusable
  era** (ideally the adjacent period, same theme) — never an obvious-century-off
  giveaway.
- **At most ONE** distractor may be `WRONG_ERA`; the other two must be same-era
  traps (`TRUE_BUT_IRRELEVANT` / `SCOPE_MISMATCH` / `PARTIALLY_TRUE`) so the item
  cannot be solved by chronology alone.
- Added a **hard subtlety self-test**: "Could a well-prepared student eliminate
  this in under one second because it's from an obviously different century/topic?
  If yes, discard and rewrite closer."

(The bulk `data_gen_prompt.md` forks the litmus SYSTEM, so it inherits this. A
further lever, if Run 2 still falls short, is candidate-set grounding: inject a
*period-windowed* development list so distractors are drawn from era-appropriate
options.)

## What Run 2 must show to flip to BUILD

- **P1:** teacher expert-grade **≥70%** (key_valid already 98%, so the only thing
  that needs to move is `distractors_period_plausible` → `spec_adherence` = 2).
- **P2:** prompted candidate **≤45–55%** expert-grade (Run 1 was 13% — expected to
  stay low; the base model's real failure is key validity + format).
- If teacher clears ≥70%: **BUILD (distill)** — clean labels exist and the gap is
  large. If it does not even with grounding: escalate to a genuine RETHINK (change
  the output unit, e.g. "repair/grade an item").

> Re-run: `python3 eval/harness.py --runs 3 --n 6`, then inspect with
> `python3 eval/show_items.py --model claude-opus-4-8 --fails-only` and append the
> Run 2 table below.
