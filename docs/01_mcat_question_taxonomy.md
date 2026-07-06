# MCAT Question Taxonomy — Deep Research

> **Deliverable 1 of the project.** A grounded, exhaustive map of the question
> types that appear on the MCAT, grouped into categories and rendered in a form
> that a data-generation *agent* can loop over. The companion machine-readable
> file is [`taxonomy/mcat_question_archetypes.json`](../taxonomy/mcat_question_archetypes.json).
>
> **Why this exists:** the goal of the wider project is an SLM that turns
> medical/scientific **notes** into **expert-grade MCAT questions** — questions
> that "feel human-made," not the on-the-nose MCQs that LLMs default to. You
> cannot generate that reliably without a precise, shared vocabulary for *what a
> good MCAT question actually is*. This document is that vocabulary.

---

## 0. How to read this document (for humans and agents)

The MCAT does not label its questions with "types." Question type is an
**emergent** property of three independent axes that every item combines:

| Axis | What it controls | Source of truth |
| :--- | :--- | :--- |
| **A. Cognitive skill** | *What mental operation* the test-taker must perform | AAMC **Scientific Inquiry & Reasoning Skills** (SIRS 1–4); CARS skills |
| **B. Content** | *What knowledge* is required | AAMC **10 Foundational Concepts** → Content Categories |
| **C. Surface form** | *How the item is packaged* | Passage type + stem format (discrete, Roman-numeral, EXCEPT, etc.) |

A concrete question = `(skill) × (content) × (surface form)`. An "archetype"
(Section 6) is a **named, recurring, generation-ready combination** of these
axes — e.g. *"vignette → diagnosis"* is (Skill 2) × (physiology/pathology) ×
(discrete or short-passage). Archetypes are the unit an agent should iterate
over. Sections 1–5 define the axes; Section 6 is the catalog; Section 7 is the
quality bar; Section 8 maps everything to the data we already have.

All facts below are cited to AAMC's own published materials or standard
psychometric item-writing guidance (see `docs/sources.md`).

---

## 1. The MCAT at a glance

The exam has **four sections**. Three are *science content + reasoning*; one
(CARS) is pure reading/argument analysis with **no science content**.

| Section | Abbrev. | Questions | Format | Disciplines |
| :--- | :--- | :--- | :--- | :--- |
| Chemical & Physical Foundations of Biological Systems | **C/P** | 59 | 10 passages (44 Q) + 15 discrete | Gen Chem 30%, Physics 25%, Biochem 25%, O-Chem 15%, Bio 5% |
| Critical Analysis & Reasoning Skills | **CARS** | 53 | **All** passage-based (9 passages) | Humanities 50%, Social sci 50% (no science recall) |
| Biological & Biochemical Foundations of Living Systems | **B/B** | 59 | 10 passages (44 Q) + 15 discrete | Biology 65%, Biochem 25%, Gen/O-Chem 10% |
| Psychological, Social & Biological Foundations of Behavior | **P/S** | 59 | 10 passages (44 Q) + 15 discrete | Psych 65%, Sociology 30%, Biology 5% |

**Two structural facts that dominate everything downstream:**

1. **~75% of science questions are passage-based; ~25% are discrete.** A
   "passage" is a 200–400-word block describing an experiment, an information
   set, or an argument, followed by 4–7 questions. Discrete questions stand
   alone. *The prized "expert-feeling" questions are almost always
   passage-based* — the passage is what lets a question build a novel scenario
   on top of known content.
2. **Most questions test knowledge you have in a context you've never seen.**
   The recurring design principle in every AAMC example: *familiar concept,
   unfamiliar scenario.* This is the single most important thing an LLM
   generator gets wrong (it tends to test the concept in the *same* context the
   note presents it).

---

## 2. Axis A — Cognitive skill (the "spine")

### 2a. Science sections: the four Scientific Inquiry & Reasoning Skills (SIRS)

AAMC explicitly writes every science item to one of four skills. **These are
the official, load-bearing categories** — the closest thing to a canonical
"question type" list the MCAT has. The per-section weighting is identical across
C/P, B/B and P/S:

| Skill | Name | Weight | One-line essence |
| :--- | :--- | :--- | :--- |
| **Skill 1** | Knowledge of Scientific Concepts & Principles | **35%** | Recognize / recall / relate a concept; plug into a given equation. |
| **Skill 2** | Scientific Reasoning & Problem-Solving | **45%** | *Use* a concept to predict, explain, or judge a novel case. |
| **Skill 3** | Reasoning About the Design & Execution of Research | **10%** | Evaluate methodology: variables, controls, confounds, ethics, "what would you change." |
| **Skill 4** | Data-Based & Statistical Reasoning | **10%** | Read a table/graph; draw the conclusion the data *do* (and don't) support. |

> **Load-bearing insight for scope:** Skills 1+2 = **80%** of all science
> questions. Skills 3+4 = only **20%** — but Skills 3 & 4 are exactly the
> "experiment/data → conclusion" questions the user finds most impressive and
> most human. They are the hardest to write well *and* the lowest-volume. This
> tension (impressiveness vs. frequency vs. difficulty) is the central scoping
> question for the SLM.

**Skill-by-skill detail with authentic AAMC examples** (verbatim item cores
from AAMC's *Scientific Inquiry and Reasoning Skills* guide):

- **Skill 1 — Knowledge / Relate.** *"In a study, each trial administers a drop
  of lemon juice and measures salivation; over trials, salivation declines; the
  researcher then switches to lime juice. This researcher is most likely
  studying which process?"* → **Habituation and dishabituation.** The item
  *dresses recall as a mini-scenario* — this is why even "recall" MCAT questions
  don't feel like flashcards.
- **Skill 2 — Reason / Predict.** *"The radius of the aorta is ~1.0 cm, blood
  velocity 30 cm/s; a capillary radius ~4×10⁻⁴ cm, velocity 5×10⁻² cm/s.
  Approximately how many capillaries are in the body?"* → requires recognizing
  flow-continuity (Q is conserved) then computing. **Familiar principle,
  unfamiliar target quantity.**
- **Skill 3 — Critique the study.** *"A test for urinary protein via
  precipitation is complicated by calcium phosphate precipitation. Which
  procedure prevents precipitation of the salt?"* → *change an experimental
  parameter to remove a confound.* The stem hands you a flawed method and asks
  for the fix.
- **Skill 4 — Read the data.** *"Three curves show hemoglobin O₂ binding at pH
  7.2 / 7.4 / 7.6. What conclusion can be drawn?"* → **Low pH favors the
  low-affinity state (Bohr effect).** The concept is trivial; the work is
  *extracting the relationship from the figure.*

### 2b. CARS: three reasoning skills (no science content)

CARS is **out of primary scope** for a note→question model (it needs a
humanities/social-science *passage*, not medical notes), but a complete
taxonomy must include it, and its "reasoning-beyond-the-text" machinery is a
useful template for the science "apply to a new scenario" archetypes.

| CARS Skill | Weight | Sub-types |
| :--- | :--- | :--- |
| Foundations of Comprehension | 30% | Main Idea / Primary Purpose · Detail (direct retrieval) · Inference · Definition-in-Context |
| Reasoning Within the Text | 30% | Function ("why did the author include X") · Strengthen–Weaken *within* the passage |
| Reasoning Beyond the Text | 40% | Apply / Analogy to a new case · Strengthen–Weaken with *new outside* info · Author-response / Prediction |

The single highest-value, hardest CARS pattern — **"here is new outside
information; how does it affect the author's argument?"** — is structurally
identical to the science **"here is a follow-up study; what does it do to the
theory?"** archetype (Section 6, `THEORY_PLUS_STUDY`). That structural reuse is
important for the SLM: one reasoning shape, many content skins.

---

## 3. Axis B — Content (the 10 Foundational Concepts)

Every science item is tagged to one of AAMC's **10 Foundational Concepts**,
each subdivided into Content Categories. The SLM does not need to *reproduce*
this hierarchy, but the generator must **respect it**: a good question stays
inside one coherent content pocket and tests it at MCAT depth.

| FC | Section | Theme |
| :--- | :--- | :--- |
| FC1 | B/B | Biomolecules → structure/function of cells (55% of B/B) |
| FC2 | B/B | Assemblies of molecules/cells/organs carry out functions (20%) |
| FC3 | B/B | Systems sense environment & maintain homeostasis (25%) |
| FC4 | C/P | Physical principles of transport, sensing, signaling (40% of C/P) |
| FC5 | C/P | Chemical principles of molecular dynamics (60% of C/P) |
| FC6 | P/S | Sensing, perceiving, thinking, reacting to stimuli (25% of P/S) |
| FC7 | P/S | Factors influencing behavior & behavior change (35%) |
| FC8 | P/S | Self-identity & social interaction (20%) |
| FC9 | P/S | Social/cultural differences & well-being (15%) |
| FC10 | P/S | Social stratification & resource access (5%) |

We already hold a **56-concept, kebab-case content taxonomy** (`prev_data/
speedrun_concepts.json`) that maps cleanly onto these FCs across 7 topics
(biochemistry, biology, general-chemistry, organic-chemistry, physics,
psychology, sociology). That file is the ready-made *content vocabulary* for
the generator; the FC table above is its authority spine.

---

## 4. Axis C — Surface form

### 4a. Passage types (science sections)

Every science passage is one of three types (AAMC / standard prep taxonomy):

1. **Experiment / Research Presentation** — describes a study: setup, methods,
   variables, results (often tables/figures). *Feeds Skills 3 & 4.* This is the
   richest soil for expert questions and the format of the strongest items in
   our existing bank (e.g. the OpenMCAT `LDH-R` kinetics passage).
2. **Information / Situation Presentation** — lays out a phenomenon, model, or
   real-world situation and asks you to interpret/apply it. *Feeds Skills 1 & 2.*
3. **Persuasive / Argument Presentation** — advances a scientific claim/position
   (more common in P/S); asks you to evaluate the argument. *Feeds Skill 2.*

### 4b. Stem format modifiers (overlay any skill/content)

These change the *packaging*, not the underlying skill, and each has its own
failure modes for a generator:

| Format | Shape | Notes for generation |
| :--- | :--- | :--- |
| **Standard best-answer** | "Which of the following…" + 4 options | The default. "Most likely / best explains" framing is deliberate — more than one option can be *partly* right; exactly one is *best*. |
| **Roman-numeral (I/II/III)** | 3 statements; options are combinations ("I and III only") | Tests multiple facts at once; hard to write so that combinations are non-redundant and all individually defensible. |
| **Negative (EXCEPT / LEAST / NOT)** | "All of the following… EXCEPT" | Three options true, one false (or "least" supported). Easy to write badly (the odd-one-out becomes obvious). |
| **2×2 / paired reasoning** | Choose claim **and** the reason ("because…") | Common for cause/effect; both halves must be independently gradeable. |
| **Data-referenced** | "According to Figure 2 / Table 1…" | Requires an actual data object; answer must be *forced* by the data, not by prior knowledge. |

**Hard constraints from psychometric best practice (NBME / Medical Council of
Canada / Haladyna):** options must be *homogeneous* (same category, grammar,
length); every distractor must be *plausible* and traceable to a **specific
misconception or reasoning error**; **never** use "all/none of the above";
the stem should be answerable *before* seeing the options ("cover-the-options"
test). These rules are the operational definition of "not on the nose."

---

## 5. The four families (the top-level grouping)

Collapsing Axis A into generation-friendly buckets gives **four families**.
Every archetype in Section 6 belongs to exactly one. This is the grouping to
hang the SLM's scope decision on.

| Family | Maps to | Volume | "Human-expert" feel | Note-input required |
| :--- | :--- | :--- | :--- | :--- |
| **F1 · Knowledge & Discrimination** | SIRS 1 | High (35%) | Low–Med | A concept + its near-neighbors |
| **F2 · Applied Reasoning** | SIRS 2 | Highest (45%) | Med–High | A concept + a mechanism/relationship |
| **F3 · Research & Experiment** | SIRS 3 | Low (10%) | **Highest** | A concept that implies a *method* / study |
| **F4 · Data & Statistics** | SIRS 4 | Low (10%) | **High** | A concept + a *quantitative relationship* |

The user's two motivating examples map as: *"symptoms → diagnosis"* → **F2**
(applied reasoning over pathophysiology); *"theory + follow-up study →
conclusion"* → **F3/F4 hybrid** (the crown-jewel archetype).

---

## 6. The archetype catalog (the generation-ready unit)

Each archetype below is the atomic thing a generation agent iterates over.
Fields mirror the JSON companion so the doc and the machine file stay in sync:

- **`id`** — stable slug.
- **`family`** — F1–F4.
- **`skill`** — SIRS skill.
- **`input_needed`** — what must be present in the source note to seed it.
- **`shape`** — the template of the stem.
- **`good_example`** — an authentic-style item (answer + why the distractors work).
- **`llm_failure`** — how a naive LLM ruins this archetype ("the tell").
- **`difficulty_levers`** — how to dial rigor up/down.

### F1 — Knowledge & Discrimination

**`CONCEPT_DISCRIMINATION`** · Skill 1
- *input_needed:* a concept plus ≥1 easily-confused neighbor (habituation vs.
  sensitization; competitive vs. noncompetitive inhibition).
- *shape:* a short scenario that instantiates one concept; ask which
  process/principle it is, with the confusable neighbors as distractors.
- *good_example:* the lemon-juice/lime-juice salivation item → *habituation &
  dishabituation* (distractors: sensory adaptation, stimulus generalization,
  classical conditioning — each a real neighbor a novice would pick).
- *llm_failure:* names the concept in the stem, or picks distractors from
  unrelated chapters so the answer is obvious by topic-matching.
- *difficulty_levers:* closeness of the neighbors; whether the scenario is
  described in lay terms vs. jargon.

**`REPRESENTATION_TRANSLATION`** · Skill 1
- *input_needed:* a concept expressible in ≥2 forms (prose ↔ graph ↔ equation ↔
  structure).
- *shape:* give one representation, ask for the matching one (e.g. "which graph
  shows the relationship between educational attainment and life expectancy?").
- *llm_failure:* trivial one-to-one mapping with no plausible mis-readings.

### F2 — Applied Reasoning

**`MECHANISM_PERTURBATION`** · Skill 2  *(highest-value F2 pattern)*
- *input_needed:* a mechanism/pathway with a control point (enzyme kinetics, a
  feedback loop, a circuit, an equilibrium).
- *shape:* introduce a perturbation (inhibitor, mutation, ΔpH, added
  resistance); ask for the downstream consequence.
- *good_example:* *"A pyruvate analog (PYA) raises apparent Km for pyruvate from
  0.10→0.55 mM with Vmax nearly unchanged. Which mechanism best describes PYA's
  effect?"* → **Competitive inhibition.** Distractors (uncompetitive,
  allosteric activation, tetramer dissociation) each match a *different*
  Km/Vmax signature — so the item forces true discrimination. (Authentic
  OpenMCAT item in our bank.)
- *llm_failure:* the perturbation and the answer are the same fact restated;
  distractors are random rather than each a distinct mechanistic signature.
- *difficulty_levers:* one-hop vs. two-hop (perturbation → intermediate →
  observable); whether numbers are given.

**`QUANTITATIVE_APPLICATION`** · Skill 2
- *input_needed:* a governing equation/relationship + a scenario where the
  target quantity isn't the one directly given.
- *shape:* novel scenario → select the right model → compute/estimate.
- *good_example:* the aorta→capillary count item (flow continuity + geometry).
- *llm_failure:* plug-and-chug where the needed equation is obvious and the
  numbers are clean; no unit or order-of-magnitude reasoning.

**`CLINICAL_VIGNETTE_TO_DIAGNOSIS`** · Skill 2  *(user's example #1)*
- *input_needed:* a condition with a recognizable sign/symptom or lab
  signature, plus differentials that share features.
- *shape:* present symptoms/labs/history → ask for the most likely diagnosis,
  underlying mechanism, or best next step.
- *llm_failure:* pathognomonic giveaway in the stem ("bronze skin + cirrhosis +
  diabetes" spelled out) and differentials that don't share any presenting
  feature — the hallmark "too on-the-nose" question. Expert version withholds
  the giveaway and makes each differential explain *some* of the findings.
- *difficulty_levers:* number of overlapping differentials; whether the ask is
  diagnosis vs. mechanism vs. management.

**`PRINCIPLE_TO_PREDICTION`** · Skill 2
- *input_needed:* a theory/model with predictive content (cultural capital,
  Maslow, Le Chatelier, natural selection).
- *shape:* "which outcome does <theory> predict in <new situation>?"
- *good_example:* *"What does the concept of cultural capital predict?"* →
  distinctions associated with elite classes become more valued.
- *llm_failure:* restates the theory's definition as the correct option.

### F3 — Research & Experiment  *(highest "expert" feel)*

**`IDENTIFY_VARIABLES`** · Skill 3
- *input_needed:* a describable study with manipulated and measured quantities.
- *shape:* describe the study → ask for IV / DV / control / confound.
- *good_example:* social-loafing study (solo vs. group × task) → IV = working
  alone-vs-group, DV = individual contribution. Distractors swap IV/DV or name
  the wrong quantity.
- *llm_failure:* IV/DV are labeled in the stem; confound options are nonsense.

**`EXPERIMENTAL_FIX_OR_FLAW`** · Skill 3  *(crown-jewel #1)*
- *input_needed:* a method with a realistic failure mode / confound.
- *shape:* present a method that has a subtle problem → ask what change removes
  the confound (or what flaw invalidates the conclusion).
- *good_example:* urinary-protein precipitation test giving false positives from
  calcium phosphate → *buffer to neutral pH.* The reasoning is entirely about
  the method, not the underlying chemistry fact.
- *llm_failure:* invents a flaw that isn't real, or the "fix" is generic ("use a
  bigger sample").
- *difficulty_levers:* subtlety of the confound; whether domain knowledge is
  needed to see it.

**`DESIGN_THE_TEST`** · Skill 3
- *input_needed:* a hypothesis or claim.
- *shape:* "which experiment/measurement would best test <hypothesis>?" or
  "which is the most appropriate control?"
- *llm_failure:* the "best" design is obviously best; alternatives don't
  actually test the hypothesis at all.

### F4 — Data & Statistics  *(high "expert" feel)*

**`DATA_TO_CONCLUSION`** · Skill 4
- *input_needed:* a quantitative relationship expressible as a small table/graph.
- *shape:* present a compact data object → ask the single conclusion it
  supports.
- *good_example:* hemoglobin O₂-binding curves at three pH values → low pH →
  low-affinity state. Distractors: "affinity independent of pH," "binding
  noncooperative at low pH" — each a *specific* misreading of the figure.
- *llm_failure:* the "data" merely restate a fact; distractors aren't tied to
  particular misreadings; the correct answer over-generalizes beyond the data.

**`THEORY_PLUS_STUDY`** · Skill 4 / Skill 2 hybrid  *(user's example #2 — crown-jewel #2)*
- *input_needed:* a theory/model **and** a plausible follow-up finding.
- *shape:* state a theory → introduce a *new* study result → ask what it does to
  the theory (supports / weakens / is irrelevant / requires which revision).
- *good_example (shape):* "Model M predicts X. A follow-up finds Y under
  condition Z. Which conclusion is best supported?" — options span
  {supports, weakens, consistent-but-not-diagnostic, contradicts a *different*
  claim}. This is the single most "human-expert" archetype and the one LLMs
  most reliably botch.
- *llm_failure:* the new study trivially confirms or trivially refutes; no
  "consistent-but-uninformative" trap; the conclusion isn't actually licensed by
  the finding.
- *difficulty_levers:* whether the finding is confound-laden; whether the
  correct answer is "cannot conclude" (calibration to uncertainty).

**`STATISTICAL_INFERENCE`** · Skill 4
- *input_needed:* a result with a statistical property (correlation, p-value, CI,
  spread, sampling frame).
- *shape:* ask what claim the statistics license (correlation≠causation, what a
  CI means, why median>mean for income, generalizability from the sample).
- *good_example:* "Which correlation supports the bystander effect?" → # of
  bystanders positively correlated with time-to-help.
- *llm_failure:* conflates significance with effect size; distractors aren't
  real statistical misconceptions.

### Format overlays (applied to any archetype above)

`ROMAN_NUMERAL`, `NEGATIVE_EXCEPT`, `PAIRED_CLAIM_REASON`, `DATA_REFERENCED`.
These are **modifiers**, not standalone archetypes — an agent selects an
archetype, then optionally applies one overlay. (See JSON `overlays`.)

---

## 7. What separates an *expert* question from an *LLM* question

This section is the **quality rubric** — it is simultaneously the data-gen
filter and (later) the eval criterion. An item is "expert-grade" only if it
clears **all** of these; LLM-default questions typically fail 3+.

1. **Familiar concept, unfamiliar scenario.** The tested idea must be applied in
   a context *not* stated in the source note. If the note says "PFK-1 is the
   rate-limiting enzyme," a bad item asks "what is the rate-limiting enzyme of
   glycolysis?"; a good item drops you into a cell with high ATP/citrate and
   asks which step slows.
2. **The stem is answerable without the options** (cover-the-options test). If
   the options are load-bearing for comprehension, the item is testing
   test-taking, not knowledge.
3. **Every distractor encodes a specific, nameable error.** For each wrong
   option you must be able to write the exact misconception or misstep that
   makes a competent-but-imperfect student choose it. "Random plausible-sounding
   phrase" is disqualifying. (This is the #1 differentiator per NBME/MCC/
   Haladyna guidance and the user's core complaint about "obvious wrong
   answers.")
4. **Options are homogeneous** — same category, grammar, and length; the correct
   answer isn't the longest/most-qualified; no "all/none of the above."
5. **≥2 hops of reasoning** for F2–F4 items (perturbation→intermediate→
   observable; data→pattern→conclusion). One-hop lookups belong only in a
   minority of Skill-1 items.
6. **Calibrated to uncertainty where appropriate.** The best F3/F4 items include
   a "cannot be concluded / consistent but not diagnostic" option that is
   *sometimes correct*, punishing over-claiming.
7. **No self-contained tells:** no grammatical agreement leaking the answer, no
   absolute-word distractors ("always/never") that are trivially false, no
   numeric answer that's the only "round" one.

> These seven checks are directly encodable as an LLM-as-judge rubric and a set
> of programmatic checks (option length variance, "all of the above" regex,
> answer-position balance, concept-leak detection). They are the bridge from
> this research to the eval harness the spec demands *before* training.

---

## 8. Mapping to assets we already have (`prev_data/`)

| Asset | What it is | Role in the pipeline |
| :--- | :--- | :--- |
| `speedrun_question_bank.json.gz` | 1,586 MCQs: **169 OpenMCAT** (with passages, per-choice explanations, "common mistake" notes) + **1,417 MMLU** (MCAT-relevant subsets, no explanations) | The OpenMCAT items are **few-shot gold** for F2/F3/F4 (esp. passage + Km/Vmax reasoning). MMLU items are mostly F1 — useful as *negative* examples of "flat" questions and as content seeds. |
| `speedrun_concepts.json` | 60-concept content taxonomy across 7 topics | The generator's **content vocabulary**; ties every generated item to a concept slug. |
| `speedrun_first_principles.json` | Hand-authored "first-principle" cards (the underlying rule a *family* of questions tests) | **Seed material**: exactly the "notes → concept" front-half the SLM must expand from. A card's `back` is the principle; the SLM's job is to build a novel scenario on top of it. |
| `speedrun_paraphrase.json` | 30 cards × 2 reworded items testing the *same* idea in new words | A ready-made **transfer test**: proves whether generated questions test the idea rather than the surface wording — a direct measure of "familiar concept, unfamiliar scenario." |

**Implication:** we already possess (a) a content spine, (b) principle-level
seeds, (c) authentic expert-style exemplars with distractor rationales, and (d)
a transfer-style eval scaffold. The missing piece the SLM must add is
*reliable* generation of the F2–F4 archetypes with Section-7 quality.

---

## 9. Agent-iteration interface

The machine-readable catalog lives in
[`taxonomy/mcat_question_archetypes.json`](../taxonomy/mcat_question_archetypes.json).
Its top-level shape:

```jsonc
{
  "families":  [ { "id": "F2", "name": "...", "skill": "SIRS-2", "weight": 0.45, ... } ],
  "archetypes":[ { "id": "MECHANISM_PERTURBATION", "family": "F2", "skill": "SIRS-2",
                   "input_needed": "...", "shape": "...", "good_example": {...},
                   "llm_failure": "...", "difficulty_levers": [ ... ],
                   "expert_feel": 0.8, "note_seedability": 0.9 } ],
  "overlays":  [ { "id": "ROMAN_NUMERAL", "applies_to": ["*"], "rule": "..." } ],
  "quality_checks": [ { "id": "distractor_has_named_error", "type": "judge|programmatic", ... } ],
  "content_vocabulary_ref": "../prev_data/speedrun_concepts.json"
}
```

An agent's generation loop is then: **pick a concept** (from
`content_vocabulary`) → **pick an archetype** (weighted by scope decision) →
**optionally apply an overlay** → **generate** to `shape` → **self-filter**
against `quality_checks` → keep/discard. The scope decision in Deliverable 3
determines *which* archetypes stay in the loop.

---

### TL;DR for the next stages

- The MCAT's real "type" system is **SIRS 1–4** (science) + **3 CARS skills**,
  crossed with **content** and **surface form**.
- We distilled that into **4 families → ~13 generation-ready archetypes**, with
  the "expert feel" concentrated in **F3/F4** (only 20% of the exam, hardest to
  write, most human).
- The user's two examples are `CLINICAL_VIGNETTE_TO_DIAGNOSIS` (F2) and
  `THEORY_PLUS_STUDY` (F4-hybrid) — the two crown-jewel targets.
- Quality is defined by **7 concrete checks** (Section 7), all encodable as an
  eval, all centered on *distractors tied to named errors* and *familiar
  concept / unfamiliar scenario*.
