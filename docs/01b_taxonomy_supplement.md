# MCAT Taxonomy Supplement — Additive Research

> **Companion to** [`01_mcat_question_taxonomy.md`](01_mcat_question_taxonomy.md) and
> [`taxonomy/mcat_question_archetypes.json`](../taxonomy/mcat_question_archetypes.json).
> Patterns found in supplementary AAMC/prep research that are **not yet** standalone
> archetypes in the JSON catalog. v1 SLM scope intentionally uses only two archetypes;
> this file preserves the full map for v2+ and agent iteration.

---

## Science archetypes not yet in JSON

### SIRS-1 (Knowledge)

- **Conceptual contrast** — similarities/differences between two frameworks (e.g. operant vs classical conditioning); distractors swap direction or attribute features across frameworks.
- **Stage/classification slot** — assign a case to Piaget stage, extinction type, etc.; neighbors are adjacent stages.

### SIRS-2 (Applied reasoning)

- **Sequence / symbolic application** — apply a rule to a novel string (start codon → count amino acids before stop); between recall and full quantitative application.
- **Theory selection from model** — which sociological/psych theory best fits a diagram or campaign; rival-theory distractors.
- **Causal-argument evaluation** — is a causal explanation licensed? Traps: correlation-as-causation, ignored third variables.
- **Structural prediction (chem/bio)** — what bond/interaction forms if two structures were adjacent? Distinct from mechanism perturbation (no upstream/downstream chain).

### SIRS-3 (Research & experiment)

- **Technique-mechanism** — why SDS-PAGE separates by MW (charge/shape normalized); design logic, not IV/DV labeling.
- **Research ethics violation** — identify breach of participant rights/safety/privacy (explicit AAMC Skill 3 bullet; **gap in current JSON**).
- **Sampling & generalizability** — given recruitment method, judge external validity.
- **Measure reliability/validity** — appropriateness of self-report vs behavioral measures.
- **Third-variable / confound in correlational design** — name the confound explaining an association.
- **Association vs causation design cues** — temporality, random assignment, controls.
- **Method-type identification** — survey vs ethnographic vs experimental.

### SIRS-4 (Data & statistics)

- **Table-pattern → inference** — titration pKa table → which amino acid / side chain; ignore irrelevant columns.
- **Central tendency choice** — median vs mean under skew (distinct from correlation framing).
- **Random vs systematic error** — which error type explains a discrepancy.
- **Claims licensed by study design** — longitudinal vs cross-sectional vs experimental.
- **Alternative explanation for same data** — different mechanism, not “no conclusion.”
- **Over-claim / beyond-the-evidence** — inverse of `DATA_TO_CONCLUSION`; pairs with uncertainty calibration.

### Figure families (feed F3/F4)

Recurring AAMC objects: dose–response, time-course, bar + error bars, kinetics/transport curves. Stem patterns: missing control, best additional experiment, saturation/EC50/Km shift.

---

## CARS subtypes (out of primary SLM scope)

AAMC CARS skill weights (30/30/40) match our JSON. Missing **named subtypes**:

**Foundations (30%)**

- Author tone / attitude / bias
- Passage structure (cause-effect vs chronology vs point-counterpoint)
- Rhetorical function (local phrase / transition)

**Reasoning within the text (30%)**

- Thesis scope traps (too narrow, too broad, reversed stance)
- Paradox / inconsistency across sections
- Perspective attribution (author vs quoted views)
- Argument evaluation (claims, evidence, faulty causality)

**Reasoning beyond the text (40%)**

AAMC splits **Apply/Extrapolate** and **Incorporation** (not one bucket):

- Apply / extrapolate — extend passage logic to novel scenario
- Analogy mapping — shared underlying relationship
- Incorporation support/contradict — new info supports, contradicts, or coexists
- Incorporation least disruption — which new fact least alters the thesis
- Author agreement — “author would most likely agree / find troubling”

---

## Surface overlays to add (future JSON v2)

| Overlay | Rule |
| :--- | :--- |
| `BEST_ANSWER` | “Most likely / best supported”; >1 partially true option |
| `LEAST_SUPPORTED` | Negative framing when all options are plausible |
| `PASSAGE_BOUND` | CARS: answer must cite passage-only support |
| `DISCRETE_STEM` | Standalone item (~25% of science section); no passage |

---

## AAMC vs generic MCQ (generation heuristics)

Already encoded in taxonomy §7; additional AAMC-specific markers:

- Passage-integrated novelty — answer not recallable without the passage/data object
- Partial-truth traps — three competitive wrong answers, not one silly option
- Experimental subtlety — confounds need domain mechanism (not “increase sample size”)
- Scope-calibrated correctness — “consistent but not diagnostic” often *correct*

---

## Corrections vs authoritative AAMC

| Existing | Issue | Fix |
| :--- | :--- | :--- |
| F1 label “Knowledge & Discrimination” | AAMC: “Knowledge of Scientific Concepts and Principles” | Naming only |
| SIRS-3 family | Ethics is an explicit Skill 3 bullet | Add `RESEARCH_ETHICS` archetype in v2 |
| CARS Beyond-the-Text subtypes | Collapsed into strengthen/weaken + apply | Split Apply vs Incorporation per AAMC PDF |
| Concept count in docs | Stated “60” in places | **`speedrun_concepts.json` has 56** |

Sources: [AAMC SIRS PDF](https://students-residents.aamc.org/media/9061/download), [AAMC CARS PDF](https://students-residents.aamc.org/media/9271/download).
