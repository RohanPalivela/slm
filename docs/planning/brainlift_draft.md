# Brainlift Draft — Notes → Expert MCAT Questions (SLM)

> Spec Day 1 deliverable (draft). Final revision with evidence ships at M6.

---

## Spiky POV (thesis)

**Expert MCAT questions are not “flashcards with four options.”** They apply a *familiar*
principle in an *unfamiliar* scenario, with distractors that each encode a *named*
reasoning error. LLMs fail this by echoing the note, writing filler distractors, and
keying answers that are wrong or double-correct.

A **fine-tuned 4B model** can learn this reliably **only when the task is structurally
determined** — closed distractor menus + rule-derivable answer keys + a verification
pass — not when it must invent clinical vignettes or do arithmetic from scratch.

**We are not building “an MCAT question generator.”** We are building a **reliable
specialist** for two archetypes that share one deep skill: *classify a scenario into a
named relation and justify each option from a fixed signature.*

---

## Behavior spec (falsifiable)

> Given a study note stating a mechanism-with-a-control-point
> (`MECHANISM_PERTURBATION`) or a theory-with-predictive-content plus a follow-up
> finding (`THEORY_PLUS_STUDY`), the model returns exactly one valid JSON MCQ in which:
> (a) the principle is tested in a scenario **not stated in the note**; (b) **exactly one**
> option is fully correct with an **independently verifiable** key; (c) each distractor is a
> **named error from the archetype’s closed menu**; (d) options are homogeneous with no
> all/none-of-the-above and the stem passes cover-the-options. **PASS** iff all four hold.

This spec is simultaneously the data-gen rubric, eval criterion, and inference guard.

---

## Why this exists (vs prompting a frontier model)

| Approach | Problem |
| :--- | :--- |
| Prompt-only base 4B | Drifts on JSON, note-echo, filler distractors, wrong keys |
| Prompt-only frontier | Works sometimes but expensive, slow, inconsistent — not a product |
| Broad “generate any MCAT type” SLM | Mushy model; SC5 collapses on clinical facts and arithmetic |
| **Narrow tuned 4B + verifier** | Reliable local specialist; dataset is the durable artifact |

---

## What would falsify the thesis

1. Litmus: prompted base 4B ≥80% expert-grade → **don’t build**
2. Litmus: frontier teacher <70% on scope → **rethink** (no clean labels)
3. Tuned model + verifier: key-correctness <85% after v2 data → **rethink scope**
4. Eval gains collapse when dedup threshold tightens → contamination artifact

---

## Evidence to collect (brainlift final)

- Base-vs-tuned pass rate + variance on held-out human notes
- Paraphrase fidelity/novelty (in-scope subset)
- Verifier-off vs verifier-on key-correctness demo
- One data-iteration story (e.g. THEORY not-diagnostic trap under-represented → fixed in data → metric moved)
