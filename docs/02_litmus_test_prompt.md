# Litmus Test — Protocol, Scoring & Decision (Deliverable 2)

> **The one question this answers:** *Should this SLM be built at all?*
>
> Per the project spec, fine-tuning is justified **only if a well-prompted base
> model can't already do the behavior reliably.** So we take the strongest
> reasonable prompt
> ([`prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md))
> and measure how reliably models produce **expert-grade APUSH stimulus-based
> MCQs** from a provided source + note. The result routes us to one of three
> doors: **BUILD**, **DON'T BUILD**, or **RETHINK**.

---

## 1. What "reliably" and "expert-grade" mean here

- **Expert-grade** = an item passes **all disqualifying quality checks** from the
  taxonomy (§7 of [`01_apush_question_taxonomy.md`](01_apush_question_taxonomy.md)
  / JSON `quality_checks`): stimulus-grounded, requires-outside-knowledge,
  every-distractor-a-named-trap, distractors-period-plausible,
  skill-matches-command-phrase, anachronism-consistent key, single-best-answer.
  These are booleans; an item either clears the bar or it doesn't.
- **Reliably** = expert-grade **≥ 80% of the time**, across varied sources and
  archetypes, *and* stable across repeated runs (low variance). Reliability, not
  peak quality, is the whole point — a prompt can get lucky once; a trained model
  must do it every time.

This mirrors the spec's eval rubric (Spec adherence, Robustness, Task quality,
Consistency), specialized to APUSH question-writing.

---

## 2. The instrument

`prompts/litmus_generation_prompt.md` — a maximal prompt encoding the full
behavior spec, the closed stem menu, the **closed 4-trap distractor menu**, all
archetype→stem mappings, and two gold few-shot exemplars, with strict JSON output
so grading is automatic. It is intentionally the *best* prompt we can write,
because the litmus is a **ceiling test**: "even when told exactly how, can the
model do it?"

---

## 3. Fixed test inputs (held constant across all models)

Because APUSH MCQs are stimulus-based, each input is a **(source, attribution,
note)** triple, drawn from the legally-sourced seed corpus
([`data/seed_stimuli.jsonl`](../data/seed_stimuli.jsonl); provenance in
[`05_data_sourcing_and_legal.md`](05_data_sourcing_and_legal.md)). Draw **15
sources** so results are comparable and representative:

- **10 primary-source excerpts** — one per core period (3–8) plus 4 spread across
  the remaining periods, covering ≥6 of the 8 themes (public-domain speeches,
  laws, platforms, letters, court opinions).
- **3 secondary-source (historian) arguments** — to exercise the crown-jewel F5
  archetypes (`EVIDENCE_SUPPORTS/UNDERMINES_CLAIM`, `COMPETING_INTERPRETATIONS`);
  synthetic or public-domain historiographical excerpts.
- **2 adversarial inputs** — a terse bullet-note with a source fragment, and a
  multi-development source (probe robustness / single-target selection).

For each source, request **6 items** cycling the in-scope archetypes at
operational difficulty. Total = **90 items per model per run**; do **3 runs** per
model (temperature ≈ 0.7, different seeds) to measure consistency → **270
items/model**.

> The exact source list and a runnable harness stub belong to Day-2 of the build
> (the spec wants the eval built before training). This doc specifies *what* to
> run and *how to decide*; the harness is scaffolded in the training plan
> (Deliverable 4 → [`planning/plan_v2.md`](planning/plan_v2.md)).

**Firewall:** the 15 litmus sources are frozen in `data/splits.json` and are
**disjoint** from all training seeds (no source is used both to litmus and to
generate training data).

---

## 4. Scoring

### 4a. Programmatic gates (cheap, run first)

- valid JSON; 4 options; exactly one answer key; required fields present
- regex reject `all of the above|none of the above|always|never`
- option-length homogeneity (correct answer not the longest by > X%)
- answer-key position balanced across a run (detects "always C" collapse)
- **anachronism date-check** — for date-verifiable archetypes, confirm the keyed
  development's date obeys the stem's time direction (cause < source < effect),
  checked against [`data/apush_key_developments.json`](../data/apush_key_developments.json).
  This is the APUSH analog of the MCAT project's deterministic verifier and is the
  cheapest strong signal.
- concept/source-leak check: the answer phrase is not a verbatim span of the source

### 4b. LLM-as-judge (a strong frontier model, NOT a model under test)

Per item, score each **disqualifying** check pass/fail, plus three graded
dimensions on **0 / 1 / 2** (from the spec's rubric):

| Dimension | 0 | 1 | 2 |
| :--- | :--- | :--- | :--- |
| **Spec adherence** | violates ≥1 disqualifying check | minor wobble | fully expert-grade |
| **Distractor craft** | ≥1 filler/absurd option | mixed | every distractor a named, era-plausible trap |
| **Outside-knowledge / skill-fit** | asks the source back to itself OR answer mismatches the command phrase | partial | genuinely requires outside knowledge AND matches the skill |

- **`expert_grade(item)`** = all disqualifying checks pass **and** every graded
  dimension ≥ 1 **and** Spec adherence = 2.
- **Historical-accuracy sub-check (critical for a fact-dense domain):** the judge
  must flag any item whose **keyed answer is historically wrong** or whose keyed
  answer is **not uniquely best** (a distractor is also defensibly correct). This
  is the APUSH crux (SC-key in Deliverable 3) and is reported separately as
  `key_valid_rate`.
- Judge reliability: 20% of items get a second independent judge pass; report
  agreement. A random ≥30-item slice is **human-spot-checked** for historical
  accuracy (LLM judges themselves err on history facts).

### 4c. Metrics per model

- **Pass rate** = fraction `expert_grade` (primary metric).
- **`key_valid_rate`** = fraction with a historically-correct, uniquely-best key
  (the reliability crux).
- **Mean rubric** per dimension; **Consistency** = std of pass rate across 3 runs.
- **Archetype breakdown** = pass rate per archetype (reveals the real bottleneck —
  expected: F1 easy, F5 hardest).

---

## 5. Models to run (the comparison that makes the decision)

| Tier | Model(s) | Role |
| :--- | :--- | :--- |
| **SLM candidates** | Qwen3-0.6B / 1.7B / 4B **Instruct** (optionally Llama-3.2-1B/3B) | the would-be base — what an SLM must beat |
| **Frontier ceiling** | a top frontier model (GPT/Claude class) | the distillation *teacher*; establishes whether the behavior is achievable at all |

Run the **identical** prompt + inputs through both tiers, with and without the
few-shot block.

---

## 6. Decision matrix

Let `S_small` = best small-candidate pass rate, `S_frontier` = frontier pass rate,
and `K` = the frontier's `key_valid_rate`.

| Condition | Door | Reasoning |
| :--- | :--- | :--- |
| `S_small ≥ 80%` (reliable) | **DON'T BUILD** | a prompt already does it — the spec's litmus fails; ship a prompt, not a fine-tune. |
| `S_frontier ≥ 70%` **and** `S_small ≤ 45%` | **BUILD (distill)** | the behavior is achievable (teacher exists) but small models can't reach it by prompting — the exact gap SFT/QLoRA closes. Target regime. |
| `45% < S_small < 80%` | **BUILD (narrow first)** | promising but shaky; scope to the highest-gap archetypes and distill. |
| `S_frontier < 50%` **or** `K < 70%` even with few-shot | **RETHINK** | if the *teacher* can't do it reliably, or can't key answers correctly, we have no clean labels to distill; reframe (provide richer sources, narrow archetypes, or change the output unit — e.g., "repair/grade an item" instead of "generate from scratch"). |

**Expected prior (to be confirmed by the run, not assumed):** F1
(`DEVELOPMENT_ILLUSTRATED`, comprehension) likely falls in the DON'T-BUILD zone
even for small models; the F3/F4/F5 reasoning archetypes (causation, comparative
analog, argument-evidence) likely fall in the BUILD zone (frontier can, small
can't). The **`key_valid_rate` gap** — whether small models fabricate or
double-key answers where the frontier does not — is expected to be the decisive
signal, because history is fact-dense. This gap profile is the direct input to the
feasibility agent (Deliverable 3).

---

## 7. A note on why the run is non-skippable

Two things are unknown until the run:

1. **Can the frontier teacher key APUSH items correctly and uniquely?** History
   MCQs fail in a way physics MCQs don't: a distractor can be *also* defensible, or
   the "most directly" judgment can be contestable. If `K` is low, distillation
   has no clean labels — this is the single most decision-relevant number.
2. **How far below the teacher is the prompted 0.6–4B model, per archetype?** The
   size cliff (0.6B → 4B) and the archetype-level gap profile determine the scope
   and size picks in Deliverable 3.

Do **not** start training on the strength of the priors alone.

---

## 8. Output of this stage

A results table (`docs/02b_litmus_results.md`, produced when the harness runs)
with pass rate and `key_valid_rate` by model × archetype, the door selected, and
the archetype-level gap profile. That profile feeds the **feasibility agent**
(Deliverable 3 → [`03_feasibility_assessment.md`](03_feasibility_assessment.md)),
which converts "there is a gap" into "here is the exact scope an SLM can win, at
>90% confidence."
