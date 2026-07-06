# APUSH Taxonomy Supplement — Additive Research

> **Companion to** [`01_apush_question_taxonomy.md`](01_apush_question_taxonomy.md)
> and [`taxonomy/apush_question_archetypes.json`](../taxonomy/apush_question_archetypes.json).
> Material that is either **out of the primary MCQ scope** (the free-response
> question types) or **not yet a standalone archetype** in the JSON. v1 SLM scope
> intentionally uses a subset of MCQ archetypes; this file preserves the full map
> for v2+ and for agent iteration.

---

## 1. The free-response question types (out of primary scope)

The SLM's task ("notes → questions") targets the **machine-checkable MCQ**. The
three free-response types produce *open-ended prose graded by rubric*, so they
are not single-best-answer items and are excluded from v1. They are mapped here
because (a) they share the same skill spine, and (b) a v2 stretch could generate
**FRQ prompts** (not answers), which *is* a constrained generation task.

### 1a. Short-Answer Question (SAQ) — 3 questions, 40 min, 20%

- **Shape:** a prompt with parts **(a), (b), (c)**, each asking for a *brief*
  identify/describe/explain. Q1 includes 1–2 **secondary** sources; Q2 includes 1
  **primary** source; Q3/Q4 (student choice) have **no stimulus**. [CED-exam]
- **Skill spine:** P1 (developments), P3 (claims/evidence), P5 (a reasoning
  process). A very common SAQ shape is the **secondary-source pair**: *"describe
  one difference between the two historians' interpretations; explain one piece of
  evidence that supports each."* — the open-ended twin of the MCQ archetype
  `COMPETING_INTERPRETATIONS`.
- **Why v2, not v1:** grading requires a rubric-based LLM-judge on free text
  (no closed option set), so the answer-key verifier that anchors MCQ feasibility
  does not apply. Generating *SAQ prompts* is feasible; grading answers is a
  separate project.

### 1b. Document-Based Question (DBQ) — 1 question, 60 min, 25%

- **Shape:** a prompt + **7 documents**; the student writes a thesis-driven essay
  using ≥6 documents, ≥1 piece of outside evidence, and document sourcing (POV /
  purpose / situation / audience for ≥3 docs). Range **1754–1980**. Scored on a
  7-point rubric (thesis, context, evidence, sourcing, complexity). [CED-exam,
  CED-sample]
- **Skill spine:** all of P2, P3, P4, P5, P6 at once — the fullest expression of
  the discipline.
- **Relevance to the SLM:** the DBQ is a *goldmine of exemplar stimuli* — its
  documents are exactly the kind of primary/secondary excerpts our MCQ generator
  needs. Legally, we source equivalent public-domain documents ourselves rather
  than reuse College Board's document sets (see
  [`05_data_sourcing_and_legal.md`](05_data_sourcing_and_legal.md)).

### 1c. Long-Essay Question (LEQ) — choose 1 of 3, 40 min, 15%

- **Shape:** three prompt options at different period bands (1491–1800 /
  1800–1898 / 1890–2001), **same reasoning process** across all three (all
  causation, or all comparison, or all CCOT); student writes a thesis essay with
  **no documents**. 6-point rubric. [CED-exam]
- **Relevance:** the LEQ prompt itself is a clean, constrained generation target
  (a well-formed comparison/causation/CCOT prompt at a given period) — a plausible
  v2 output unit that reuses the reasoning-process menu without needing an
  answer-key verifier.

---

## 2. MCQ archetypes / patterns not yet standalone in the JSON

Recurring MCQ shapes found in the CED sample set and prep-source corpora that are
folded into existing archetypes today but could be split out for v2:

| Candidate archetype | Skill | Shape | Note |
| :--- | :--- | :--- | :--- |
| `MAIN_POINT_OF_SOURCE` | P1/P3 | "the author's main argument is best summarized as…" | pure comprehension; low expert-feel; base model likely already passes → **don't-build** candidate |
| `POINT_OF_VIEW` | P2 | "the author would most likely agree with…" | currently a `stem_template`; split from `SOURCE_POV_PURPOSE` if needed |
| `SERVES_AS_EVIDENCE_FOR_CLAIM` | P3 | "best serves as evidence for the [quoted sub-claim]" | narrower than `EVIDENCE_SUPPORTS_CLAIM`; anchors to a quoted phrase (CED Q8) |
| `PRIMARY_PAIR_COMPARISON` | R1 | two **primary** sources; "these two authors would most disagree about…" | the primary-source twin of `COMPETING_INTERPRETATIONS` |
| `MAP_DEVELOPMENT` | P4/GEO | described map → "the pattern shown resulted from…" | needs a described map stimulus (see §3) |
| `CHANGE_OVER_TIME_TABLE` | R3 | described multi-decade table → "which best explains the change from X to Y" | the CCOT twin of the chart-causation item |

These are intentionally **not** in v1 scope; the JSON keeps the catalog tight so
the SLM trains on a narrow, high-reliability distribution (per the spec's "no
broad domains" rule).

---

## 3. Text-only handling of image / map / chart stimuli

A 0.6B–4B **text** model cannot see an image. APUSH uses images heavily (cartoons,
posters, photos, maps, charts). Two options:

1. **Exclude image/map/chart stimuli from v1** (simplest; keeps scope to text
   primary/secondary sources — recommended for the first build).
2. **Render the visual as a structured text stimulus** — the way a released exam's
   *description* would read — so the item is answerable from prose:

```
STIMULUS (image, described):
  type: political_cartoon
  attribution: "Puck magazine, 1901"
  caption: "<the printed caption, if any>"
  description: "<2-4 sentences of neutral visual description: who/what is
    depicted, symbols, labels, and the depicted stance — WITHOUT stating the
    answer to any question about it>"
```

The hard rule (JSON overlay `IMAGE_STIMULUS`): the **description must not state
the answer**; it describes *what is depicted*, and the item still requires outside
knowledge to interpret. This mirrors how the real exam works (the image + a short
attribution; the interpretation is the student's job). For v1 we recommend
**text primary/secondary only**, and treat described-image support as a v2 rung.

---

## 4. Additional surface overlays (future JSON v2)

| Overlay | Rule |
| :--- | :--- |
| `EXCEPT_FRAMING` | "All of the following… EXCEPT" — three era-true developments, one that doesn't fit; the odd-one-out must not be giveaway-obvious |
| `TWO_SOURCE_SET` | the stimulus is *two* sources; items may compare them (feeds `COMPETING_INTERPRETATIONS` / `PRIMARY_PAIR_COMPARISON`) |
| `QUOTED_SUBCLAIM` | the stem quotes a specific phrase from the source and asks for its evidence/meaning (CED Q8, Q10) |

Note: APUSH MCQs **rarely** use Roman-numeral or "all of the above" formats
(unlike some other exams); the dominant format is a single "best-answer" stem with
four homogeneous options. The generator should default to that.

---

## 5. Notes & corrections vs the authoritative CED

| Claim | Status | Note |
| :--- | :--- | :--- |
| Theme code for Politics and Power | **PCE** | Some prep sites abbreviate "POL"; the CED uses **PCE**. |
| MCQ per-skill percentages | **not published** | Unlike MCAT SIRS weights, College Board does not publish a fixed skill-mix for the MCQ; scope decisions use command-phrase frequency + expert-feel, not an official %. |
| Period ranges overlap | **intended** | e.g., Period 4 ends 1848, Period 5 begins 1844 — thematic, not strict boundaries (CED "note about periodization"). |
| "Every MCQ is stimulus-based" | **confirmed** | CED exam page: Section I Part A questions appear in sets of 3–4 based on primary/secondary sources, images, graphs, and maps. |
| Digital format (2025+) | **confirmed** | Exam is delivered in the Bluebook app; structure/timing unchanged. |

Sources for this supplement: College Board AP U.S. History CED and Exam page
[CED-exam, CED-skills, CED-reasoning, CED-content, CED-sample]; see
[`sources.md`](sources.md) for URLs. Prep-source corpora [missed-mcq,
reasoning-guide] corroborate the distractor-trap and command-phrase taxonomy.
