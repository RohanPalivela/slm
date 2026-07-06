# Training Plan v1 — Notes → Expert-Grade MCAT MCQs (SLM)

> **Deliverable 4+ (the build plan).** Converts the binding feasibility verdict
> (`docs/03_feasibility_assessment.md`) into an execution-ready recipe. Scope,
> size, and the "verifier-is-a-precondition" rule are inherited, not re-litigated.
> This is the BRAINSTORMER's v1; a Validator will critique it.

```
┌─ PLAN AT A GLANCE ──────────────────────────────────────────────────────────┐
│ 1. GOAL   Fine-tune Qwen3-4B-Instruct (QLoRA/Unsloth) so a study NOTE →       │
│           one expert-grade MCAT MCQ, reliably, for exactly 2 archetypes.      │
│ 2. SCOPE  MECHANISM_PERTURBATION (anchor) + THEORY_PLUS_STUDY (value only);   │
│           qualitative-only (no arithmetic); answer-key verifier is required.  │
│ 3. DATA   ~2,500 raw/archetype → ~900 KEPT/archetype (~1,800) via programmatic│
│           gate → LLM-judge (7 checks) → independent answer-key verifier.      │
│ 4. EVAL   Built BEFORE training: held-out HUMAN notes + 30×2 paraphrase       │
│           novelty probe; base-vs-tuned on pass-rate AND run-to-run variance.  │
│ 5. WIN    Tuned expert-grade ≥75% and ≥+25 pts over prompted base, std ≤5 pts,│
│           verified key-correctness ≥98% in prod. Ship HF dataset+model+demo.  │
│ 6. NEXT   Stretch = DPO from the off-spec negatives filtering already yields. │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Fixed inheritances (do not re-decide):** base = `Qwen3-4B-Instruct`; scope =
`MECHANISM_PERTURBATION` + `THEORY_PLUS_STUDY`; qualitative items only (numeric
fingerprints are *given data*, never computed); a verification pass is a
precondition; the dataset is the deliverable; eval is built before training;
base-vs-tuned is mandatory; one target / one context (no broad domains); do not
tune hyperparameters to fix a data problem.

**Assets confirmed on disk (grounding the numbers below):** 82 first-principle
cards (biochem 15 / bio 14 / phys 13 / gen-chem 13 / psych 11 / o-chem 10 / soc
6); 60-concept taxonomy (7 topics); 169 OpenMCAT items, each with a rich
`explanation` = correct-reasoning + **per-choice A/B/C/D rationale** + a
**"Common mistake"** line (few-shot gold; ~26 mechanism-shaped, ~15 theory-shaped,
26 passage-length >300 chars); 1,417 flat MMLU items (negative "flat-recall"
exemplars); 30 paraphrase cards × 2 rewordings (transfer probe; card #1 is
literally competitive-inhibition kinetics — on-archetype).

---

## 1. Behavior Spec (the falsifiable gate)

**Spec (pass/fail, markable by a stranger):**

> *Given a study note that states a mechanism-with-a-control-point (for
> `MECHANISM_PERTURBATION`) or a theory-with-predictive-content plus a follow-up
> finding (for `THEORY_PLUS_STUDY`), the model returns exactly one valid JSON MCQ
> of the requested archetype in which (a) the tested principle is applied to a
> scenario **not stated in the note**; (b) **exactly one** option is fully correct
> and its key is **independently verifiable** with **no second defensible**
> option; (c) each of the three distractors is a **named error drawn from that
> archetype's closed menu**; and (d) options are homogeneous, contain no
> all/none-of-the-above, and the stem passes cover-the-options. The output is
> **PASS** iff all four hold; otherwise **FAIL**.*

This single spec is the data-gen rubric (§2–3), the eval criterion (§4), and the
inference guard (§6). It is the operationalization of the taxonomy's 7 quality
checks (`docs/01`, §7), narrowed to two archetypes.

**The two closed menus (what makes this SLM-feasible — structural determinacy):**

| Archetype | Correct answer is… | Closed distractor/label menu (each carries its own named error) |
| :--- | :--- | :--- |
| **MECHANISM_PERTURBATION** | a **label** mapped from a given qualitative fingerprint | `competitive` (Km↑, Vmax=) · `uncompetitive` (Km↓, Vmax↓) · `noncompetitive/mixed` (Km=/↑, Vmax↓) · `allosteric activation` (Vmax↑ / Km↓) · `dissociation-or-denaturation` (ruled out by a stated structural datum). *(For non-enzyme control points the menu is the analogous closed set: Le Chatelier shift left/right/none/rate-only; feedback up/down/no-effect/compensatory.)* |
| **THEORY_PLUS_STUDY** | an **evidential relation** between finding and claim | `supports` · `weakens (in-scope)` · `consistent-but-not-diagnostic` · `contradicts a *different* claim` · `requires a bounded revision`. Correct answer is a logical judgment, not a fact lookup; the signature trap is `consistent-but-not-diagnostic`. |

Because the answer is *selected from a named menu whose members each have a fixed
signature*, "distractor authoring" and "answer-key correctness" become
classification + rule-derivation (SLM strengths) rather than open invention (SLM
weaknesses). That is the entire feasibility thesis.

---

## 2. Data-generation pipeline

### 2.1 Models (decoupled on purpose)

| Role | Model (default; swappable within tier) | Why |
| :--- | :--- | :--- |
| **Teacher (generator)** | a frontier reasoning model, e.g. Claude-Opus-class | Establishes the clean-label ceiling; must clear ≥70% expert-grade in litmus (P1). |
| **Judge (7 checks + graded dims)** | a **different family**, e.g. GPT-class | Decorrelate blind spots from the teacher; avoids "teacher grades itself." |
| **Answer-key verifier (independent solver)** | a **third path**: different-family solver **+** deterministic rule-checker | The crux (SC5). Two independent signals, one of them non-LLM (see §3.3). |

> Decision: teacher ≠ judge ≠ verifier family wherever possible. If only two
> frontier families are available, teacher and verifier must differ; the judge
> may share the verifier family but runs a different prompt/temperature.

### 2.2 Seeds — where notes come from, and the contamination firewall

We deliberately make **eval seeds human-authored** and **most training seeds
teacher-authored**, so the eval measures transfer to *human* notes (harder,
honest). Splits are frozen in `data/splits.json` before any generation.

| Seed pool | Source | Count | Role |
| :--- | :--- | :--- | :--- |
| **EVAL-heldout** | 82 FP cards, stratified holdout across both archetypes' concepts | **20** | primary held-out eval notes (never a training seed) |
| **EVAL-paraphrase** | `speedrun_paraphrase.json` | **30 (×2)** | novelty/transfer probe (§4.2) |
| **EVAL-adversarial** | teacher-authored terse/abbrev + multi-concept notes | **10** | robustness rung (§4.5) |
| **TRAIN-human** | remaining FP cards | **62** | training seeds (the `back` field = the note) |
| **TRAIN-synthetic** | teacher writes principle-notes styled on the FP `back`, keyed to the 60-concept taxonomy for the in-scope concepts | **~300** | training seeds; dedup vs all eval pools |

**Firewall (all enforced programmatically):** (1) the 20 EVAL-heldout cards and
30 paraphrase items are on a blocklist; (2) every generated training stem/note is
embedded and dropped if cosine ≥ **0.90** to any eval note, paraphrase `card_back`,
or paraphrase reworded stem; (3) train-synthetic notes are generated only for
concepts, then deduped against eval; (4) exact + near-dup dedup *within* train too
(§3.1). We report the tightened-threshold ablation in §9-R2 to prove gains aren't
contamination.

**In-scope concepts (from the 60-concept taxonomy).** MECH_PERT: enzyme-regulation,
glycolysis, oxidative-phosphorylation, bioenergetics, acid-base-equilibria,
kinetics-equilibrium, gas-phase, electrochemistry, membrane-transport, physiology
(feedback/homeostasis), circuits, thermochemistry (~12). THEORY_PLUS_STUDY:
evolution-ecology, associative-learning, social-psychology, theoretical-approaches,
social-class, culture-socialization, developmental-psychology, personality,
emotion-motivation, cognition-language, physiology-as-model, kinetics-equilibrium
(as Le Chatelier theory) (~12). ⇒ ~900 kept / ~12 concepts ≈ 60–75 items/concept
× {2 difficulties} × {scenario samples}.

### 2.3 The generation call (reuse the litmus prompt, add self-labeling)

Reuse `prompts/litmus_generation_prompt.md` **SYSTEM** verbatim but (i) restrict
the archetype list to the two in scope, (ii) request **one item per call** (not a
batch) for cleaner per-item control, (iii) add the **closed-menu self-labeling**
instruction and an explicit **`answer_derivation`** field, and (iv) keep the two
existing few-shots (they are already MECH_PERT + THEORY_PLUS_STUDY). The
Bohr/kinetics few-shots plus ~10 hand-verified gold THEORY items (bootstrapped
first, since native THEORY exemplars are thinner: ~15 vs ~26 mechanism) are the
few-shot bank.

**Self-labeling requirement (the key exploit).** The teacher must:
1. choose the correct menu member for the scenario it invents;
2. fill the other 3 options **from the same closed menu**;
3. for each option emit `{label, signature, verdict}` — e.g. MECH_PERT:
   `{"uncompetitive","Km↓ & Vmax↓","wrong: scenario shows Vmax unchanged"}`;
   THEORY: `{"consistent-but-not-diagnostic","finding also predicted by rival","wrong: the clamp result IS discriminating"}`;
4. emit `answer_derivation`: the ≤2-hop chain from the scenario fingerprint to the
   unique label (this is the supervised reasoning that makes SC5 rule-derivable).

**Scenario-novelty controls (the note must not be asked back):** the prompt fixes
rule 1 (familiar concept / unfamiliar scenario); a `scenario_slot` sampler forces
a *different instantiation* than any example in the note (different enzyme /
organism / follow-up finding); and a programmatic concept-leak + embedding-novelty
gate rejects note-echoes (§3.1). Difficulty is sampled from
`{operational, hard}` to spread rigor.

### 2.4 Exact training-example schema (chat format)

Production prompt is **short** (no few-shots) — baking the behavior in is the
whole point of fine-tuning. Loss is on the assistant turn only.

```json
// SYSTEM (compact, ~200 tokens): role + 7 rules + the 2 archetype menus + "Output ONLY the JSON object."
// USER:
"SOURCE NOTE:\n\"\"\"{{note}}\"\"\"\nArchetype: MECHANISM_PERTURBATION\nDifficulty: operational/test-day"
// ASSISTANT (the training target):
{
  "archetype": "MECHANISM_PERTURBATION",
  "concept": "enzyme-regulation",
  "stem": "<novel scenario with a qualitative fingerprint; passes cover-the-options>",
  "options": ["<menu member>", "<menu member>", "<menu member>", "<menu member>"],
  "answer": "A",
  "answer_derivation": "<=2-hop map: fingerprint -> unique menu label",
  "rationale": {
    "correct": "<one sentence>",
    "A": "correct",
    "B": "<named error: the exact misread/misconception>",
    "C": "<named error>",
    "D": "<named error>"
  },
  "unfamiliar_scenario": "<one line: why this is NOT a restatement of the note>",
  "reasoning_hops": 2
}
```

`answer_derivation` sits **inside** the JSON (not free-form CoT) so it is
parseable and gradeable, and so we can run Qwen3 in **non-thinking mode**
(structured reasoning beats long CoT for SLMs; dodges the arithmetic/CoT failure
mode). This is a deliberate output-design decision (flagged in the summary).

### 2.5 Target volumes (justified against the 200–1,000+ range)

| Quantity | Value | Justification |
| :--- | :--- | :--- |
| KEPT items / archetype | **~900** | Feasibility P3 (600–1,000); LoRA-Land effective range; enough for ~60–75/concept coverage. |
| KEPT total | **~1,800** | Two archetypes sharing one deep skill → mutually reinforcing, not diluting. |
| Split of kept | 800 train / 100 internal-dev **per archetype** | dev set is for loss/early-stop only; real eval is the separate human-note harness. |
| RAW generated / archetype | **~2,500** | to net ~900 kept at the ~36% end-to-end yield in §3.4. |

---

## 3. Quality gate / filtering (raw → kept)

Three stages, cheapest first. Every rejected item is **retained as an off-spec
negative** for DPO (§8).

### 3.1 Programmatic gate (free, deterministic)

| Check | Rule | Disqualifying |
| :--- | :--- | :--- |
| Schema/JSON | parses; exactly 4 options; one key ∈ {A,B,C,D}; all required fields present | ✅ |
| all/none-of-the-above | reject `/all of the above|none of the above/i` | ✅ |
| Menu conformance | every option ∈ the archetype's closed menu (MECH_PERT) / the 4 evidential relations are distinct (THEORY) | ✅ |
| Option homogeneity | length ratio max/min < **2.0**; correct answer not the longest by >**25%**; same grammatical category | ✅ |
| Concept-leak | answer phrase / menu label not verbatim in stem; ≤ **6-gram** overlap with the source note | ✅ |
| Scenario novelty | embedding cosine(stem, note) < **0.80**; and < 0.90 vs any eval artifact | ✅ |
| Surface tells | no absolute-word distractors ("always/never") that are trivially false; no lone round number | flag |
| Dedup / near-dup | exact hash + cosine ≥ **0.92** within the kept set | ✅ |
| Answer-position balance | across the kept batch: no position >**35%** or <**15%** (χ²); rebalance by resampling | batch-level |
| Label balance | correct-answer label distribution ≈ uniform across the menu (no member >**40%**) | batch-level |

### 3.2 LLM-judge (7 disqualifying checks + 3 graded dims)

Judge = different family than the teacher. Per item, score each `docs/01` §7
disqualifying check pass/fail, plus the litmus graded dims on 0/1/2:

| Dimension | 0 | 1 | 2 |
| :--- | :--- | :--- | :--- |
| Spec adherence | violates ≥1 disqualifying check | minor wobble | fully expert-grade |
| Distractor craft | ≥1 filler/implausible option | mixed | every distractor a named menu error |
| Scenario novelty | asks the note back | partial reframe | genuinely new scenario |

`expert_grade(item)` = **all disqualifying checks pass AND every graded dim ≥ 1
AND spec-adherence = 2.** Judge reliability: 20% double-judged (report agreement);
50-item human spot-check per archetype before trusting the judge.

### 3.3 Answer-key VERIFICATION (SC5 — the crux; three independent signals)

An item is key-valid only if **all** pass:
1. **Independent solve + self-consistency:** a different-family solver receives
   `stem + options` (no key), votes **k=5** at temp 0.7; keep only if
   majority = teacher's key **and** margin **≥ 4/5**. Catches wrong-key.
2. **Double-correct probe:** verifier asked "is more than one option defensible?
   list all." Reject if ≥2 flagged. Catches second-correct.
3. **Deterministic rule-checker (MECH_PERT only):** parse the stated qualitative
   fingerprint (Km/Vmax direction words, %-tetramer datum, ΔpH) → look up the
   unique menu label in a hand-built truth table → assert `key == table[fingerprint]`.
   A **non-LLM** guarantee for the anchor archetype. THEORY_PLUS_STUDY has no
   symbolic rail → it leans on (1)+(2) with a stricter margin (≥5/5) *(flagged)*.

### 3.4 Expected yield (funnel, per archetype)

| Stage | In → Out | Pass rate | Rationale |
| :--- | :--- | :---: | :--- |
| Raw generated | 2,500 | — | teacher, one item/call |
| Programmatic gate | 2,500 → 2,000 | 80% | JSON/menu/leak/dup are mostly clean from a frontier teacher |
| LLM-judge (7 checks) | 2,000 → 1,150 | 58% | novelty + distractor-craft are the real cullers |
| Answer-key verifier | 1,150 → 900 | 78% | SC5 rejects wrong/double keys; stricter on THEORY |
| **KEPT** | **900** | **~36%** | matches "filter hard; quality > volume" |

If yield < 900, generate another batch (do **not** relax gates). If THEORY yield
is structurally lower, accept an asymmetric dataset (e.g., 900 MECH / 700 THEORY)
rather than lowering the bar.

---

## 4. Eval harness (built BEFORE training)

Built and frozen on Day 2. Also serves as the litmus run that confirms
preconditions P1/P2 *before* a single training step.

### 4.1 Held-out note set (no leakage)

20 EVAL-heldout human FP cards (≈10 per archetype's concept mix) + 10
EVAL-adversarial notes. These notes never seed training (§2.2 firewall).

### 4.2 Paraphrase transfer / novelty probe (30×2)

For each of the 30 paraphrase `card_back` principles: feed as a note → model
generates an item → judge checks (a) **fidelity**: the item tests that principle;
(b) **novelty**: scenario differs from the card AND from *both* provided
rewordings (cosine < 0.80). This is the direct measure of "familiar concept /
unfamiliar scenario." Target: fidelity ≥ 90%, novelty ≥ 90%.

### 4.3 Judge rubric & metrics

Same rubric as §3.2 **plus** answer-key correctness via the §3.3 independent
solver. Metrics per model: **pass rate** (fraction `expert_grade`, primary);
mean per graded dim; **answer-key correctness** (tracked separately — the crux);
per-archetype and per-concept breakdown.

### 4.4 Base-vs-tuned protocol (mandatory)

| Arm | Prompt | Purpose |
| :--- | :--- | :--- |
| **Base** | Qwen3-4B + **maximal litmus prompt** (full spec + few-shots) | the "a good prompt already does it?" ceiling for the base |
| **Tuned** | Qwen3-4B(SFT) + **short production prompt** (no few-shots) | the "data bought reliability" claim |
| **Tuned-ablation** | Tuned + maximal prompt | isolates SFT effect from prompt effect |
| *(context)* Frontier | teacher + maximal prompt | secondary "rival frontier" bar (not required) |

**Reliability = pass-rate AND variance:** 3 runs at temp 0.7, different seeds;
report mean ± std of pass rate, and the fraction of notes where **all 3 runs**
pass (all-pass rate). Reliability, not peak, is the deliverable.

### 4.5 Adversarial / robustness rung

Attack notes designed to break the behavior: terse abbreviation-heavy fragments;
multi-concept paragraphs (does it pick one coherent target?); notes that bait
note-echo; notes that bait arithmetic (must stay qualitative). Report clean vs
under-attack pass rate.

### 4.6 Exact success targets

| Metric | Base (expected) | Tuned target | Gate |
| :--- | :---: | :---: | :--- |
| Expert-grade pass rate (held-out) | ~35–50% | **≥ 75%** | **required**; and **≥ +25 pts** over base |
| Run-to-run std | ~10–15 pts | **≤ 5 pts** | required (tuned ≤ base) |
| Answer-key correctness (raw model) | ~60–75% | **≥ 90%** | crux |
| Answer-key correctness (with §6 verifier, "production") | — | **≥ 98%** | crux |
| Paraphrase novelty / fidelity | — | **≥ 90% / ≥ 90%** | required |
| Per-archetype pass rate | — | **both ≥ 70%** | required |
| Robustness (under-attack) pass rate | — | **≥ 60%** | reported (v2 target) |

---

## 5. Training config (Qwen3-4B-Instruct + Unsloth QLoRA)

Starting points; change **only** via principled sweeps, never to paper over data.

```python
# Unsloth QLoRA — Qwen3-4B-Instruct
model, tok = FastLanguageModel.from_pretrained(
    "unsloth/Qwen3-4B-Instruct", load_in_4bit=True,   # NF4, double-quant, bf16 compute
    max_seq_length=2048)
model = FastLanguageModel.get_peft_model(
    model, r=16, lora_alpha=32, lora_dropout=0.05,
    target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"],
    use_gradient_checkpointing="unsloth", random_state=3407)
# TRL SFTTrainer args:
#   per_device_train_batch_size=8, gradient_accumulation_steps=4   # eff. 32
#   learning_rate=2e-4, lr_scheduler_type="cosine", warmup_ratio=0.03,
#   weight_decay=0.01, num_train_epochs=3, optim="adamw_8bit",
#   packing=True, bf16=True, seed=3407
# train_on_responses_only(...) -> loss masked to the assistant JSON only
```

| Item | Value | Note |
| :--- | :--- | :--- |
| Chat template | Qwen3 ChatML; **enable_thinking=False** | structured `answer_derivation` replaces CoT |
| max_seq_len | 2048 | longest passage-note ≈ 500 tok; item ≈ 400 tok → fits |
| Epochs | 3 | ~1,600 train ex; early-stop on internal-dev expert-grade proxy |
| Eff. batch | 32 (8×4) | scale to VRAM |
| First sweep knob (if underfit) | r 16→32 | then epochs, then lr — never to mask data issues |
| VRAM / runtime | 1×A100-80GB (or H100): peak ~18–22 GB, ~20–40 min/epoch → **~1–1.5 hr/run**; fits 40/24 GB with smaller batch | single-GPU per spec |

---

## 6. Inference-time verification pass (makes SC5 safe in production)

The tuned model is wrapped in a **reject-and-regenerate** loop that reuses the
**exact §3.3 verifier module** (shared code path — the filter *is* the guard):

```
generate item  ->  §3.1 programmatic gate  ->  §3.3 verifier (solve+SC, double-correct,
                                                MECH_PERT rule-checker)
   PASS  -> return item
   FAIL  -> regenerate (up to K=3, temp bumped, optional "you failed check X, fix it")
   still FAIL after K -> abstain / return best-scored candidate flagged "unverified"
```

- Lifts raw key-correctness (~90%) to **≥98%** in production because wrong/double
  keys are caught and re-rolled.
- Cheap path first: programmatic gate + MECH_PERT rule-checker are free; the
  frontier solver is invoked only for items that pass those (and always for
  THEORY, which lacks a symbolic rail).
- Demo exposes a toggle so the video can show verifier-off (occasional bad key) vs
  verifier-on (clean) — concrete proof the guard matters.

---

## 7. Iteration strategy (v1 → v2 — fix in the DATA)

Loop: eval error-analysis → bucket failures by (check failed × archetype ×
concept) → **fix the data distribution** → regenerate/rebalance → retrain →
re-eval. Hyperparameters are frozen unless a controlled test shows clean data +
under/overfit.

| Observed failure mode | Root cause | **Data fix (not hyperparams)** |
| :--- | :--- | :--- |
| Model keys "competitive" far too often | label imbalance / menu collapse | rebalance kept set to ~uniform correct-label; add items where competitive is a *distractor* |
| THEORY never selects "consistent-but-not-diagnostic" | that slot under-represented | oversample items whose correct answer is the not-diagnostic trap (calibration) |
| "Asks the note back" on terse notes | few messy seeds; low-novelty training items | add EVAL-adversarial-style messy seeds to TRAIN; up-weight novelty=2 items |
| Wrong key on 2-hop items | weak derivations in targets | keep only verifier-margin-5/5 items; strengthen `answer_derivation` supervision |
| Homogeneity fails (correct = longest) | teacher verbosity bias | length-normalize options in gate; regenerate offenders |

**Worked example.** v1 eval shows MECH_PERT pass 82% but THEORY 61%, and THEORY's
miss is 70% "trivially confirms/refutes, no not-diagnostic trap." *Fix:* raise
the not-diagnostic correct-answer share from ~20%→35% in the THEORY training set
and add 120 items with confound-laden findings; retrain. Expected v2: THEORY →
~72%+, with no hyperparameter change.

---

## 8. Stretch ladder

1. **DPO / preference tuning (first rung).** Reuse the off-spec negatives the
   filter already produces: pair `chosen` = a verified expert-grade item with
   `rejected` = a same-note/same-archetype item that failed (wrong key, filler
   distractor, or note-echo). ~1,500–3,000 pairs. DPO on top of SFT
   (β=0.1, lr 5e-6, 1 epoch). Measure Δ expert-grade and Δ key-correctness vs SFT
   alone (contrastive fallacy-labeled negatives are documented to sharpen exactly
   this).
2. **Adversarial / robustness eval.** Promote §4.5 to a graded rung: report
   pass-rate under attack (note-echo bait, arithmetic bait, malformed notes).
3. **Composed behavior (hardest).** Add a genuinely competing constraint:
   *include a numeric fingerprint as given data yet keep the item
   qualitatively-solvable (never require arithmetic)* — numbers present but not to
   be computed. Show the model holds format + novelty + this tension at once.

---

## 9. Risk register

| # | Risk | Mitigation | **Kill-criterion → action** |
| :--- | :--- | :--- | :--- |
| R1 | **SC5**: wrong or double-keyed answer (the crux) | symbolic + self-consistency verifier in filter **and** inference; strong `answer_derivation` supervision | tuned key-correctness **<85%** after v2 **and** with verifier → **RETHINK scope**: drop to MECH_PERT-only, add retrieval, or switch output unit to "grade/repair an item" |
| R2 | Seed/eval **contamination** inflates gains | human held-out eval, cross-split near-dup gate, paraphrase blocklist | eval gain **collapses when dedup threshold tightened** (0.90→0.80) → gains are artifacts; rebuild splits |
| R3 | **Mode collapse** to one distractor/label | label- & position-balanced sampling; coverage tracking | any menu member **>40%** of correct keys in kept/eval → rebalance data |
| R4 | **Teacher-ceiling** failure (no clean labels) | litmus run **before** training (P1) | teacher **<70%** expert-grade on the two archetypes → **RETHINK**: supply data object, retrieval grounding, or MECH_PERT-only |
| R5 | **Litmus fails** (prompt already suffices) | run prompted base 4B in litmus (P2) | base 4B **≥80%** expert-grade → **DON'T BUILD**; ship the prompt |
| R6 | **Messy-note collapse** (SC6) | clean-note v1; adversarial rung deferred | tuned strong on clean but collapses on messy → **NARROW inputs** to clean cards for v1 |
| R7 | Judge unreliable / teacher==judge correlation | different families; 20% double-judge; 50-item human check | judge–human agreement **<0.8** → revise rubric/judge model |
| R8 | Overfit to 82 seeds | synthetic-note expansion; dedup; early-stop | large train–eval gap **and** low eval novelty → expand/di­versify seeds |

**Single most decision-relevant result:** whether the frontier **teacher** clears
≥70% expert-grade on the two archetypes in the litmus run. Teacher-can +
base-can't = textbook distillation BUILD; teacher-can't = RETHINK before spending
a GPU-hour.

---

## 10. Milestones (mapped to the one-week arc & final package)

Sequenced for **structure/coverage, not speed**. Arc day in brackets.

| M | Milestone | Exit checkpoint | Spec day |
| :--- | :--- | :--- | :---: |
| **M0** | Env + repro: base Qwen3-4B runs inference; assets loaded; `data/splits.json` frozen | base model responds; splits + firewall in place | D1 |
| **M1** | Behavior spec frozen; **eval harness built**; **litmus run** (teacher + prompted base 4B) | P1 (teacher ≥70%) & P2 (base ≤~45–55%) confirmed → BUILD greenlit | D1–D2 |
| **M2** | Data-gen + 3-stage quality gate + verifier coded; **50-item junk smoke** through generate→train→eval | full loop runs end-to-end | D2 |
| **M3** | v1 dataset (~1,800 kept, funnel logged); first QLoRA run; **first base-vs-tuned eval** | **midweek gate: base-vs-tuned numbers on the board** | D3 |
| **M4** | Error analysis → **v2 data fixes** → retrain → improvement report | **one failure mode resolved via data** (e.g., THEORY not-diagnostic) | D4 |
| **M5** | Inference demo w/ reject-&-regenerate; final eval + results table; robustness rung | tuned meets §4.6 gates | D5 |
| **M6** | **Publish**: dataset + model to HF Hub; brainlift ("data→behavior held?"); 3–5 min demo video | final submission package complete | D5 |
| **M7** | Stretch: DPO from filter negatives → adversarial eval → composed behavior | each a standalone gradeable result | post |

**Final package (spec §"Final submission"):** (1) the **dataset**, published on HF
(the real artifact); (2) the **model** on HF Hub + running inference demo with the
verifier; (3) **eval harness + results table** (base vs tuned, expert-grade pass
rate + variance + key-correctness); (4) **brainlift** (behavior thesis + evidence
data→behavior held); (5) **demo video** showing the tuned model reliably doing
what the prompted base fails to do.

---

## Appendix A — Frozen artifacts to create

- `data/splits.json` — the seed firewall (eval-heldout 20, paraphrase 30,
  adversarial 10, train-human 62, train-synthetic ~300) + blocklist hashes.
- `data/mcat_slm_v1.{train,dev}.jsonl` — chat-format items (§2.4 schema).
- `data/negatives.jsonl` — off-spec rejects for DPO (§8).
- `eval/harness.py` — programmatic gate + judge + independent-solver verifier
  (shared with `infer/verify.py`).
- `eval/truth_tables/mech_pert.json` — the deterministic fingerprint→label table.
- `results/base_vs_tuned.md` — the mandatory results table.

## Appendix B — Compliance map (spec non-negotiables → where honored)

QLoRA SFT on small open base → §5. Dataset is the deliverable → §2–3, App-A.
Eval before training → §4, M1. Base-vs-tuned mandatory → §4.4, §4.6. No broad
domains → §1–2 (2 archetypes, ~12 concepts each). Don't fix data with
hyperparams → §5, §7. Verifier is a precondition → §3.3, §6, R1. Qualitative-only
→ §1, §2.3, §5 (non-thinking), R-arith. Stack = Qwen3 + Unsloth QLoRA + single
A100/H100 → §5. Stretch = DPO/adversarial/composed → §8.
