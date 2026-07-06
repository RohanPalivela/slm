# Training Plan v1 — Notes/Source → Expert APUSH Causation MCQs (SLM)

> **Deliverable 4, draft v1 (BRAINSTORMER output).** Operationalizes the binding
> verdict in [`../03_feasibility_assessment.md`](../03_feasibility_assessment.md).
> Inherits, does **not** relitigate: scope = the date-anchored causation pair
> (`CAUSE_OF_SOURCE` anchor + `EFFECT_OF_SOURCE`), base = **Qwen3-4B-Instruct**
> (QLoRA + frontier distillation), **~91%** confidence *conditional* on
> table-grounding + an inference-time verifier + a confirmed teacher
> `key_valid_rate`. Crux = **SC-KEY** (single-best historical correctness). The
> anachronism date-check is **necessary-not-sufficient**. `CONTEXT_SITUATION` is
> the sanctioned first expansion (stretch, not v1). Companion:
> [`brainlift_draft.md`](brainlift_draft.md).
>
> *A validator will find gaps. This is a genuine first draft, not padding.*

---

## 1. Plan at a glance

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ GOAL       Reliably turn a provided PD/CC-BY historical source into an         │
│            expert-grade APUSH stimulus-based MCQ for TWO archetypes.           │
│ SCOPE      CAUSE_OF_SOURCE (anchor) + EFFECT_OF_SOURCE. Text primary sources   │
│            only (P7). CONTEXT_SITUATION = stretch. F5/free-form = OUT.          │
│ BASE       unsloth/Qwen3-4B-Instruct-2507 (non-thinking), QLoRA 4-bit.         │
│ TEACHER    frontier model (ToS-gated); Judge = DIFFERENT family; Key-verifier  │
│            = THIRD family + programmatic date-check.                            │
│ DATA       Final ~1,600 kept items (~800/archetype; P3 floor = 600). Midweek   │
│            ~700 kept. ~39% net filter yield → ~4,500 raw generations.          │
│ GROUNDING  Keyed development SELECTED from data/apush_key_developments.json,    │
│            never free-recalled (P5). Non-negotiable.                            │
│ GATES      3-stage filter (programmatic → judge → key-verifier) at train time; │
│            same verifier reused at inference (reject-and-regenerate).           │
│ EVAL       (A) LITMUS build-gate (P1/P2) BEFORE training. (B) base-vs-tuned on  │
│            HELD-OUT sources, 3 runs, bootstrap CIs.                             │
│ WIN        Tuned ≥80% expert-grade AND lower run-to-run variance than prompted  │
│            base, on held-out sources; both archetypes ≥78%; key_valid ≥90%      │
│            post-verifier. Delta CI lower-bound > 0.                             │
│ KILL       Base ≥80% (DON'T BUILD) · teacher key_valid <70% (RETHINK) ·         │
│            tuned SC-KEY <85% after v2 + verifier (RETHINK scope).               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**One-week arc mapping:** M0 = Day 1 (setup/research/Brainlift) · M1–M2 = Day 2
(harness + smoke test + **litmus build-gate**) · M3 = Day 3 (v1 data + first
base-vs-tuned) · M4 = Day 4 (data iteration) · M5 = Day 5 (ship) · M6 = stretch.

---

## 2. Behavior spec (falsifiable, one paragraph)

> Given a **provided, legally-sourced, date-tagged historical STIMULUS** (text
> primary source) and a causation command phrase (`cause_of` → the answer is a
> CAUSE; `effect_immediate` → the answer is a short-term EFFECT), the model emits
> a **single strict-JSON APUSH stimulus-based MCQ** whose keyed answer is the
> **one outside development — SELECTED from
> [`data/apush_key_developments.json`](../../data/apush_key_developments.json),
> never free-recalled — that (a) is DATE-CONSISTENT with the stem's time
> direction** (a cause dated strictly *before* the stimulus date; an effect
> strictly *after*) **and (b) is the SPECIFIC, most-direct mechanism**, not a
> broad background condition and not a merely topical match; and whose **three
> distractors are each exactly one of the four named College Board traps**
> (`wrong_era`, `true_but_irrelevant`, `scope_mismatch`, `partially_true`),
> spanning **≥2 distinct trap types**, each a real, era-plausible development a
> strong-but-imperfect student would seriously consider. **An item PASSES iff:**
> valid JSON, 4 homogeneous options, exactly one key; the key **requires outside
> knowledge** (not a paraphrase of the source) reached in **≥2 reasoning hops**;
> the date-check holds **and** ≥1 distractor is a genuine `wrong_era` violation;
> and **exactly one** option is defensibly best (no distractor is *also* "most
> directly" correct). Any single violation FAILS the item — the identical boolean
> whether the item is being **generated** (data-gen rubric), **scored** (eval
> criterion), or **served** (inference guard).

This paragraph is the contract shared by §3 (generation), §4 (filtering), §5
(eval), and §7 (inference). It is intentionally the same wording as
[`brainlift_draft.md`](brainlift_draft.md) so thesis, data, and metric cannot
drift apart.

---

## 3. Data generation

### 3.1 Model roles (three DIFFERENT families — anti-correlated errors)

| Role | Family | Job | Why a distinct family |
| :--- | :--- | :--- | :--- |
| **Teacher** | Frontier A (e.g. Claude/GPT class) | Generate the item (stem + options + key + `answer_dating` + per-option trap labels) via [`data_gen_prompt.md`](../../prompts/data_gen_prompt.md) | Highest ceiling; establishes the clean-label distribution to distill. **Precondition (Deliverable 5 §4.2): confirm the teacher's ToS permits using outputs to train another model before any bulk generation.** |
| **Judge** | Frontier B (different vendor/family) | Score every disqualifying `quality_check` + graded rubric + single-best | A same-family judge shares the teacher's blind spots (correlated errors); a different family catches them. |
| **Key-verifier** | Frontier C (third family) **+ programmatic date-check** | Independently *solve* the item k-of-n; flag double-correct; run the deterministic anachronism date-check | SC-KEY is the crux; the only defensible certification is an *independent* solver that never saw the intended key, plus a rule-based date gate. |

> Programmatic date-check is family-independent and **always** runs (it is the one
> deterministic verifier APUSH affords). The date-check is
> **necessary-not-sufficient**: it kills the wrong-era slice of SC-KEY but cannot
> certify "most directly" — that residual is why the LLM judge + independent
> solver are also required (feasibility §2, SC-KEY caps ~0.80 even at 4B).

### 3.2 Seeds & firewall — `data/splits.json`

The firewall is a P6 precondition: **no stimulus_id may appear in more than one
partition.** Freeze it in `data/splits.json` on Day 1 (blocking artifact A1)
*before* any generation.

| Partition | Purpose | Size (v1) | Contents |
| :--- | :--- | :--- | :--- |
| **LITMUS** | Build-gate only (§5A); never used for gen | **15** sources (per [`02`](../02_litmus_test_prompt.md) §3) | 10 primary (1/core period 3–8 + 4 spread) + 3 secondary + 2 adversarial (terse note; multi-development source) |
| **EVAL_HELDOUT** | Product eval only (§5B) | **~18** primary sources | Disjoint from litmus & train; ≥6 themes, core periods 3–8 |
| **TRAIN** | Data generation only | **~55–80** primary sources | Disjoint from the above; the bulk-gen pool |

**Honest gap (validator will flag this):** the current corpus is **22 stimuli**
(14 primary + 8 secondary — see [`seed_stimuli.jsonl`](../../data/seed_stimuli.jsonl)).
That is enough for the litmus + a smoke test, **not** for TRAIN + EVAL at volume.
Corpus expansion to ~80–100 **text primary** stimuli is **blocking artifact A3**:
scale PD ingestion via [`build_seed_corpus.py`](../../data/build_seed_corpus.py)
(Wikisource/LoC/Avalon/CourtListener, ≤1930 or federal) + CC-BY(-SA) note-seeds
from The American Yawp / legacy OpenStax. Keep licenses **segregated with
per-chunk provenance** (Deliverable 5 §4.1 ShareAlike collision).

- **Note-seeds.** A "note-seed" = a short study-note paragraph (CC-BY textbook
  prose) paired with a PD stimulus, filling the optional `{{NOTE}}` slot; it
  steers which development the item should test. Note-seeds inherit the split of
  their stimulus (no cross-split leakage).
- **Embedding dedup.** Embed every kept item's `(stimulus_id + stem + answer)`;
  drop any pair with cosine **≥ 0.92** (near-duplicate stems/keys). Also enforce
  **cross-split** dedup at **≥ 0.90** so held-out items are not paraphrases of
  train items — the anti-contamination check in
  [`brainlift_draft.md`](brainlift_draft.md) §"what would falsify."

### 3.3 Prompts

Use [`data_gen_prompt.md`](../../prompts/data_gen_prompt.md) verbatim, with the
v1-scope archetype list = **{`CAUSE_OF_SOURCE`, `EFFECT_OF_SOURCE`}** only. The
grounding clause is mandatory and load-bearing:

> *"The keyed answer is derived as: (a claim licensed by the SOURCE) + (exactly
> one outside development **from the developments table**) whose date obeys the
> stem's time direction … Do NOT invent historical facts."*

Seed with the two litmus few-shots (`CAUSE_OF_SOURCE` + one causation exemplar)
plus any hand-verified gold items in `data/gold/` once they exist (artifact A4).
Generate **one item (or one `SET_OF_THREE`) per call** so each carries the full
verification payload.

### 3.4 Training-example schema

Each kept example is one JSON object (superset of the `data_gen_prompt.md` output,
plus provenance the filter stamps on):

```json
{
  "stimulus_id": "monroe_doctrine_1823",
  "source_text": "<verbatim stimulus>",
  "attribution": "President James Monroe, ... 1823",
  "source_date": 1823,
  "archetype": "CAUSE_OF_SOURCE",
  "stem_template": "cause_of",
  "period": 4, "theme": "WOR",
  "stem": "Which of the following contributed most directly to ...?",
  "options": ["...", "...", "...", "..."],
  "answer": "C",
  "answer_dating": "<keyed development's date + why it obeys the time direction>",
  "options_meta": {
    "A": {"development_id": "war_of_1812", "verdict": "wrong_era|true_but_irrelevant|scope_mismatch|partially_true|correct", "why": "<named error>"},
    "B": {"...": "..."}, "C": {"...": "..."}, "D": {"...": "..."}
  },
  "trap_types": ["scope_mismatch", "wrong_era", "true_but_irrelevant"],
  "requires_outside_knowledge": "<the outside development the answer depends on>",
  "reasoning_hops": 2,
  "_prov": {"teacher": "...", "judge_pass": true, "keyverify": {"votes": "3/3", "double_correct": false}, "gen_ts": "..."}
}
```

The **training target string** the model learns to emit is the object from
`archetype` through `reasoning_hops` (the `source_*` fields and `_prov` are prompt
context / bookkeeping, not generated). Loss is on the assistant JSON only (§6).

### 3.5 Phased volumes & expected filter funnel

Realistic one-week arc: a **midweek v1 set** (Day 3) big enough for a real
base-vs-tuned signal, then a **final v2 set** (Day 4–5) after data iteration.
Net keep ≈ **0.80 × 0.65 × 0.72 ≈ 0.39**.

| Stage | Midweek v1 | Final v2 (cumulative) | Yield |
| :--- | ---: | ---: | :--- |
| Raw teacher generations | 1,800 | 4,500 | — |
| After **Stage A** (programmatic) | 1,440 | 3,600 | ~80% |
| After **Stage B** (LLM judge) | 936 | 2,340 | ~65% of A |
| After **Stage C** (key-verifier) | **~674** | **~1,685** | ~72% of B |
| Kept per archetype | ~337 | **~840** | — |
| Trap-labeled rejects retained (DPO pool) | ~1,100 | ~2,800 | free byproduct |

Final ~840/archetype clears the **P3 floor of 600–1,000/archetype** with margin.
Rejects are **not discarded** — they are the DPO negative pool (stretch §9).

---

## 4. Quality gate (3 stages, with expected yields)

Ordered cheapest-first; a disqualifying failure at any stage drops the item.
Implemented once in `slm/verifier.py` and reused at inference (§7).

### Stage A — Programmatic (no API cost) · ~80% pass

| Check | Rule | Disq? |
| :--- | :--- | :---: |
| valid JSON / schema | parses; all required fields; 4 options; exactly one key | ✅ |
| `reasoning_hops ≥ 2` | integer field ≥ 2 | ✅ |
| no absolute / all-none | regex reject `all of the above|none of the above|always|never` | ✅ |
| **anachronism date-check** | keyed development date obeys `answer_time_direction` (cause `< source_date`, effect `> source_date`) vs [`apush_key_developments.json`](../../data/apush_key_developments.json); ≥1 distractor genuinely `wrong_era` | ✅ |
| trap-diversity ≥ 2 | the 3 distractors span ≥2 distinct trap ids | ➖ (warn) |
| option homogeneity | same category; correct answer not the longest by >X% | ➖ (warn) |
| source-leak | answer phrase is not a verbatim span of `source_text` | ✅ |
| answer-position balance | across a run, key position ~uniform (detect "always C") | run-level |

### Stage B — LLM judge (different family) · ~65% of A-survivors

Scores the taxonomy `quality_checks`
([`apush_question_archetypes.json`](../../taxonomy/apush_question_archetypes.json))
+ the spec rubric (0/1/2): **Spec adherence, Distractor craft, Outside-knowledge/
skill-fit.** Disqualifying if any: `requires_outside_knowledge` fails
(paraphrase), `every_distractor_named_trap` fails (filler), `single_best_answer`
fails, `skill_matches_command_phrase` fails. Reports **historical-accuracy** +
**single-best** as `key_valid` (the SC-KEY signal). The `single_best` and
`requires_outside_knowledge` checks are the dominant killers here.

### Stage C — Key-verifier (third family + probe) · ~72% of B-survivors

- **k-of-n independent solve:** a third-family model solves the item **n=3**
  times without the intended key; keep only if it selects the keyed option
  **≥2/3** (self-consistency vote).
- **Double-correct probe:** ask "is *more than one* option defensibly 'most
  directly' correct?" — reject on yes (catches the SC-KEY double-key tail the
  date-check cannot).
- **Human spot-check (P3):** a random ≥30-item slice per batch is human-audited
  for historical accuracy (LLM judges themselves err on history facts — [`02`](../02_litmus_test_prompt.md) §4b).

### SC-KEY targets per archetype

| Archetype | Raw model `key_valid` (pre-verifier) | Production (post-verifier) |
| :--- | :---: | :---: |
| `CAUSE_OF_SOURCE` | **≥ 0.80** | **≥ 0.92** |
| `EFFECT_OF_SOURCE` | **≥ 0.80** | **≥ 0.92** |
| `CONTEXT_SITUATION` (stretch) | ≥ 0.85 | ≥ 0.93 |

Raw ~0.80 matches the feasibility SC-KEY ceiling at 4B (§2); the verifier lifts
production to ≥0.90. **If raw stays <0.85 after v2 data iteration AND the verifier
is on → kill-criterion "RETHINK scope"** (§8, feasibility §5).

---

## 5. TWO eval instruments (do not conflate)

### 5A. LITMUS run — the BUILD gate (BEFORE any training)

Runs [`02_litmus_test_prompt.md`](../02_litmus_test_prompt.md) exactly: the
maximal [`litmus_generation_prompt.md`](../../prompts/litmus_generation_prompt.md)
over the **15 frozen LITMUS sources**, 6 items/source, **3 runs** (temp ≈ 0.7),
across Qwen3-{0.6B,1.7B,4B}-Instruct **and** the frontier teacher, with/without
few-shot. **Its job is to confirm the preconditions, not to train anything.**

| Gate | Metric | Threshold | Flips to if failed |
| :--- | :--- | :--- | :--- |
| **P1** | frontier teacher expert-grade **and** `key_valid_rate` | **≥ 70–75%** | `key_valid` <70% → **RETHINK** (no clean labels) |
| **P2** | prompted base **4B** expert-grade | **≤ 45–55%** | ≥80% → **DON'T BUILD**; 55–80% → narrow further |

Output: `docs/02b_litmus_results.md` (artifact A5) with pass-rate + `key_valid_rate`
by model × archetype. **The single most decision-relevant number is the frontier
teacher `key_valid_rate` on the causation pair** (feasibility §5). No training
step happens until P1 ∧ P2 hold.

### 5B. Product eval — base-vs-tuned (the required win)

Base = **same** Qwen3-4B-Instruct prompted with the maximal litmus prompt (the
honest bar, per feasibility §1). Tuned = the QLoRA model. Both generate on the
**~18 EVAL_HELDOUT sources** (disjoint per §3.2), **6 items/source, 3 runs**,
same judge + key-verifier as training.

| Success target | Metric | Bar |
| :--- | :--- | :--- |
| **Reliability** | tuned expert-grade pass rate | **≥ 80%** |
| **Delta over base** | tuned − base pass rate | **≥ +25 pts**, and **bootstrap 95% CI lower-bound > 0** |
| **Variance reduction** | run-to-run std (tuned vs base) | tuned **std ≤ 5 pts** and **< base std** |
| **Per-archetype** | `CAUSE_OF_SOURCE`, `EFFECT_OF_SOURCE` each | **≥ 78%** |
| **SC-KEY** | `key_valid_rate` (production, verifier-on) | **≥ 90%** |
| **Ablation** | verifier-off vs verifier-on key correctness | report the lever's size |

Report **mean per rubric dimension, base vs tuned**, + an error-analysis
paragraph (spec Appendix A). Bootstrap CIs (≥1,000 resamples) over items. A tuned
model that beats base on **Spec adherence + Consistency** is the win the spec
names; **do not** stake the project on beating a *prompted frontier* (feasibility
§1 secondary bar).

---

## 6. Training config (Unsloth QLoRA)

| Knob | Value | Rationale |
| :--- | :--- | :--- |
| Base | `unsloth/Qwen3-4B-Instruct-2507` | 4B clears the reliability cliff (feasibility §2 [arith-2025]); the **Instruct/non-thinking** variant is the pick for a deterministic JSON emitter. |
| Quantization | 4-bit NF4 (QLoRA), bf16 compute | fits one 24–40GB GPU; the spec's named recipe. |
| LoRA | **r=16, α=32**, dropout=0 | small, narrow distribution → modest rank avoids overfitting; α=2r. |
| Target modules | `q,k,v,o,gate,up,down_proj` | standard Unsloth full-attention+MLP coverage. |
| Epochs | **2–3** (early-stop on held-out pass rate) | ~1.6k items is small; >3 epochs risks memorizing keys (contamination risk). |
| LR / sched | 2e-4, cosine, 5–10% warmup | Unsloth QLoRA default band. |
| Batch | effective **16–32** (micro-batch × grad-accum) | stability on a small set. |
| Max seq len | **2048** | source + JSON object fit comfortably. |
| **enable_thinking** | **False** (train & infer identically) | thinking adds output variance/latency and risks the mode-dependent format collapse [arith-2025]; a JSON item needs no visible CoT. If a later ablation wants reasoning, distill it into `answer_dating`, not a `<think>` block. |
| **Loss masking** | **assistant JSON only** (`train_on_responses_only`) | never train on the prompt/source; learn the *emission*, per §3.4. |
| Artifacts | LoRA adapter + merged 16-bit + optional GGUF Q4_K_M | adapter for reproducibility; merged/GGUF for the HF demo. |

Fixed seed; log to Trackio/W&B. Save the base-vs-tuned generation configs
(temp, top-p) identical so the comparison is fair.

---

## 7. Inference verifier (reject-and-regenerate)

**Same `verifier.py` as the training filter** (one source of truth — the spec
rubric = data-gen rubric = eval criterion = inference guard). At serve time:

```
generate item  →  Stage A programmatic (JSON, date-check, trap-diversity,
                   absolute-words, source-leak, homogeneity)
   ├─ fail → regenerate (≤ k=4 tries; on repeated fail, return best + flag)
   └─ pass → Stage B/C-lite: judge single-best + programmatic date-check
        ├─ fail → regenerate
        └─ pass → emit item + verification receipt
```

- **Programmatic date-check** is always on (free, deterministic, catches
  wrong-era). The **judge single-best** pass is the SC-KEY guard that the
  date-check cannot cover; it can run as the same different-family judge or a
  cheaper distilled check for latency.
- The verifier **rejects and regenerates** rather than silently emitting — this
  is what converts SC-KEY from a liability into a *gated* output (P4). The
  inference demo (HF Space) exposes the receipt so a user sees *why* an item
  passed (the "expert-made feel" the Brainlift claims).

---

## 8. Iteration strategy — fix failures in DATA, not hyperparameters

Spec law (Rules/traps): *"Don't tune hyperparameters to fix a data problem."*
Every eval failure routes to a **data** change; hyperparameters stay fixed after
M3 unless a run is diverging.

| Failure mode | Eval symptom | Root cause in DATA | Data fix (v2) |
| :--- | :--- | :--- | :--- |
| **Double-key** ("most directly" ambiguous) | `key_valid` / single-best low | training set had subtle double-keys the judge passed | tighten key-verifier to 3/3; add contrastive `scope_mismatch` pairs (specific vs background); expand developments table to disambiguate |
| **Wrong-era key** | date-check fail | grounding not enforced / table gaps | enforce table-selection; expand table coverage (A3); add wrong-era hard negatives |
| **Filler distractor** | distractor-craft = 0 | trap distribution skewed / homogeneous | rebalance trap mix; oversample `true_but_irrelevant` + `scope_mismatch` (the hard traps); add DPO negatives |
| **Echoes source** (paraphrase) | `requires_outside_knowledge` fail | weak outside-knowledge items slipped in | raise `reasoning_hops` floor; judge harder on paraphrase; drop 1-hop items |
| **Broken JSON** | programmatic fail | too few schema-consistent examples / thinking leaked | more examples; confirm `enable_thinking=False`; loss-on-JSON-only |
| **Collapses on terse/adversarial notes** | robustness dim low, clean ≫ messy | training lacked terse/multi-development inputs | add terse note-seeds + multi-development sources (still in-scope) → matches kill-criterion "NARROW inputs" |

Each v2 cycle resolves **one** named failure mode and re-runs 5B (the spec's Day-4
exit). Document the story for the Brainlift (e.g., "scope-mismatch under-represented
→ added in data → double-key rate −N pts").

---

## 9. Stretch ladder (only after the core arc clears)

Per spec order (DPO + adversarial are the natural first two):

1. **DPO from filter negatives.** The trap-labeled rejects (§3.5, ~2,800) are a
   ready preference set: pair each kept item (chosen) with a matched reject
   (rejected) on the same stimulus+archetype. Target ~500–800 pairs; run DPO on
   the SFT adapter; measure whether spec adherence / `key_valid` sharpens **beyond
   SFT** ([ccot] fallacy-labeled negatives added +12.5%).
2. **Adversarial / robustness eval.** A hard set designed to break the behavior:
   terse fragments, multi-development sources, near-miss developments one year off
   the boundary (stress the date-check), decoys that tempt double-keying. Report
   robustness under attack vs clean.
3. **Add `CONTEXT_SITUATION`** (the sanctioned 3rd archetype; feasibility §3a).
   Re-run 5B for the 3-archetype scope (expected ~89% — below the 2-archetype
   91%, hence a *stretch*, not v1).
4. **F5 crown jewel later** (`EVIDENCE_SUPPORTS_CLAIM`) — highest expert-feel,
   needs secondary-source stimuli + a support-vs-undermine judge; explicitly a v2+
   research rung, not this build (feasibility §3b marks F5 OUT of v1).

---

## 10. Milestones M0–M6 (one-week arc + stretch)

| # | Day | Focus | Exit criterion (gradeable) |
| :--- | :--- | :--- | :--- |
| **M0** | 1 | Setup, research, Brainlift | Qwen3-4B-Instruct runs inference locally; **teacher ToS confirmed** (Deliverable 5 §4.2); `data/splits.json` drafted (A1); Brainlift spiky POV written & matches target behavior. |
| **M1** | 2 AM | Harness + pipeline + smoke test | Full loop **generate → filter → train → eval** runs end-to-end on **50 junk examples**; `verifier.py` + eval harness scaffolded (A2). |
| **M2** | 2 PM | **LITMUS build-gate** | `docs/02b_litmus_results.md` (A5) shows **P1 (teacher ≥70–75% + key_valid ≥70–75%)** and **P2 (base ≤45–55%)** → BUILD; else kill/RETHINK. **No training before this passes.** |
| **M3** | 3 | v1 dataset + first real numbers | Midweek gate: ~700 kept items (A3/A4 in place), first QLoRA run done, **base-vs-tuned numbers on the board**; tuned > base on Spec adherence. |
| **M4** | 4 | v2 dataset (data iteration) | **One** specific failure mode (§8) resolved *in data*; retrain; report the improvement (e.g., `key_valid` +N pts) with the delta CI. |
| **M5** | 5 | Ship & defend | Final 5B eval + error analysis; **dataset published**; **model on HF + inference demo (verifier-on)**; **eval harness + base-vs-tuned results table**; **Brainlift final**; **3–5 min demo video** showing what the base fails at. All §1 win targets met or honestly reported. |
| **M6** | 5+ | Stretch | ≥1 rung of §9 (DPO or adversarial) produces a gradeable result. |

---

## Appendix A — Blocking artifacts & owners

| ID | Artifact | Blocks | Owner | Status |
| :--- | :--- | :--- | :--- | :--- |
| **A1** | `data/splits.json` (LITMUS/EVAL_HELDOUT/TRAIN, disjoint) | all gen + eval (P6) | data lead | **TODO** (Day 1) |
| **A2** | `slm/verifier.py` + `slm/eval_harness.py` (shared filter/eval/inference) | M1, M2, filtering, §7 | eng | **TODO** (Day 2) |
| **A3** | Corpus expansion to ~80–100 text primary stimuli (via `build_seed_corpus.py`; PD + CC-BY note-seeds, provenance segregated) | TRAIN/EVAL volume (P3) | data lead | **TODO** — current 22 stimuli insufficient |
| **A4** | `data/gold/` hand-verified few-shots (≥6/archetype, human-keyed) | prompt quality, judge calibration | historian review | **TODO** |
| **A5** | `docs/02b_litmus_results.md` | M2 build-gate (P1/P2) | eng | **TODO** (Day 2) |
| **A6** | Developments-table expansion (84 → ~150–200, dates re-verified vs OpenStax/Yawp) | date-check coverage, double-key disambiguation | historian review | **TODO** |
| **A7** | Teacher-ToS confirmation (outputs-for-training permitted) | any bulk gen | project lead | **TODO** (Day 1) |

## Appendix B — API / compute budget estimate (order-of-magnitude)

Assumes frontier ~\$3/1M in, ~\$15/1M out; SLM inference local. "AI costs are
covered" (spec) — this sizes effort, not a hard cap.

| Line | Volume | Est. cost |
| :--- | :--- | ---: |
| Teacher generation (final, incl. ~1.3× regen) | ~5,800 calls × (~2.5k in + ~0.6k out) | ~\$110 |
| Judge (Stage B, incl. 20% double-judge) | ~4,300 × (~2k in + ~0.3k out) | ~\$55 |
| Key-verifier (Stage C, n=3 solves) | ~2,600 × 3 × (~1.5k in + ~0.2k out) | ~\$45 |
| Litmus run (frontier gen + judge; SLMs local) | 270 gen + ~800 judge calls | ~\$35 |
| Product eval 5B (judge + verifier; gen local) | ~720 judge calls × 2 iterations | ~\$20 |
| Iteration slack (v2 regen, ablations, DPO gen) | — | ~\$60 |
| **Frontier subtotal** | | **~\$325** |
| GPU (QLoRA): 1× A100/H100, ~3–5 runs × ~1–2 h | Modal/RunPod ~\$2–4/h | **~\$40–80** |

**Total ≈ \$365–405**, dominated by teacher generation; comfortably within a
covered-cost, one-week build.

## Appendix C — Spec-compliance checklist

| Spec non-negotiable | Where satisfied |
| :--- | :--- |
| Dataset is the deliverable (published) | §3, §10 M5, A-artifacts |
| Eval built **before** training | §5A litmus at **M2**, before M3 training |
| Base-vs-tuned comparison mandatory | §5B, §1 win condition |
| QLoRA/Unsloth on a small open base | §6 (Qwen3-4B-Instruct) |
| No broad domains ("one target, one context") | §1 scope = causation pair only |
| Fix failures in DATA, not hyperparameters | §8 |
| Pick a behavior that **fails the prompt test** | §5A P2 (base ≤45–55%); kill if base ≥80% |
| Published dataset | §10 M5, A-artifacts |
| Model on HF + inference demo | §10 M5, §7 verifier-on demo |
| Eval harness + results table (base-vs-tuned) | §5B, A2 |
| Brainlift (thesis + evidence) | [`brainlift_draft.md`](brainlift_draft.md) → final M5 |
| 3–5 min demo video | §10 M5 |
| **Inherited:** grounding to developments table | §2, §3.3, §4 Stage A (P5) |
| **Inherited:** inference-time verifier in loop | §7 (P4) |
| **Inherited:** confirmed teacher `key_valid_rate` | §5A P1 (M2) |
| **Inherited:** text primary sources only (v1) | §3.2 (P7) |
| **Inherited:** no College Board content in pipeline | §3.2 sourcing (Deliverable 5 §3) |
| **Inherited:** MMLU high_school_us_history = EVAL-ONLY | not in TRAIN (Deliverable 5 §2) |
