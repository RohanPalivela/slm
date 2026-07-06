# Brainlift Draft — Notes/Source → Expert APUSH Questions (SLM)

> Spec Day-1 deliverable (draft). Final revision, with base-vs-tuned evidence,
> ships at M6. Inherits the verdict in
> [`../03_feasibility_assessment.md`](../03_feasibility_assessment.md).

---

## Spiky POV (thesis)

**Expert APUSH multiple-choice questions are not "recall with four options."** Every
one hangs on a **source**, requires connecting that source to an **outside historical
development not stated in it**, and — the part everyone underrates — its distractors
are each a **named trap**: *wrong-era*, *true-but-irrelevant*, *scope-mismatch*, or
*partially-true*. All four wrong answers are **historically true and era-plausible**;
each is wrong for one specific, writable reason. That is exactly what makes them feel
human-made.

LLMs fail this in three predictable ways: they **echo the source** back as the
"question," they write **absurd or obviously-wrong distractors** (the user's core
complaint), and they **mis-key "most directly"** — picking a broad background
condition over the specific mechanism, or keying an answer a second option also
satisfies.

A **fine-tuned 4B model** can learn to avoid all three **only when the task is
structurally determined**: the **stimulus is provided** (not invented), the **stem
comes from a closed command-phrase menu**, the **distractors come from the closed
4-trap menu**, the answer is **grounded to a curated, date-tagged developments table**
(selection, not free recall), and a **programmatic anachronism date-check** guards the
key. Remove that scaffolding and a small model reverts to fabricating history.

**We are not building "an APUSH question generator."** We are building a **reliable
specialist** for the two **date-anchored causation archetypes** —
`CAUSE_OF_SOURCE` and `EFFECT_OF_SOURCE` — which are *the same deep skill in
opposite temporal directions*: "map the stimulus to the one outside development whose
date obeys the required direction and that is the *specific*, not background, match."

---

## Behavior spec (falsifiable)

> Given a **provided, dated source** (primary text) and an optional study note, the
> model returns **exactly one valid JSON MCQ** in which:
> **(a)** answering requires an **outside development not stated in the source**
> (never the source paraphrased back);
> **(b)** **exactly one** option is fully correct, with a key that is **date-consistent
> with the stem's time direction** (cause predates the source; effect postdates it) and
> is the **uniquely "most-directly" match**, drawn from the developments table;
> **(c)** each of the three distractors is one of the **four named traps**, is
> **era-plausible**, and the three span **≥2 trap types**;
> **(d)** options are **homogeneous**, there is **no all/none-of-the-above** or
> absolute-word tell, and the stem is answerable before the options.
> **PASS iff all four hold.**

This single spec is simultaneously the **data-generation rubric**, the **eval
criterion**, and the **inference-time guard**.

---

## Why this exists (vs just prompting)

| Approach | Problem |
| :--- | :--- |
| Prompt-only **base 4B** | Drifts on JSON, echoes the source, writes filler distractors, mis-keys "most directly" — unreliable run-to-run |
| Prompt-only **frontier** | Works *sometimes* but is expensive, slow, and inconsistent — not a cheap local product; and its terms may forbid using outputs to train our model |
| Broad **"generate any APUSH item"** SLM | Mushy model; SC-KEY (historical correctness) collapses across the long tail of facts |
| **Narrow tuned 4B + grounding + verifier** | Reliable local specialist on one deep skill; the **dataset is the durable artifact** |

The defensible win, per the spec, is **reliable constrained behavior (base-vs-tuned)**,
not beating a frontier model on raw capability.

---

## What would falsify the thesis

1. **Litmus: prompted base 4B ≥80%** expert-grade on the causation pair → **don't build**
   (a prompt already suffices).
2. **Litmus: frontier teacher `key_valid_rate` <70%** on the pair → **rethink**
   (no clean labels to distill; the load-bearing precondition).
3. **Tuned 4B: SC-KEY (single-best historical correctness) <~85%** after v2 data
   iteration *and* with the verifier → **rethink scope** (drop to one archetype, tighten
   grounding to a candidate set, or switch the output unit to "repair/grade an item").
4. **Base-vs-tuned gains vanish when the dedup threshold is tightened** → the win was a
   **contamination artifact**, not learned behavior.

---

## Evidence to collect (brainlift final, M6)

- Base-vs-tuned **expert-grade pass rate + run-to-run variance** on held-out sources.
- **Verifier-off vs verifier-on** key-correctness (isolate the grounding/verifier lever).
- **Anachronism date-check** hit rate: how much of the wrong-era error class it removes.
- One concrete **data-iteration story** (e.g., "scope-mismatch distractors under-represented →
  added them in data → the 'most directly' double-key rate dropped").
- **Per-archetype** pass (both `CAUSE_OF_SOURCE` and `EFFECT_OF_SOURCE` ≥ target).
