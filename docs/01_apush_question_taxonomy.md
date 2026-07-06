# APUSH Question Taxonomy — Deep Research

> **Deliverable 1 of the project.** A grounded, exhaustive map of the question
> types on the **AP U.S. History (APUSH)** exam, grouped into categories and
> rendered in a form a data-generation *agent* can loop over. The companion
> machine-readable file is
> [`taxonomy/apush_question_archetypes.json`](../taxonomy/apush_question_archetypes.json).
>
> **Why this exists:** the wider project is an SLM that turns study **notes /
> text** into **expert-grade APUSH questions** — items that "feel human-made,"
> not the on-the-nose MCQs LLMs default to (obvious wrong answers, testing the
> note back to itself). You cannot generate that reliably without a precise,
> shared vocabulary for *what a good APUSH question actually is*. This document
> is that vocabulary. All facts are cited to the College Board Course and Exam
> Description (CED) or corroborating sources in [`sources.md`](sources.md).

---

## 0. How to read this document (for humans and agents)

APUSH does not label its multiple-choice questions with "types." A question's
type is an **emergent** property of four independent axes that every item
combines:

| Axis | What it controls | Source of truth |
| :--- | :--- | :--- |
| **A. Skill / reasoning** | *What historical operation* the student performs | CED **Historical Thinking Skills** (6 practices) + **Reasoning Processes** (comparison, causation, continuity & change) |
| **B. Content** | *What knowledge* is required | CED **9 periods** (1491–present) × **8 themes** (NAT/WXT/GEO/MIG/PCE/WOR/ARC/SOC) |
| **C. Stimulus** | *What source* the item hangs on | primary text, secondary/historian text, image/cartoon, map, chart/table |
| **D. Stem template** | *How the question is phrased* (the command phrase) | a small closed menu of official stems ("contributed most directly to…", "best illustrates…", "most similar to…") |

A concrete question = `(skill) × (content) × (stimulus) × (stem template)`. An
**archetype** (Section 6) is a **named, recurring, generation-ready combination**
of these axes. Archetypes are the unit an agent iterates over. Sections 1–5
define the axes; Section 6 is the catalog; Section 7 is the quality bar (what
separates an expert item from an LLM item); Section 8 is the agent interface.

**The single most important structural fact:** on APUSH, **every Section I
multiple-choice question is stimulus-based.** [CED-exam] There are no free-floating
"what year was X" items. Questions come in **sets of 3–4** attached to one
source, and each item couples *reading the source* with *outside historical
knowledge*. This is the APUSH analog of the MCAT's "familiar concept, unfamiliar
scenario," and it is the design principle LLM generators most reliably violate.

---

## 1. The APUSH exam at a glance

| Section | Part | Format | Count | Time | Weight |
| :--- | :--- | :--- | :--- | :--- | :--- |
| I | A — **Multiple choice** | **stimulus sets of 3–4** | **55** | 55 min | **40%** |
| I | B — Short answer (SAQ) | 3 parts each; some sourced | 3 | 40 min | 20% |
| II | A — Document-based (DBQ) | 7 documents → essay | 1 | 60 min | 25% |
| II | B — Long essay (LEQ) | choose 1 of 3 → essay | 1 | 40 min | 15% |

Source: College Board AP U.S. History Exam page and CED. [CED-exam]

**Scope decision for this project.** The user's task — *"take notes / text and
turn it into questions"* — maps directly and almost exclusively onto **Section I
Part A (the stimulus-based MCQ)**. SAQ/DBQ/LEQ are open-ended *written* answers
graded on a rubric; they are not machine-checkable single-best-answer items and
are **out of primary scope** (their skill spine is mapped in
[`01b_taxonomy_supplement.md`](01b_taxonomy_supplement.md) for completeness and
v2). **Everything below is about the MCQ unless noted.**

Two consequences that dominate downstream design:

1. **The item is a *set on a source*, not a lone question.** The generation unit
   is ideally *(one stimulus → 3 non-redundant items)*. This is both more
   authentic and a natural way to force variety of skill within a shared context.
2. **The correct answer and every distractor are historical facts.** Unlike a
   physics MCQ, correctness is not derivable from first principles — it depends
   on the historical record. This is the central **feasibility risk** for a small
   model (fact recall / hallucination), and Section 7 + Deliverable 3 are built
   around neutralizing it (provide the source; verify dates; constrain distractors
   to a closed menu).

---

## 2. Axis A — Skill & reasoning (the "spine")

### 2a. The six Historical Thinking Skills (practices)

The CED writes every task to one of six skills ("practices"). [CED-skills]

| # | Practice | One-line essence | MCQ-facing? |
| :--- | :--- | :--- | :--- |
| **1** | Developments and Processes | Identify/explain the historical development a source shows. | Yes |
| **2** | Sourcing and Situation | Analyze a source's **point of view, purpose, audience, historical situation**. | Yes |
| **3** | Claims and Evidence in Sources | Analyze a source's **argument** and what evidence supports/undermines it. | Yes (crown jewel) |
| **4** | Contextualization | Situate a source/event in the **broader context** that produced or surrounds it. | Yes |
| **5** | Making Connections | Apply a **reasoning process** (below) across developments. | Yes |
| **6** | Argumentation | Build and defend a thesis. | **No** — FRQ only |

Practices 1–5 are the MCQ engine. Practice 6 (Argumentation) is the essay engine
and is out of MCQ scope.

### 2b. The three Reasoning Processes

Practice 5 ("Making Connections") is powered by three reasoning processes — the
"cognitive operations… the way practitioners think in the discipline." [CED-reasoning]

| Process | Aspects (CED) | MCQ command-phrase tell |
| :--- | :--- | :--- |
| **Comparison** | describe / explain / weigh similarities & differences | "most **similar** to", "**differs** from … in that" |
| **Causation** | causes & effects; primary vs secondary; short- vs long-term | "contributed **most directly** to", "most immediately **led to**" |
| **Continuity & Change (CCOT)** | patterns of continuity/change over time; relative significance | "**continuation** of", "would be most **challenged** by" |

> **Load-bearing insight for scope.** APUSH does not publish a fixed
> skill-percentage for the MCQ the way the MCAT publishes SIRS weights. But the
> *command phrase* deterministically signals the skill, and the set of command
> phrases is **small and closed** (Section 4b). This is the single most useful
> fact for a generator: the phrase is a template slot, and the phrase *tells you
> what kind of answer is correct*. "Most directly contributed to" is a different
> task from "best reflects," which is different from "most similar to." [missed-mcq]

### 2c. How the skill hides inside the stem (the pattern to imitate)

Strong students "read the prompt as a skill signal before they read the answer
choices." [reasoning-guide] A generator must do the same in reverse: **pick the
skill first, then emit the command phrase that signals it, then build an answer
of the matching kind.** The most common student (and LLM) error is producing an
answer that is *historically true and era-appropriate but does not answer the
skill the phrase demands* — see Section 7.

---

## 3. Axis B — Content (9 periods × 8 themes)

Every item lives at a `(period, theme)` coordinate. [CED-content]

### 3a. Nine periods (with exam weighting)

| Period | Range | Exam weight | Core? |
| :--- | :--- | :--- | :--- |
| 1 | 1491–1607 | 4–6% | |
| 2 | 1607–1754 | 6–8% | |
| 3 | 1754–1800 | 10–17% | ✅ |
| 4 | 1800–1848 | 10–17% | ✅ |
| 5 | 1844–1877 | 10–17% | ✅ |
| 6 | 1865–1898 | 10–17% | ✅ |
| 7 | 1890–1945 | 10–17% | ✅ |
| 8 | 1945–1980 | 10–17% | ✅ |
| 9 | 1980–present | 4–6% | |

**Core periods 3–8 ≈ 80% of the exam.** Ranges intentionally overlap — College
Board periodization is thematic, not strict. The date-boundaries matter enormously
for the generator because the **#1 distractor trap is "wrong era"** (Section 4c),
which is only nameable if you know when each development happened.

### 3b. Eight themes ("connective tissue")

| Code | Theme |
| :--- | :--- |
| **NAT** | American and National Identity |
| **WXT** | Work, Exchange, and Technology |
| **GEO** | Geography and the Environment |
| **MIG** | Migration and Settlement |
| **PCE** | Politics and Power |
| **WOR** | America in the World |
| **ARC** | American and Regional Culture |
| **SOC** | Social Structures |

The themes are the axis along which the **"true-but-irrelevant" distractor trap**
operates: a wrong answer is often a real, same-era development from a *different
theme* than the stem asks about. The generator's content vocabulary
([`data/apush_periods_themes.json`](../data/apush_periods_themes.json) and the
date-tagged [`data/apush_key_developments.json`](../data/apush_key_developments.json))
is organized on this period×theme grid.

---

## 4. Axis C & D — Stimulus and stem form

### 4a. Stimulus types

Every MCQ set hangs on one source. [CED-exam]

1. **Primary text** — speech, law, party platform, letter, court opinion, treaty,
   pamphlet. Author is a historical actor. *Richest soil for sourcing (P2),
   contextualization (P4), and causation (R2).*
2. **Secondary / historian text** — a scholar's *interpretation* (e.g., "Larson,
   historian, 2001"). *Uniquely enables the crown-jewel "support/undermine the
   argument" and "competing interpretations" items (P3, R1).* A recurring trap:
   students mistake the **publication date** for the historical period.
3. **Image / political cartoon / poster / photograph** — feeds sourcing (P2:
   purpose/audience) and contextualization. **For a text-only SLM the image must
   be rendered as a caption + prose description** (see [`01b`](01b_taxonomy_supplement.md)).
4. **Map** — settlement, expansion, migration, election maps (GEO-heavy).
5. **Chart / table** — demographic/economic time-series. The "explain the
   *pattern*" causation item ("what most directly accounts for the drop after
   1921?") lives here. [missed-mcq]

### 4b. Stem templates (the closed command-phrase menu)

These are transcribed/abstracted from the CED's official sample MCQs [CED-sample]
and prep-source corpora [missed-mcq, reasoning-guide]. **This menu is small and
closed — the key generation lever.** (Full list with time-direction metadata in
the JSON `stem_templates`.)

| Stem template | Command phrase | Skill | Answer is… |
| :--- | :--- | :--- | :--- |
| `cause_of` | "…contributed **most directly** to…" | R2 | a cause (predates the source) |
| `effect_immediate` | "…most **immediately led to**…" | R2 | a short-term effect |
| `effect_longterm` | "…most directly contributed to which **later** characteristic…" | R2→R3 | a long-term legacy |
| `reflects_or_illustrates` | "…best **illustrates** / most directly **reflects**…" | P1 | the broader development |
| `context_response_to` | "…most likely given **in response to**…" | P4 | the prompting situation |
| `influenced_by` | "…most directly **influenced by**…" | P4 | an antecedent idea/movement |
| `purpose_intended_to` | "…most likely **intended to**…" | P2 | the author's purpose |
| `point_of_view` | "…would most likely **agree with**…" | P2 | the implied stance |
| `evidence_supports` | "…best used as evidence to **support** the argument…" | P3 | an outside strengthener |
| `evidence_undermines` | "…best used to **challenge** the argument…" | P3 | an outside weakener |
| `serves_as_evidence_for_claim` | "…best serves as **evidence for the claim** that…" | P3 | the grounding fact |
| `similar_effect` | "…had an effect most **similar** to…" | R1 | a cross-time analog |
| `continuation_or_challenge` | "…would be most **challenged/continued** by…" | R3 | a later break/extension |
| `differs_from` | "…**differs** from … most significantly in that…" | R1 | the axis of difference |

### 4c. The distractor architecture (the four traps) — *the heart of "expert vs LLM"*

This is the most important section for the whole project. Prep analysis of
released exams finds that **APUSH wrong answers are usually historically true;
they just don't answer the question.** [missed-mcq] College Board builds
distractors with exactly **four architectures**, and an expert item's every
distractor is one of them, each tied to a *nameable* student error:

| Trap | Rule | Why a good student falls for it | Verifiable? |
| :--- | :--- | :--- | :--- |
| **Wrong era** | a real development from a *different* time period | recognizes the term, ignores chronology | **Yes — date-checkable** |
| **True but irrelevant** | accurate for the era but answers a *different* question (wrong theme/mechanism) | endorses a familiar true statement without checking it fits the stem | judge (theme/skill mismatch) |
| **Scope mismatch** | too broad (general background when the stem says "most directly") or too narrow (one example when it asks for a trend) | matches topic but not the *scale/directness* the phrase demands | judge (granularity) |
| **Partially true** | one clause accurate, one fabricated/overstated (often "…and…"/"…while…"), or right direction / wrong magnitude | agrees with the true half, misses the false half | judge (clause-level) |

**This directly answers the user's complaint.** The user's objection — "LLM
questions have very obvious wrong answers and are too on-the-nose" — is precisely
a failure to build distractors from this menu. An LLM left to itself writes
distractors that are *absurd, off-topic, or anachronistically obvious*; an expert
writes three distractors that are each *true, era-plausible, and wrong for a
specific, nameable reason.* Encoding this menu as a hard generation constraint
(every distractor must be labeled with its trap id) is the core of the whole
approach.

> **The "most directly" trap, specifically.** When a stem says "most directly,"
> two options may both be causally linked; the right one is the *specific
> mechanism*, the wrong one is the *broad background condition*. Example from
> released-style analysis: for "what most directly caused 1920s immigration
> restriction," *WWI-era nativism* (background) loses to *the Emergency Quota Act
> of 1921* (the legislative mechanism). [missed-mcq] Getting this right is a
> **reasoning skill, not a fact lookup** — which is exactly why it is winnable
> for a grounded small model.

---

## 5. The five families (top-level grouping)

Collapsing the skill spine into generation-friendly buckets gives **five
families**. Every archetype in Section 6 belongs to exactly one. This is the
grouping the SLM's scope decision hangs on (Deliverable 3).

| Family | Skills | Volume | "Expert feel" | What it demands of the source |
| :--- | :--- | :--- | :--- | :--- |
| **F1 · Comprehension & Sourcing** | P1, P2 | High | Low–Med | any readable source |
| **F2 · Contextualization** | P4 | Med | Med–High | a source with a clear situation/antecedent |
| **F3 · Causation** | R2 | High | High | a development with an identifiable cause/effect |
| **F4 · Continuity, Change & Comparison** | R3, R1 | Med | High | a development that recurs / changes across time |
| **F5 · Argument & Evidence** | P3 (+R1) | Med (mostly secondary sources) | **Highest** | a source that makes an *argument* |

The user's two motivating examples map cleanly:

- *"Describe environments/situations and ask you to conclude from general historic
  trends"* → **F3 (Causation)** and **F4 (Comparative analog / CCOT)** — connect
  the described situation to a broader trend or a cross-time parallel.
- *"Definitions with close-by answers"* → **F1 (`DEVELOPMENT_ILLUSTRATED`)** with
  **true-but-irrelevant / scope-mismatch** distractors — discriminate the right
  labeled development from its near neighbors.

F5 is the APUSH crown jewel and the closest analog to the MCAT project's
`THEORY_PLUS_STUDY`: it evaluates an **argument** against **evidence**, with a
closed relational menu (*supports / undermines / consistent-but-not-diagnostic /
axis-of-difference*).

---

## 6. The archetype catalog (the generation-ready unit)

Twelve archetypes, mirrored exactly in the JSON companion. Each field: `family`,
`skill`, `stem_template`, `input_needed`, `shape`, `good_example` (an authentic
CED item, cited, used for *analysis only*), `llm_failure` (the tell), and
`difficulty_levers`. Below is the human-readable summary; the JSON has the full
`good_example` with per-distractor trap labels.

### F1 — Comprehension & Sourcing

- **`DEVELOPMENT_ILLUSTRATED`** (P1, "best illustrates"). Give a source; ask which
  broader development it exemplifies. *Ex (CED Q5):* Larson on the Erie Canal →
  **"the expansion of access to markets."** Distractors: Native-American commerce
  (true-but-irrelevant), internal slave trade (true-but-irrelevant), semisubsistence
  agriculture (partially-true/opposite). *LLM tell:* the "development" merely
  paraphrases the source.
- **`SOURCE_POV_PURPOSE`** (P2, "intended to"). Ask the author's purpose/audience.
  *Ex (CED Q12):* 1940s women-in-industry poster → **"the movement of women into
  jobs traditionally held by men."** *LLM tell:* purpose stated in the caption.

### F2 — Contextualization

- **`CONTEXT_SITUATION`** (P4, "in response to"). Ask what prompted the source.
  *Ex (CED Q15):* Ford's 1974 oath remarks → **Watergate.** Distractors are other
  same-era crises (true-but-irrelevant) or wrong-era events. *Date-verifiable.*
- **`CONTEXT_INFLUENCED_BY`** (P4, "influenced by"). Ask the antecedent
  idea/movement. *Ex (CED Q9):* 1860 Republican platform → **free-soil movement.**
  *Date-verifiable.*

### F3 — Causation *(high expert feel)*

- **`CAUSE_OF_SOURCE`** (R2, "contributed most directly to"). *Crown jewel.* Ask
  the most-direct cause. *Ex (CED Q1):* Declaratory Act 1766 → **debates over
  paying for the Seven Years' War.** The signature trap is *broad background vs
  direct mechanism* (scope mismatch). *Date-verifiable* (cause predates source).
- **`EFFECT_OF_SOURCE`** (R2, "most immediately led to"). *Crown jewel.* Ask the
  short-term effect. *Ex (CED Q2):* Declaratory Act → **Parliament intensifying
  colonial tax measures.** Includes a reversed-direction (partially-true) distractor.
  *Date-verifiable* (effect postdates source).

### F4 — Continuity, Change & Comparison *(high expert feel)*

- **`LONGTERM_LEGACY`** (R2→R3, "later characteristic"). Ask the durable legacy.
  *Ex (CED Q4):* debates over parliamentary authority → **reservation of powers to
  the states (federalism).**
- **`COMPARATIVE_ANALOG`** (R1, "most similar effect"). *Crown jewel.* Ask which
  *later* development had a similar effect. *Ex (CED Q7):* Erie Canal → **the
  first transcontinental railroad.** *LLM tell:* matches on surface topic, not on
  the shared mechanism.
- **`CONTINUITY_OR_CHANGE`** (R3, "would be most challenged by"). Ask the later
  break/extension of a pattern. *Ex (CED Q14):* 1940s women workers → **1950s
  domestic-conformity culture.** *LLM tell:* confuses "continues" with "challenges."

### F5 — Argument & Evidence *(highest expert feel; secondary-source engine)*

- **`EVIDENCE_SUPPORTS_CLAIM`** (P3, "support the argument"). *Crown jewel.* Ask
  which outside development strengthens the source's *specific* claim. *Ex (CED
  Q6):* Larson's interregional-rivalry claim → **opposition to federal funding of
  public works.** *LLM tell:* offers any era-appropriate fact as "support" without
  testing that it strengthens *this* claim.
- **`EVIDENCE_UNDERMINES_CLAIM`** (P3, "challenge the argument"). *Crown jewel.*
  The hardest single item type: distinguishing a fact that *weakens* a claim from
  one that *confirms* it. *LLM tell:* offers a confirming fact as the "challenge."
- **`COMPETING_INTERPRETATIONS`** (R1, two historians, "differ most significantly
  over"). Ask the true axis of disagreement between two secondary sources.
  *Ex:* Peiss (cultural/consumer) vs Enstad (political) on working women. *LLM
  tell:* names a point they actually agree on, or invents a non-difference.

### Format overlays (modifiers, not archetypes)

`IMAGE_STIMULUS`, `CHART_STIMULUS`, `SET_OF_THREE`, `SECONDARY_SOURCE` — an agent
selects an archetype, then optionally applies one overlay (see JSON `overlays`).

---

## 7. What separates an *expert* APUSH question from an *LLM* question

This is the **quality rubric** — simultaneously the data-gen filter and the eval
criterion. An item is "expert-grade" only if it clears **all** of these;
LLM-default items typically fail 3+. (Encoded as JSON `quality_checks`.)

1. **Stimulus-based and grounded.** Every item hangs on a source and is *not*
   answerable as free-floating trivia. *(disqualifying)*
2. **Requires outside knowledge.** The answer requires connecting the source to a
   development **not stated in the source** — the APUSH "familiar concept,
   unfamiliar scenario." A paraphrase-of-the-source item is disqualified. This is
   the exact thing LLMs get wrong: they "ask the source back to itself."
   *(disqualifying)*
3. **Every distractor encodes a named trap.** Each of the three wrong options maps
   to exactly one of {wrong-era, true-but-irrelevant, scope-mismatch,
   partially-true} and that label is defensible. *This is the #1 differentiator
   and the direct fix for the user's "obvious wrong answers" complaint.*
   *(disqualifying)*
4. **Distractors are period-plausible.** Each is a real, era-appropriate
   development a good-but-imperfect student would consider — never absurd or
   off-topic filler. *(disqualifying)*
5. **The skill matches the command phrase.** A causation stem is answered by a
   cause; a "support" stem by a strengthener. Reject answers that are merely
   "related and true." *(disqualifying)*
6. **Answer key is anachronism-consistent.** Where the archetype is
   date-verifiable, the keyed answer's date obeys the stem's time direction
   (cause before, effect after), and a wrong-era distractor *violates* it. This is
   **programmatically checkable** against the developments table — the APUSH analog
   of the MCAT project's deterministic "truth-table" verifier, and a major
   feasibility lever. *(disqualifying)*
7. **Single best answer**, homogeneous options, no "all/none of the above," no
   absolute-word tells ("always/never"), correct answer not the longest.

> These checks are directly encodable as an LLM-as-judge rubric plus programmatic
> checks (option homogeneity, absolute-word regex, and — crucially — a
> date-consistency check against the developments table). They are the bridge from
> this research to the eval harness the spec demands *before* training.

---

## 8. Agent-iteration interface

The machine-readable catalog lives in
[`taxonomy/apush_question_archetypes.json`](../taxonomy/apush_question_archetypes.json).
Its generation loop:

```
1. pick a STIMULUS (legally-sourced text / described image / described chart),
   tagged period + theme + date            (data/seed_stimuli.jsonl)
2. pick an ARCHETYPE the stimulus supports  (weighted by Deliverable-3 scope)
3. instantiate its STEM_TEMPLATE (fill the command phrase)
4. derive the ANSWER = (source claim) + (one outside development from the
   date-tagged developments table, consistent with the stem's time direction)
5. author 3 DISTRACTORS, each from the closed trap menu, spanning >=2 trap types;
   label each with its trap id + named error
6. self-filter against quality_checks (drop on any disqualifying failure);
   run the anachronism date-check where applicable
7. optionally apply SET_OF_THREE for a full 3-item stimulus set
8. log (stimulus_id, archetype, period, theme, trap_types) for coverage
```

---

### TL;DR for the next stages

- APUSH's real MCQ "type" system is **(6 practices + 3 reasoning processes) ×
  (9 periods × 8 themes) × (5 stimulus types) × (a closed menu of ~14 command
  phrases).** Every MCQ is **stimulus-based**.
- We distilled that into **5 families → 12 generation-ready archetypes**, with
  "expert feel" concentrated in **F3/F4/F5** (causation, comparison/CCOT, and
  argument–evidence).
- The **decisive generation lever is the closed distractor menu** (wrong-era,
  true-but-irrelevant, scope-mismatch, partially-true). Encoding it as a hard
  constraint is the direct fix for "LLM questions have obvious wrong answers."
- The **feasibility crux is factual answer-key correctness** (history is
  fact-dense). It is neutralized by (a) *providing* the source rather than
  inventing it, and (b) a **programmatic anachronism date-check** — the APUSH
  analog of a deterministic verifier. Deliverable 3 quantifies this.
