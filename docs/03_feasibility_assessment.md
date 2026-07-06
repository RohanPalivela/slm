# SLM Feasibility Assessment — Deliverable 3

> **The one question this answers:** *Can a fine-tuned SMALL open model (0.6B–4B,
> QLoRA SFT + frontier-teacher distillation) RELIABLY turn study notes / historical
> sources into expert-grade AP U.S. History (APUSH) stimulus-based MCQs — and at
> what SCOPE (which archetypes, which model size)?* This stage runs no model; it
> converts the taxonomy ([`01`](01_apush_question_taxonomy.md) /
> [`taxonomy/apush_question_archetypes.json`](../taxonomy/apush_question_archetypes.json))
> and the litmus design ([`02`](02_litmus_test_prompt.md)) into a calibrated
> **go / narrow / rethink** decision with an explicit confidence and kill-criteria.
> It is deliberately skeptical: per the spec, the win is **reliability of a
> constrained behavior**, not raw capability. Every number below is a *prior* the
> Day-2 litmus run must confirm before a single training step (§5).

---

## 0. Executive verdict

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  VERDICT:           BUILD — but NARROW HARD                                     │
│                                                                                │
│  RECOMMENDED SIZE:  Qwen3-4B-Instruct  (QLoRA SFT + frontier distillation)     │
│                     → 0.6B is DISQUALIFIED for a reliability-first spec         │
│                       (documented 0.6B→4B cliff [arith-2025]); 1.7B is a        │
│                       fallback, not the pick.                                   │
│                                                                                │
│  RECOMMENDED SCOPE: TWO date-anchored causation archetypes that share one      │
│                     deep skill —                                                │
│                       1. CAUSE_OF_SOURCE   (IN — anchor; crown jewel)           │
│                       2. EFFECT_OF_SOURCE  (IN; same skill, opposite arrow)     │
│                     First sanctioned expansion: CONTEXT_SITUATION (§3).         │
│                     Everything else: Tier-2/3, OUT, or DON'T-BUILD (§3).        │
│                                                                                │
│  CONFIDENCE:        91%  that a tuned Qwen3-4B reliably beats its OWN prompted  │
│                     base at expert-grade items on this scope — CONDITIONAL on   │
│                     the §5 preconditions (answer GROUNDED to the developments   │
│                     table + a verification pass + a confirmed teacher ceiling). │
│                     Strip grounding OR the verifier → ~82%. At 1.7B: ~78%.      │
│                     At 0.6B: ~55%.  CAUSE_OF_SOURCE alone: ~92%.                │
│                                                                                │
│  BIGGEST RISK:      SC-KEY — single-best HISTORICAL correctness. A keyed        │
│                     answer that is factually wrong, or (worse) a distractor     │
│                     that is ALSO defensibly "most directly" correct. The date   │
│                     verifier catches only the wrong-era slice; it CANNOT        │
│                     certify "most directly." This is why the verifier +         │
│                     table-grounding are preconditions, not nice-to-haves.       │
└──────────────────────────────────────────────────────────────────────────────┘
```

**One-sentence thesis.** APUSH's fact-density makes single-best-answer historical
correctness (SC-KEY) a *worse* crux than any science domain — but APUSH also has
unusually strong **structural determinacy** (provided stimulus + closed stem menu
+ closed 4-trap distractor menu + a date-tagged verifier), and where those levers
apply *most completely* — the date-anchored causation archetypes — they convert
open-ended generation into **templated selection + rule-derivation**, the SLM
sweet spot. Feasibility is therefore not uniform across the 12 archetypes; it is
governed by **how much of SC-KEY the structural levers can offload**, which is
highest for `CAUSE_OF_SOURCE`/`EFFECT_OF_SOURCE` and near-zero for
`COMPETING_INTERPRETATIONS`.

---

## 1. What "success" / "outperform" means here

The spec is blunt: *"Your 1B model will not beat a frontier model on raw
capability… the defensible win is reliable, constrained behavior."* We grade
against two bars; only the first is required.

| Bar | Definition | Required? | Verdict |
| :--- | :--- | :--- | :--- |
| **Primary — base-vs-tuned** | Tuned SLM produces `expert_grade` items (all disqualifying `quality_checks` pass) at a **higher pass rate AND lower run-to-run variance** than the *same model prompted with the maximal litmus prompt* ([`prompts/litmus_generation_prompt.md`](../prompts/litmus_generation_prompt.md)). | **YES** (spec's midweek gate) | **Winnable at high confidence** on the narrow scope. |
| **Secondary — beat prompted frontier** | Tuned SLM matches a prompted frontier model's pass rate. | **No** | Not required; do **not** stake the project on it. |

**Why the base-vs-tuned delta is winnable — decomposed honestly.** The delta is
*near-certain on five of six sub-capabilities and conditional on the sixth*:

- The base SLM, even with the *best* prompt, drifts in exactly the ways the
  quality checks forbid: it **breaks strict JSON** under load (Qwen3-0.6B hits
  **1.4%** format compliance in direct-answer mode vs 85.8% in its preferred mode
  [arith-2025]); it **"asks the source back to itself"** (fails
  `requires_outside_knowledge`); it writes **filler distractors** that match no
  trap in the menu; and it **fabricates or double-keys** answers (hallucination is
  ~1/5 of SLM failures [slm-review]). The first three are *format/behavior* gaps —
  the canonical thing SFT on a tight, filtered distribution fixes reliably and a
  prompt cannot guarantee. This is the regime where LoRA-Land fine-tunes beat
  their base by **+34 pts** average [loraland], structured-blueprint distillation
  adds **+8.1** over unstructured-CoT distillation [struct-sql], and
  fallacy-labeled contrastive negatives add **+12.5%** on Phi-2 [ccot].
- The **sixth** — SC-KEY (historical correctness) — is *not* automatically fixed
  by SFT, because history isn't derivable from first principles. It is the entire
  reason this verdict is BUILD-**NARROW** and conditional, not BUILD.

So the "outperform" claim is precise: the tuned model wins the required
base-vs-tuned bar because it captures the format/distractor/skill wins for free
**and** — via table-grounding + an inference-time verifier — keeps its SC-KEY tail
from tanking the expert-grade rate, while the prompted base cannot.

---

## 2. Sub-capability decomposition & per-size feasibility

`f(source, note) → expert APUSH MCQ` breaks into seven load-bearing
sub-capabilities. Scores are **post-QLoRA-SFT + distillation** feasibility, 0–1
(0 = won't do it reliably; 1 = reliable), for the **recommended narrow scope**.
Where a capability splits by archetype regularity, `a / b` = *free-form
archetypes / structurally-determined archetypes*.

| # | Sub-capability | 0.6B | 1.7B | 4B | Bottleneck? | Basis |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **SC1** | **Source comprehension** (read the *provided* stimulus) | 0.70 | 0.82 | 0.90 | No | Stimulus is given → this is short-passage reading, an SLM strength. Weakest on subtle secondary-source arguments (F5). |
| **SC2** | **Outside-knowledge retrieval** (recall the correct outside development) | 0.30 / 0.55\* | 0.45 / 0.70\* | 0.58 / 0.82\* | **Yes** | Free recall of history facts is an SLM weak point; the long tail barely improves with scale [mallen]. \*second number = answer **selected from the date-tagged developments table**, not free-recalled → recall becomes selection. |
| **SC3** | **Distractor authoring as trap-selection** (each wrong option = one named trap) | 0.25 / 0.60\* | 0.45 / 0.78\* | 0.60 / 0.88\* | **Yes (free-form); No (structured)** | The #1 expert differentiator. Free-form = invent misconceptions (hard). Structured = "pick a period-plausible development from the table + label its trap type" → a **classification** task, the SLM sweet spot [loraland, struct-sql]. |
| **SC4** | **Strict JSON / schema** (valid object + rationale + trap labels) | 0.80 | 0.90 | 0.96 | No (minor 0.6B) | Canonical fine-tuning win (the spec's own "structured-output" example). 0.6B retains format fragility under long schemas [arith-2025]. |
| **SC-KEY** | **Single-best historical correctness** (key right AND uniquely "most directly") | 0.28 / 0.52\* | 0.42 / 0.68\* | 0.55 / **0.80**\* | **YES — TRUE CRUX** | Two failure modes: keyed answer *factually wrong* (fabrication [slm-review, mallen]) and keyed answer *not uniquely best* (a distractor also defensible). \*with table-grounding + date-check + judge. Even at 4B this tops out ~0.80 because the date-check is **necessary-not-sufficient** (see below). |
| **SC-CONS** | **Cross-input reliability / low variance** | 0.45 | 0.65 | 0.80 | Partial | SFT on a narrow distribution sharpens consistency — the whole point. Improves monotonically as scope narrows → argues for 2 archetypes, not 8. |
| **SC-SKILL** | **Command-phrase → skill match** (answer is the KIND the stem demands) | 0.55 | 0.72 | 0.86 | No | The closed stem menu deterministically signals the required answer type; labeled SFT instills the mapping well [struct-sql]. |

\* `a / b` = free-form / structurally-determined (or, for SC-KEY/SC2,
free-recalled / table-grounded).

**The true bottleneck is SC-KEY, and it is worse than a science domain.** In the
MCAT analog, a `MECHANISM_PERTURBATION` key was *fully rule-derivable* (a Km↑/Vmax=
truth table → a deterministic verifier). APUSH has **no** fully rule-derivable
archetype. Its programmatic verifier — the anachronism date-check against
[`data/apush_key_developments.json`](../data/apush_key_developments.json) — only
confirms that the keyed development's date obeys the stem's time direction (cause
before, effect after) and that a `wrong_era` distractor violates it. That rules
out the **wrong-era slice** of SC-KEY but **cannot** certify the "most directly"
uniqueness judgment: for `CAUSE_OF_SOURCE`, both the *specific mechanism* and the
*broad background condition* predate the source, so both pass the date-check — yet
only one is keyable. The residual "second-defensible-option" tail is exactly what
keeps SC-KEY at ~0.80, not ~0.95, even at 4B with the verifier.

**Why grounding matters more than raw scale for SC-KEY.** History is long-tail and
scaling barely moves tail recall [mallen], so *drawing the outside development from
the curated table* beats free recall by more than 1.7B→4B does. Honest caveat:
sub-7B models under-utilize even *oracle* context (a 7B extracts the answer only
**14.6%** of the time on facts it doesn't already know; plain instruction-tuning
is insufficient for grounding) — but the fix that same work identifies is
**fine-tuning for grounding** (RAFT-style), exactly our QLoRA-on-distilled-and-
grounded recipe, and distilling RAG into SLMs cuts hallucination [slm-util, drag].
Hence "answer grounded to the table" is a *precondition* (§5), and if SC-KEY still
stalls the fallback is to shrink the job further — from "select from the table" to
"**select-and-justify from a provided candidate answer set**" (near-classification).

**The size cliff (why 4B, not 0.6/1.7B).** The most model-specific evidence we
have is on the exact family the spec names: Qwen3-0.6B shows catastrophic
instruction/format collapse (**1.4%** in one mode) while **Qwen3-4B is robust
(96%+) and 4B≈8B** (diminishing returns beyond 4B) [arith-2025]. For a
deliverable whose entire point is *reliability*, paying the modest VRAM for 4B is
the highest-leverage single decision. 0.6B fails SC4/SC-KEY/SC-CONS
simultaneously; 1.7B is a below-gate fallback.

---

## 3. Scope decision — the central question

Every archetype scored on the four criteria the task specifies:
**(a) structural regularity / anachronism-verifiability** (how much the levers
offload), **(b) factual/recall load** (lower = safer for SC-KEY), **(c)
`note_seedability`** and **(d) `expert_feel`** (from the JSON). "v1" is the
resulting recommendation.

| Archetype | Fam | (a) Regularity / date-verifiable | (b) Recall load | (c) Seed | (d) Expert | v1 |
| :--- | :---: | :--- | :---: | :---: | :---: | :--- |
| **CAUSE_OF_SOURCE** | F3 | **High** / ✅ (dir. checkable; "most directly" not) | Med | 0.85 | 0.85 | **IN — anchor** |
| **EFFECT_OF_SOURCE** | F3 | **High** / ✅ (effect postdates; reversed-dir trap) | Med | 0.85 | 0.85 | **IN** |
| CONTEXT_SITUATION | F2 | High / ✅ (response-to a prior crisis) | **Low–Med** | 0.85 | 0.70 | **IN (safe 3rd / v1.1)** |
| CONTEXT_INFLUENCED_BY | F2 | High / ✅ (antecedent idea predates) | Med–High | 0.80 | 0.75 | Tier-2 |
| LONGTERM_LEGACY | F4 | Med–High / ✅ but multi-hop | **High** | 0.75 | 0.85 | Tier-2 |
| EVIDENCE_SUPPORTS_CLAIM | F5 | Low–Med / ⚠️ loose (period-only; relevance not checkable) | High | 0.75 | **1.0** | Tier-2 (v2 crown) |
| CONTINUITY_OR_CHANGE | F4 | Med / ⚠️ date-only (challenge-vs-continue not checkable) | Med–High | 0.70 | 0.90 | Tier-3 |
| COMPARATIVE_ANALOG | F4 | Med / ⚠️ date-only (shared-mechanism not checkable) | High | 0.70 | 0.90 | Tier-3 |
| SOURCE_POV_PURPOSE | F1 | Med / ❌ not verifiable | Low–Med | 0.80 | 0.55 | Tier-3 |
| EVIDENCE_UNDERMINES_CLAIM | F5 | Low / ❌ verifier useless for support-vs-undermine | High | 0.70 | **1.0** | **OUT** (SLM trap) |
| COMPETING_INTERPRETATIONS | F5 | **Low** / ❌ not verifiable; needs 2-source | High | 0.65 | **1.0** | **OUT** (SLM trap) |
| DEVELOPMENT_ILLUSTRATED | F1 | Med / ❌ | Med | 0.90 | 0.40 | **DON'T-BUILD** |

### 3a. The recommended v1 scope: the date-anchored causation pair

**`CAUSE_OF_SOURCE` (anchor) + `EFFECT_OF_SOURCE`.** They are the *same operation
in opposite temporal directions* — "map the stimulus to the one outside
development from the date table whose date obeys the required direction and that
is the *specific*, not background, match." All four levers apply maximally:

1. **Stimulus provided** → the model reasons over a given source, dodging the
   biggest fabrication vector (it never invents the source) — applies to all
   archetypes, but pairs with (4) only here and in F2.
2. **Closed stem menu** → `cause_of` / `effect_immediate` deterministically fix
   the required answer *kind* (SC-SKILL).
3. **Closed 4-trap distractor menu** → distractors become "select a
   period-plausible development + label its trap," a classification task (SC3).
4. **Anachronism date-check** → a *programmatic* verifier for the whole class:
   cause must predate, effect must postdate, and a `wrong_era` distractor must
   violate it. This is the APUSH analog of a deterministic truth-table — the only
   archetypes where it fires cleanly are the single-direction causal ones.

The honest limit (§2): lever 4 is *necessary-not-sufficient* — it kills wrong-era
errors but not the "most directly" double-key, which only grounding + an LLM-judge
single-best/accuracy pass can mop up.

### 3b. Explicit OUT / DON'T-BUILD calls (the signal this is a real assessment)

- **`COMPETING_INTERPRETATIONS` — OUT.** Highest `expert_feel` (1.0) yet the worst
  SLM target: `anachronism_verifiable = false` (no programmatic safety net at
  all), it needs a *two-source* stimulus, and the answer is a subtle
  identify-the-axis-of-disagreement judgment over long-tail historiography. It
  keeps the model in pure open-generation where small models fail. Defer to v2+.
- **`EVIDENCE_UNDERMINES_CLAIM` — OUT.** The hardest single item type: telling a
  *weakener* from a *confirmer* is a logical-relevance judgment the date-check
  cannot touch, and the tempting confirming-distractor makes double-keying easy.
- **`COMPARATIVE_ANALOG` / `CONTINUITY_OR_CHANGE` — Tier-3.** Date-verifiable only
  for the "later" half; the *core* judgment (shared mechanism; challenge-vs-
  continue) is semantic, not checkable, and both are recall-heavy. Classic
  free-form, recall-heavy traps.
- **`DEVELOPMENT_ILLUSTRATED` — DON'T-BUILD.** Lowest `expert_feel` (0.4) and the
  closest to comprehension; a well-prompted base very likely **already clears it**
  → the base-vs-tuned delta is small, so fine-tuning earns little (the litmus
  DON'T-BUILD logic applied at the archetype level). `MAIN_POINT_OF_SOURCE`
  ([`01b`](01b_taxonomy_supplement.md)) is the same story, more so.

### 3c. Why 2–3 archetypes, not many

- **Spec law:** *"No broad domains. One target, one context. Diffuse data makes a
  mushy model."* Each added archetype widens the training distribution and raises
  SC-CONS variance — directly opposing the deliverable (reliability).
- **Capacity concentration.** At 4B, per-item reliability is maximized by pointing
  limited capacity at *one deep skill*. `CAUSE`/`EFFECT` share that skill, so
  training both **reinforces** the shared "check the date direction, pick the
  specific match" behavior rather than diluting it.
- **Why two (or three), not one.** The pair hedges: `CAUSE_OF_SOURCE` is the
  crown-jewel anchor; `EFFECT_OF_SOURCE` adds the clean reversed-direction
  `partially_true` distractor and natural `SET_OF_THREE` cohesion.
  `CONTEXT_SITUATION` is the **safest single archetype on SC-KEY** (its "response
  to" answer is usually one dominant, well-known crisis → low double-key risk) and
  is the sanctioned first expansion once the pair validates.

---

## 4. Confidence gate & assumptions

**Confidence that a fine-tuned Qwen3-4B reliably beats its prompted base at
expert-grade items (higher pass rate + lower variance), by scope and size.** The
user requires **>90%** to greenlight.

| Scope | Size | Conditions | Confidence | >90%? |
| :--- | :--- | :--- | :---: | :---: |
| `CAUSE_OF_SOURCE` only | **4B** | grounded + verifier + teacher-confirmed | **~92%** | ✅ |
| `CAUSE` + `EFFECT` (the pair) | **4B** | grounded + verifier + teacher-confirmed | **~91%** | ✅ |
| Pair + `CONTEXT_SITUATION` (3) | 4B | same | ~89% | ❌ (→ v1.1) |
| The pair | 4B | **no table-grounding** *or* **no verifier** | ~82% | ❌ |
| The pair | 1.7B | grounded + verifier | ~78% | ❌ (fallback) |
| The pair | 0.6B | grounded + verifier | ~55% | ❌ (do not greenlight) |
| Add `EVIDENCE_SUPPORTS_CLAIM` (F5) | 4B | grounded + verifier | ~74% | ❌ (v2) |
| `EVIDENCE_UNDERMINES` / `COMPETING_INTERP` | 4B | best case | ~60–68% | ❌ |
| Any free-form, recall-heavy archetype | 4B | grounded + verifier | ~65% | ❌ |

**Greenlight:** the **causation pair at 4B, ~91%**, *conditional on §5*
(`CAUSE_OF_SOURCE` alone is ~92% if a single-archetype maximum-confidence build is
preferred). **The honest bottom line the fact-density crux forces:** *only the
grounded + verified, date-anchored causation scope at 4B clears 90%.* Remove
table-grounding, remove the verifier, drop below 4B, or widen past the pair, and
it falls under the bar. This is a narrower and more conditional greenlight than a
science domain would earn, and that is the correct read of an APUSH build.

**Falsifiable assumptions the 91% rests on** (each mostly confirmable in the
Day-2 litmus run *before* training):

1. **Teacher ceiling exists.** A frontier teacher clears **≥70–75%** expert-grade
   *and* **`key_valid_rate` ≥70–75%** on these two archetypes in the litmus. If
   the teacher can't key APUSH items correctly and uniquely, there are no clean
   labels to distill — the single load-bearing assumption.
2. **Enough filtered data.** ≥**600–1,000** hard-filtered distilled items *per
   archetype*, every disqualifying `quality_check` enforced (programmatic + judge).
   200–1,000+ is the demonstrated effective range [loraland]; quality gate ≫ raw
   volume [spec].
3. **A verification pass is in the loop** — programmatic (date-check, option
   homogeneity, absolute-word regex, source-leak) **plus** an LLM-judge
   historical-accuracy + single-best check — that *rejects and regenerates* on any
   disqualifying failure. Converts SC-KEY from a liability into a gated output.
4. **The keyed outside development is GROUNDED** — selected from
   [`apush_key_developments.json`](../data/apush_key_developments.json), not
   free-recalled [mallen, drag, slm-util]. The single biggest SC-KEY lever.
5. **The stimulus is provided** from the legal corpus
   ([`seed_stimuli.jsonl`](../data/seed_stimuli.jsonl)) — dodges source
   fabrication.
6. **Size = 4B** (1.7B below gate, 0.6B far below) [arith-2025].
7. **Eval is base-vs-tuned on HELD-OUT sources**, disjoint from training seeds per
   the `splits.json` firewall; report pass rate **and** run-to-run variance
   (reliability, not peak).

If assumption 1, 3, or 4 fails, fall back to `CAUSE_OF_SOURCE`-only or the §5
RETHINK reframes.

---

## 5. Preconditions & kill-criteria

**Preconditions — must hold for the 91% (confirm in the Day-2 litmus, pre-training):**

- **P1.** Litmus shows **frontier teacher ≥70–75%** expert-grade AND
  **`key_valid_rate` ≥70–75%** on `CAUSE_OF_SOURCE` / `EFFECT_OF_SOURCE`
  (clean-label ceiling exists).
- **P2.** Litmus shows **prompted base 4B ≤45–55%** on the same (a real gap to
  close; otherwise the litmus fails and we ship a prompt, not a fine-tune).
- **P3.** ≥600–1,000 filtered items/archetype; the *training set's* answer-key
  validity audited (date-check + a human spot-check slice — LLM judges themselves
  err on history facts, per [`02`](02_litmus_test_prompt.md) §4b).
- **P4.** Inference-time verifier wired (reject-and-regenerate on any disqualifying
  check, incl. the anachronism date-check and a single-best/historical-accuracy
  judge pass).
- **P5.** Answer-grounding enforced: the outside development is drawn from the
  developments table (selection), never free-recalled.
- **P6.** Held-out eval on unseen sources (splits.json firewall); report pass rate
  **and** variance.
- **P7.** v1 inputs = **text primary sources only** (exclude image/map/chart per
  [`01b`](01b_taxonomy_supplement.md) §3; secondary-source F5 deferred).

**Kill-criteria — a single observation that flips the verdict:**

| Observation (litmus or v1 run) | Flips to | Why |
| :--- | :--- | :--- |
| **Prompted base 4B ≥80%** expert-grade on the scope | **DON'T BUILD** | A prompt already does it reliably; fine-tuning earns nothing (the spec's litmus). |
| **Frontier teacher `key_valid_rate` <70%** even with few-shot | **RETHINK** | No clean labels to distill. Reframe: change the output unit to "**repair/grade** an item" or "select-and-justify from a **provided candidate answer set**"; add retrieval grounding; or narrow to `CAUSE_OF_SOURCE` only. |
| Tuned-4B **SC-KEY stays <~85%** after data iteration **and** with the verifier | **RETHINK scope** | The crux is unrecoverable at this scope/size → drop to one archetype, tighten grounding to a candidate set, or switch to the repair/grade output unit. |
| Tuned beats base on clean sources but **collapses on terse/adversarial notes** | **NARROW inputs** | Constrain to clean primary-source inputs for v1; treat robustness as a v2 adversarial rung. |
| Prompted base already ≥80% on `DEVELOPMENT_ILLUSTRATED` | (expected) confirms **DON'T-BUILD** that archetype | Low delta; don't spend capacity on it. |

**The single most decision-relevant number** is the litmus **`key_valid_rate`** of
the *frontier teacher* on the causation pair. Teacher-can-key + base-can't = the
textbook distillation BUILD regime and the 91% holds. Teacher-can't-key = RETHINK
immediately, because every downstream number depends on the label quality the
teacher provides.

---

## 6. Evidence ledger (what each source actually supports — and its caveat)

- **[arith-2025]** *How LLMs Perform Arithmetic Reasoning in 2025*: Qwen3-0.6B
  1.4% vs 85.8% (mode-dependent format collapse); Qwen3-4B/8B robust 96%+, 4B≈8B.
  → **The direct basis for the 0.6B→4B reliability cliff and the 4B pick.**
  *Caveat:* it's arithmetic/format, not history — but it's the most model-specific
  evidence for the exact family the spec names.
- **[slm-review]** *State of the Art… SLMs: A Systematic Review* (MDPI 2025):
  ~1/5 of SLM failures are factual/consistency hallucinations ("plausible
  fabrications"); yet MobileLLM-350M matches Llama-2-7B on *narrow* tasks. →
  **Basis for SC-KEY being the crux** (acute in fact-dense history) and for narrow
  scope + grounding as the mitigation. *Caveat:* survey-level, domain-general.
- **[mallen]** Mallen et al., *When Not to Trust Language Models* (ACL 2023, PopQA):
  memorization is limited to *popular* facts; scaling barely helps the long tail;
  retrieval (non-parametric memory) complements parametric memory. → **Grounds the
  fact-density crux** (APUSH is long-tail-heavy) **and the table-grounding lever.**
  *Caveat:* open-domain QA on GPT-Neo/OPT/GPT-3, not ≤4B item-writing.
- **[slm-util]** *Can Small Language Models Use What They Retrieve?* (2025): even
  with **oracle** retrieval, ≤7B models fail to extract the answer 85–100% of the
  time on unknown facts (7B: **14.6%**); standard instruction-tuning is
  insufficient for grounding, but **RAFT-style fine-tuning fixes utilization**. →
  **The honest downward pressure** on the confidence (why 91%, not 95%), and the
  reason grounding must be *trained in* (our recipe), plus the candidate-set
  fallback. *Caveat:* open-domain QA, instruction-tuned baselines; our task is more
  constrained (select-from-table, not extract-from-noisy-passage).
- **[drag]** *DRAG: Distilling RAG for SLMs* (ACL 2025, arXiv:2506.01954):
  distilling RAG (evidence + graph grounding) into SLMs cuts hallucination and
  raises factual accuracy (>MiniRAG by up to 27.7%). → Supports the
  **distillation + grounding** recipe as the SLM-appropriate path to factual
  reliability. *Caveat:* QA/knowledge tasks, not MCQ authoring.
- **[loraland]** *LoRA Land* (arXiv:2405.00732): 310 QLoRA fine-tunes (≤8B) beat
  base by +34 and GPT-4 by +10 avg, concentrated on **narrow, classification-like**
  tasks. → Directional support for "narrow + tuned wins" and the
  **distractor-as-classification** argument (SC3). *Caveat, stated plainly:* the
  headline wins are **7B and classification**, not ≤4B generative quality — so this
  is *directional*, not proof for our size/task.
- **[struct-sql]** *KD with Structured CoT* (arXiv:2512.17053): distilling a
  **structured blueprint** beats unstructured-CoT distillation by **+8.1**, mainly
  by cutting schema errors. → Direct analog for the **closed distractor-trap schema
  + strict JSON** (SC3/SC4/SC-SKILL). *Caveat:* text-to-SQL — supports the *form*,
  not history-fact recall (SC-KEY).
- **[ccot]** *Contrastive CoT Fine-Tuning* (Zenodo 2025): pairing correct reasoning
  with **labeled fallacies** (LoRA on Phi-2) → −hallucination, **+12.5%**. →
  Supports **"distractor = named trap"** training and the DPO/negatives stretch.
  *Caveat:* small benchmark; supports the training format, not fact recall.
- **[kd-lora]** *KD-LoRA* (arXiv:2410.20777): LoRA + KD is a standard, working
  efficient recipe. → **Method feasibility only.**
- **[missed-mcq]** APUSH prep-corpus analysis: wrong answers are usually
  *historically true* (the four traps); "most directly" = specific mechanism vs
  broad background. → Grounds the **distractor menu** and the key insight that
  "most directly" is a *reasoning* skill (winnable) even though its *uniqueness* is
  the SC-KEY residual. *Caveat:* prep source, not peer-reviewed; corroborates CED.
- **[CED-*]** College Board Course & Exam Description + sample MCQs: exam
  structure, the six skills / three reasoning processes, periods/themes, and that
  **every Section I MCQ is stimulus-based** (the basis for lever 1). *Caveat:* used
  for taxonomy analysis only, never as training data.

**Where external evidence is thin (APUSH-specific reasoning, flagged as such).**
No public study measures ≤4B models *authoring history MCQs*. The SC-KEY numbers
in §2 are therefore reasoned from (a) the fact-density + long-tail argument
[slm-review, mallen]; (b) a first-principles coverage analysis of the date-check
(necessary-not-sufficient → caps SC-KEY below the format sub-caps); and (c)
analogy to the MCAT structural argument, discounted because APUSH lacks a
fully-rule-derivable verifier. All three are assumptions the litmus `key_valid_rate`
and the base-vs-tuned run will confirm or break (§5).

---

## 7. TL;DR

- **BUILD, but narrow hard** to the two date-anchored causation archetypes
  (`CAUSE_OF_SOURCE` anchor + `EFFECT_OF_SOURCE`) on **Qwen3-4B**; **~91%**
  confidence on the required base-vs-tuned bar, **conditional** on table-grounding
  + a verification pass + a confirmed teacher ceiling. `CONTEXT_SITUATION` is the
  sanctioned first expansion.
- **SC-KEY (single-best historical correctness) is the crux, and it is *worse*
  than a science domain** — history isn't derivable from first principles, fact
  density is high, and small models fabricate long-tail facts [slm-review, mallen].
- **Structural determinacy is the counter-lever, but it is *partial*.** Provided
  stimulus + closed stem menu + closed trap menu turn scenario/distractor/skill
  work into templated selection (SLM sweet spot); the date-check is a real but
  *necessary-not-sufficient* verifier — it catches wrong-era, not "most directly."
- **Only a grounded + verified narrow scope clears 90%.** Strip grounding or the
  verifier, drop below 4B, or widen past the pair, and confidence falls under the
  bar.
- **Explicitly OUT of v1:** `COMPETING_INTERPRETATIONS` and
  `EVIDENCE_UNDERMINES_CLAIM` (highest expert-feel but no usable verifier and
  double-key-prone), the recall-heavy `COMPARATIVE_ANALOG` / `CONTINUITY_OR_CHANGE`
  (Tier-3), and **DON'T-BUILD** `DEVELOPMENT_ILLUSTRATED` (a prompted base likely
  already passes).
- **The crux and the kill-switch are the same thing:** single-best historical
  correctness — gated by a verifier and by confirming the frontier teacher's
  `key_valid_rate` in the litmus *before* a single training step.
