# SLM Feasibility Assessment — Deliverable 3

> **The one question this answers:** *Can a fine-tuned SMALL model (0.6B–4B, QLoRA
> SFT + teacher distillation) RELIABLY turn study notes into expert-grade MCAT
> questions — and at what SCOPE?* This stage does not run the model; it converts
> the taxonomy (Deliverable 1) and the litmus design (Deliverable 2) into a
> calibrated **go / narrow / rethink** decision with an explicit confidence and
> kill-criteria. It is deliberately skeptical: per the spec, the win is
> **reliability of a constrained behavior**, not raw capability.

---

## 0. Executive verdict

```
┌────────────────────────────────────────────────────────────────────────────┐
│  VERDICT:            BUILD — but NARROW HARD                                  │
│                                                                              │
│  RECOMMENDED SIZE:   Qwen3-4B-Instruct (QLoRA SFT + frontier distillation)   │
│                      → 0.6B is disqualified for a reliability-first spec;     │
│                        1.7B is a fallback, not the pick.                      │
│                                                                              │
│  RECOMMENDED SCOPE:  TWO structurally-determined archetypes —                │
│                      1. MECHANISM_PERTURBATION   (anchor / fallback)         │
│                      2. THEORY_PLUS_STUDY        (highest expert value)      │
│                      Everything else: OUT of v1 scope (see §4).              │
│                                                                              │
│  CONFIDENCE:         92%  that tuned Qwen3-4B reliably beats its OWN          │
│                      prompted base at expert-grade items on this scope,       │
│                      CONDITIONAL on the §5 preconditions (esp. a             │
│                      verification pass). Drop THEORY_PLUS_STUDY and the       │
│                      confidence on MECHANISM_PERTURBATION alone is ~93%.      │
│                      At 1.7B: ~82%. At 0.6B: ~60% (do NOT greenlight).       │
│                                                                              │
│  BIGGEST RISK:       Single-best-answer factual correctness — a keyed        │
│                      answer that is wrong, or a *second* option that is       │
│                      also defensible. This is why a verifier is a            │
│                      precondition, not a nice-to-have.                        │
└────────────────────────────────────────────────────────────────────────────┘
```

**One-sentence thesis.** Feasibility is governed almost entirely by
**regularity**: archetypes whose *scenario slot* and *distractor set* are
**structurally determined** (a closed, named menu) convert the three hardest
sub-capabilities — novel-scenario construction, distractor authoring, and
answer-key correctness — from open-ended *generation* (an SLM weakness) into
*templated selection + rule-derivation* (an SLM strength). The two crown-jewel
structural archetypes are therefore, counter-intuitively, **more** SLM-feasible
than the free-form ones — including the user's own example #1
(`CLINICAL_VIGNETTE_TO_DIAGNOSIS`), which this assessment argues *against* for v1.

---

## 1. What "success" means here (precise reframe of "outperform")

The spec is explicit: *"Your 1B model will not beat a frontier model on raw
capability… The defensible win is reliable, constrained behavior."* So we grade
against two bars, only the first of which is required:

| Bar | Definition | Required? | Verdict |
| :--- | :--- | :--- | :--- |
| **Primary — base-vs-tuned** | Tuned SLM produces `expert_grade` items (all §7 disqualifying checks pass) at a **higher pass rate and lower run-to-run variance** than the *same model prompted with the maximal litmus prompt*. | **YES** (the spec's midweek gate) | **Achievable with high confidence** on the narrow scope. |
| **Secondary — rival frontier** | Tuned SLM matches a *prompted frontier* model's pass rate on the one archetype. | No | **Plausible but not guaranteed**; do not stake the project on it. |

Why the primary bar is winnable. The base SLM, even with the *best* prompt, is
documented to drift in exactly the ways the §7 checks forbid: it breaks strict
JSON under load (Qwen3-0.6B hits **1.4%** format compliance in direct-answer
mode vs 85.8% in its preferred mode [arith-2025]), it "asks the note back to
itself" (fails familiar-concept/unfamiliar-scenario), it writes filler
distractors, and it fabricates plausible-but-wrong answer keys (hallucination is
~1/5 of SLM failures [slm-review]). SFT on a tight, filtered distribution is the
canonical fix for precisely this class of *reliability* gap — the same regime
where LoRA-Land fine-tunes beat their base by **+34 points** average and beat
GPT-4 on narrowly-scoped tasks [loraland], and where structured-blueprint
distillation adds **+8.1** over unstructured CoT distillation for SLMs
[struct-sql] and contrastive fallacy-labeled negatives add **+12.5%** on Phi-2
[ccot]. The base→tuned delta is the easy part; the crux is the *absolute*
quality bar (§3, SC5).

---

## 2. Sub-capability decomposition and per-size feasibility

The task `f(note) → expert MCQ` breaks into six load-bearing sub-capabilities
(plus one archetype-specific one). Scores are **post-QLoRA-SFT + distillation**
feasibility on a 0–1 scale (0 = will not do it reliably; 1 = reliable), matching
the repo's `expert_feel`/`note_seedability` convention. Scores are for the
**recommended narrow scope**; free-form scope is strictly lower where noted.

| # | Sub-capability | 0.6B | 1.7B | 4B | Bottleneck? | Basis |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| SC1 | **Concept extraction** from the note (identify the testable principle) | 0.75 | 0.85 | 0.92 | No | Notes are principle cards that *hand over* the concept; near-read-off. Weakest on messy/multi-concept inputs. |
| SC2 | **Novel scenario construction** (familiar concept → unfamiliar context) | 0.35 / 0.60\* | 0.55 / 0.75\* | 0.70 / 0.88\* | **Yes (free-form)** | Open-ended creativity is an SLM weak point; but a *templated* archetype slot (perturbation type; follow-up-finding schema) is recombination, not invention. \*second number = structurally-determined archetypes. |
| SC3 | **Distractor construction** (each wrong option = a named error) | 0.25 / 0.65\* | 0.45 / 0.82\* | 0.60 / 0.90\* | **Yes (free-form); No (structured)** | The #1 expert differentiator. Free-form = invent misconceptions (hard). Structured = *select from a closed named set* (competitive/uncompetitive/…; supports/weakens/not-diagnostic) → a **classification** sub-task, the SLM sweet spot [loraland, struct-sql]. |
| SC4 | **Strict structured output** (valid JSON schema + rationale block) | 0.80 | 0.90 | 0.96 | No (minor 0.6B risk) | Canonical fine-tuning win (spec's own "structured-output" example). 0.6B retains format fragility under long/nested schemas [arith-2025]. |
| SC5 | **Single-best-answer factual correctness** (key right; no 2nd-correct) | 0.30 / 0.60\* | 0.45 / 0.72\* | 0.55 / 0.82\* | **YES — TRUE CRUX** | Leans on recall (SLM weak: hallucination [slm-review]). Safe *only* when correctness is **rule-derivable** from the item's own structure, not looked up. Needs a verifier to reach the bar (§5). |
| SC6 | **Cross-input reliability / low variance** | 0.45 | 0.65 | 0.80 | Partial | SFT on a narrow distribution sharpens consistency — the whole point of the project. Improves monotonically as scope narrows → argues for 1–2 archetypes. |
| SC7 | **Quantitative / arithmetic correctness** (`QUANTITATIVE_APPLICATION` only) | 0.15 | 0.35 | 0.55 | **Yes → exclude** | Multi-digit/multi-step arithmetic collapses below 4B and is imperfect even at 4B; GSM-Symbolic-style perturbations break it [easymath, arith-2025]. Exclude the archetype or supply numbers pre-computed. |

\* `a / b` = free-form archetypes / structurally-determined archetypes.

**True bottleneck(s).** In priority order: **SC5 (answer-key correctness)** is
the single gating capability, followed by **SC3 and SC2 for free-form
archetypes**, and **SC7 for anything quantitative**. The decisive move is that
the *right scope* neutralizes SC2/SC3 (templating) and de-risks SC5 (rule-
derivable correctness) — leaving a residual SC5 tail that a cheap verification
pass mops up. SC4/SC1/SC6 are not bottlenecks at 4B.

**The size cliff (why 4B, not 0.6/1.7B).** The most model-specific evidence we
have is on the exact Qwen3 family the spec recommends: Qwen3-0.6B shows
**catastrophic** instruction/format collapse (1.4% in one mode), while
**Qwen3-4B is robust (96%+) across modes, and 4B≈8B** (0.5-pt gap — diminishing
returns beyond 4B) [arith-2025]. There is a documented **reliability threshold
between 0.6B and 4B**. For a spec whose entire deliverable is *reliability*,
paying the modest VRAM cost for 4B is the highest-leverage single decision.
(Caveat weighed honestly: LoRA-Land's headline wins are **7B** models on
**classification**, not ≤4B generative quality — so we lean on the Qwen3-specific
and distillation-specific evidence for the size and generative-quality claims,
and treat LoRA-Land as directional support for "narrow + tuned wins," not proof.)

---

## 3. Scope decision — the central question

Each archetype is scored on the four criteria the task specifies:
**(a) regularity** of shape + distractor logic (regular = learnable at small
scale), **(b) factual/computational load** (lower = safer), **(c)
`note_seedability`**, **(d) `expert_feel`**. "SLM-fit" is the resulting v1
recommendation.

| Archetype | Family | Regularity | Fact/compute load | Seedability | Expert feel | SLM-fit (v1) |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **MECHANISM_PERTURBATION** | F2 | **Very high** (closed inhibition/mutation menu; fixed Km/Vmax signatures) | Low (qualitative) | 0.90 (best-seeded: enzyme-reg gold, LDH-R family) | 0.85 | **IN — anchor** |
| **THEORY_PLUS_STUDY** | F4/2 | **Very high** (closed evidential set: supports / weakens / not-diagnostic / contradicts-other) | Low–med | 0.85 | **1.00** | **IN — high value** |
| DATA_TO_CONCLUSION | F4 | High (misreading menu: sign-flip, over-generalize, independence) | Med (must render a coherent data object in text) | 0.70 | 0.90 | Tier-2 (v2 candidate) |
| EXPERIMENTAL_FIX_OR_FLAW | F3 | Med–high (fix/worsen/irrelevant menu) | **Med–high** (must *know* the real confound & real fix) | 0.70 | 0.95 | Tier-2 (knowledge-dependent; taxonomy crown-jewel but riskier for SLM) |
| STATISTICAL_INFERENCE | F4 | High (named stat-misconception set) | Med (stat reasoning) | 0.60 | 0.80 | Tier-2 |
| PRINCIPLE_TO_PREDICTION | F2 | Med (competing-theory distractors) | Med (hold ≥2 theories correctly) | 0.80 | 0.65 | Tier-3 |
| IDENTIFY_VARIABLES | F3 | High | Low | 0.70 | 0.85 | Tier-3 — likely **DON'T-BUILD** (base may already pass) |
| DESIGN_THE_TEST | F3 | Med–low (open design space) | Med | 0.75 | 0.85 | Tier-3 |
| CONCEPT_DISCRIMINATION | F1 | High | Low | 0.90 | 0.50 | **DON'T-BUILD** (prompt likely suffices) |
| REPRESENTATION_TRANSLATION | F1 | Med | Low | 0.60 | 0.40 | OUT (needs real graphs) |
| QUANTITATIVE_APPLICATION | F2 | Med | **High (arithmetic)** | 0.75 | 0.70 | **OUT** (SC7 bottleneck) |
| CLINICAL_VIGNETTE_TO_DIAGNOSIS | F2 | **Low** (open scenario; differentials must be real & feature-sharing) | **Very high (clinical facts)** | 0.85 | 0.85 | **OUT of v1** (user example #1 — see box) |

> **Skeptic's flag — the user's own example #1 is a trap for an SLM.**
> `CLINICAL_VIGNETTE_TO_DIAGNOSIS` scores high on expert-feel *and* seedability,
> which makes it tempting. But its correct answer is a **fact** (the real
> diagnosis), its distractors must be **real differentials that share features**,
> and the craft is *withholding the giveaway* — i.e. it maximally loads SC5
> (factual correctness) and SC2/SC3 (open scenario + real-world distractors), the
> three SLM weak points, with no structural rail to fall back on. This is where a
> sub-4B model will confidently emit a wrong or double-keyed answer. Include it
> only later, and only with **retrieval grounding**. Naming it out of v1 is the
> clearest signal that this assessment is not rubber-stamping.

### 3a. Why the structurally-determined pair is *more* feasible (the core argument)

The user's criterion asks whether structural determinacy makes the crown jewels
**more** feasible than free-form archetypes. It does, decisively, and here is the
mechanism:

- **MECHANISM_PERTURBATION** distractors are a **closed set of inhibition
  modes**, each with a *deterministic* Km/Vmax (or qualitative) fingerprint:
  competitive (Km↑, Vmax=), uncompetitive (Km↓, Vmax↓), noncompetitive (Km=,
  Vmax↓), allosteric activation (Vmax↑), dissociation (ruled out by %-tetramer).
  The model does not *invent* distractors or *recall* an answer — it **maps a
  given fingerprint to a label** (classification) and reads the other labels off
  the same table as distractors, each with its rationale pre-implied by the menu.
  Our LDH-R gold item is exactly this shape and a *single passage yields a whole
  family* of such items.
- **THEORY_PLUS_STUDY** distractors are a **closed set of evidential relations**:
  {supports · weakens · consistent-but-not-diagnostic · contradicts a *different*
  claim}. Correctness is a **logical judgment about the finding vs the claim**,
  not a fact lookup, and the hardest trap ("consistent-but-not-diagnostic") is a
  *fixed slot* the model learns to place, not an open invention.

Both collapse to the same underlying skill: **"classify a scenario into one of a
small named set of relations, and justify each option from its fixed
signature."** That is a *format/constraint* behavior, which is the exact thing
fine-tuning instills reliably and prompting does not [spec; loraland; struct-sql].
Free-form archetypes have no such closed set, so they keep the model in
open-generation territory where small models hallucinate and pick filler
distractors. **Structural determinacy is the feasibility lever.**

Note the crown-jewel labels don't perfectly coincide: the taxonomy marks
`EXPERIMENTAL_FIX_OR_FLAW` and `THEORY_PLUS_STUDY` as crown jewels, while the
*structurally-determined* pair is `MECHANISM_PERTURBATION` + `THEORY_PLUS_STUDY`.
We optimize for **structural determinacy, not the crown-jewel label** — which is
why `EXPERIMENTAL_FIX_OR_FLAW` ranks Tier-2 (its answer depends on *knowing the
real confound*, a knowledge dependency that reintroduces SC5 risk) and
`MECHANISM_PERTURBATION` is promoted to the anchor.

### 3b. Why 1–2 archetypes, not many

- **Spec law:** *"No broad domains. One target, one context. Diffuse data makes a
  mushy model."* Every added archetype widens the training distribution and
  raises SC6 variance — directly opposing the deliverable (reliability).
- **Capacity is the binding constraint at 4B.** Concentrating limited capacity on
  one reasoning schema maximizes per-item reliability; spreading it across 8
  schemas is how you get a model that is mediocre at all of them.
- **Why two, not one.** `MECHANISM_PERTURBATION` and `THEORY_PLUS_STUDY` share
  the *same* deep skill (closed-set relational classification + per-option
  justification), so training both **reinforces** the shared behavior rather than
  diluting it, while hedging our bets: MECH_PERT has the **best seed coverage**
  (safest), THEORY_PLUS_STUDY has the **highest expert value** (most impressive
  demo). If a single-archetype maximum-confidence build is preferred, ship
  **MECHANISM_PERTURBATION alone** (§4 confidence is highest there).

---

## 4. Confidence gate and assumptions

**Confidence that a fine-tuned Qwen3-4B reliably beats its prompted base at
expert-grade items, by scope:**

| Scope | Model | Confidence | Gate (>90%)? |
| :--- | :--- | :---: | :---: |
| `MECHANISM_PERTURBATION` only | Qwen3-4B | **~93%** | ✅ |
| `MECHANISM_PERTURBATION` + `THEORY_PLUS_STUDY` | Qwen3-4B | **~92%** (w/ §5 preconditions) | ✅ |
| Same 2 archetypes | Qwen3-1.7B | ~82% | ❌ (fallback only) |
| Same 2 archetypes | Qwen3-0.6B | ~60% | ❌ (do not greenlight) |
| Add a 3rd–4th archetype | Qwen3-4B | ~85% and falling | ❌ (defer to v2) |
| Any free-form archetype (e.g. vignette) | Qwen3-4B | ~55–65% | ❌ |

**Greenlight:** the **two-archetype scope at 4B, at 92%**, *conditional on §5*.
The 92% is a base-vs-tuned claim (the required bar), not a beat-frontier claim.

**The assumptions the 92% rests on** (each is falsifiable and mostly confirmable
in the Day-2 litmus run *before* training):

1. **Teacher ceiling exists.** A frontier teacher clears **≥70%** expert-grade on
   these two archetypes (litmus BUILD-zone). If the teacher can't, there are no
   clean labels to distill → this assumption is the load-bearing one.
2. **Data quantity/quality.** ≥**600–1,000** hard-filtered distilled items *per
   archetype* (all §7 disqualifying checks enforced programmatically + by judge).
   200–1,000+ is the demonstrated effective range [loraland]; quality gate > raw
   volume [spec].
3. **A verification pass is in the loop** (programmatic gates + LLM-judge or
   self-consistency vote) that *rejects* items failing single-best-answer /
   double-correct / concept-leak. This converts SC5 from a liability into a gated
   output; contrastive/negative-labeled training further sharpens it [ccot].
4. **Items stay qualitative.** Km↑/Vmax= expressed as *relations/words*; any
   numeric fingerprint is **given data**, never computed by the model (dodges SC7)
   [easymath].
5. **Size = 4B.** The confidence is stated for 4B; 1.7B is below-gate, 0.6B far
   below [arith-2025].
6. **Eval is base-vs-tuned on held-out notes**, reusing the 82 first-principles
   cards as seeds and the 30×2 paraphrase set as the transfer/novelty probe.

If assumption 1 or 3 fails, fall back to `MECHANISM_PERTURBATION`-only (still
≥90% under assumptions 2/4/5/6) or to the RETHINK reframes in §5.

---

## 5. Preconditions & kill-criteria

**Preconditions — must be true for the 92% to hold:**

- **P1.** Litmus run shows the **frontier teacher ≥70%** expert-grade on the two
  archetypes (clean-label ceiling exists).
- **P2.** Litmus run shows **prompted base 4B ≤45–55%** on the same (a real gap
  exists to close — otherwise the litmus fails and we ship a prompt).
- **P3.** ≥600–1,000 filtered items/archetype; answer-key validity of the
  *training set* audited (garbage-in kills SC5).
- **P4.** Inference-time verifier wired in (reject-and-regenerate on any
  disqualifying check); qualitative-only item policy enforced.
- **P5.** Held-out eval uses unseen notes + the paraphrase transfer set;
  report pass rate **and** run-to-run variance (reliability, not peak).

**Kill-criteria — a single result that flips the verdict:**

| Observation in the litmus / v1 run | Flips to | Why |
| :--- | :--- | :--- |
| **Prompted base 4B ≥80%** expert-grade on the scope | **DON'T BUILD** | The litmus fails — a prompt already does it reliably; fine-tuning earns nothing [spec §"litmus"]. |
| **Frontier teacher <50–70%** even with few-shot, on the scope | **RETHINK** | No clean labels to distill. Reframe: (a) supply the data object/passage and have the model *write the item around it* rather than invent the scenario; (b) add retrieval grounding for facts; (c) narrow to `MECHANISM_PERTURBATION` only. |
| Tuned-4B **single-best-answer correctness stays <~85%** after data iteration **and** with the verifier | **RETHINK scope** | SC5 (the true crux) is unrecoverable at this scope/size → drop to one archetype, add retrieval, or move to a "grade/repair an item" output unit instead of "generate from scratch." |
| Tuned model beats base on clean notes but **collapses on messy/multi-concept notes** (SC6) | **NARROW inputs** | Constrain to clean principle-card notes for v1; treat robustness as a v2 (adversarial) rung. |

**The single most decision-relevant result:** whether the **frontier teacher can
reliably produce expert-grade `MECHANISM_PERTURBATION` / `THEORY_PLUS_STUDY`
items** in the litmus run. Teacher-can + base-can't = the textbook distillation
BUILD regime and the 92% holds. Teacher-can't = RETHINK immediately, because
every downstream number depends on the label quality the teacher provides.

---

## 6. Evidence ledger (what each source actually supports)

- **[loraland]** LoRA Land (arXiv:2405.00732): 310 QLoRA fine-tunes (≤8B) beat
  base by +34 and GPT-4 by +10 avg; best fine-tune 0.756 vs GPT-4 0.661. **But**
  GPT-4 still wins 6/31 on *broad* tasks (coding, MMLU); fine-tune wins are on
  *narrow, classification-like* tasks. → Supports "narrow + tuned wins";
  cautions that these are 7B/classification, not ≤4B generative quality.
- **[arith-2025]** *How LLMs Perform Arithmetic Reasoning in 2025*: Qwen3-0.6B
  1.4% vs 85.8% (mode-dependent format collapse); Qwen3-4B/8B robust 96%+;
  4B≈8B. → Direct basis for the **0.6B→4B reliability cliff** and the size pick.
- **[easymath]** EasyMath (arXiv:2505.14852): SLMs fail multi-digit/large-number
  arithmetic; "direct distillation of complex reasoning often fails… they do
  better with shorter, simpler chains." → Exclude `QUANTITATIVE_APPLICATION`;
  keep reasoning to ~2 hops.
- **[slm-review]** *State of the Art… SLMs: A Systematic Review* (MDPI 2025):
  ~1/5 of SLM failures are hallucination/inconsistency; lean models "fill gaps
  with plausible fabrications"; **but** MobileLLM-350M matches Llama-2-7B on
  narrow API-call tasks. → SC5 is the crux; narrow tasks are the exception.
- **[struct-sql]** *KD with Structured CoT for Text-to-SQL* (arXiv:2512.17053):
  distilling a **structured blueprint** beats unstructured-CoT distillation by
  **+8.1**, mainly by cutting syntactic/schema errors in the SLM. → Direct
  analogue for the closed-set distractor schema argument (§3a).
- **[ccot]** *Contrastive CoT Fine-Tuning* (Zenodo 2025): pairing correct paths
  with **labeled fallacies** via LoRA on Phi-2 → −hallucination, **+12.5%**. →
  Supports distractor-as-named-error training and the DPO/negatives stretch rung.
- **[kd-qlora]** KD-LoRA / KdQLoRA: QLoRA + KD is a standard, working recipe. →
  Method feasibility.
- **In-repo:** 82 first-principle seed cards (well-distributed), 60-concept
  taxonomy, 169 OpenMCAT items *all with per-choice rationales + common-mistake
  notes* (~23 mechanism-perturbation-ish, ~20 theory/data-ish; the LDH-R passage
  is genuinely strong), 30×2 paraphrase transfer items. → Ceiling is non-zero
  (a capable model *can* write these) and seed/eval scaffolding already exists;
  says nothing about ≤4B, which the litmus must measure.

---

## 7. TL;DR

- **BUILD, but narrow to two structurally-determined archetypes**
  (`MECHANISM_PERTURBATION` + `THEORY_PLUS_STUDY`) on **Qwen3-4B**; **92%**
  confidence on the required base-vs-tuned bar, conditional on a verification pass.
- **Structural determinacy — not the "crown-jewel" label — is the feasibility
  lever.** It turns novel-scenario, distractor, and answer-key work into
  templated classification, the SLM sweet spot.
- **Exclude** arithmetic (`QUANTITATIVE_APPLICATION`) and, notably, the user's
  fact-heavy `CLINICAL_VIGNETTE_TO_DIAGNOSIS` from v1.
- **The crux and the kill-switch are the same thing:** single-best-answer
  correctness, gated by a verifier and by confirming the teacher's ceiling in the
  litmus run before a single training step.
