# Training Plan v2 — Primary Source (+ optional study note) → Expert APUSH Causation MCQs (SLM)

> **Deliverable 4, v2 (BRAINSTORMER).** Revises [`plan_v1.md`](plan_v1.md) to
> clear the VALIDATOR verdict **REVISE (major)**
> ([`validator_feedback_v1.md`](validator_feedback_v1.md)). Every one of the 12
> approval criteria is addressed below (see §0 and the closing checklist).
> **Binding, not relitigated** ([`../03_feasibility_assessment.md`](../03_feasibility_assessment.md)):
> scope = `CAUSE_OF_SOURCE` (anchor) + `EFFECT_OF_SOURCE`; base = Qwen3-4B-Instruct
> (QLoRA + frontier distillation); ~91% conditional on grounding + verifier +
> confirmed teacher `key_valid_rate`; **SC-KEY** is the crux; the date-check is
> **necessary-not-sufficient**; `CONTEXT_SITUATION` = sanctioned first expansion
> (stretch). Companion: [`brainlift_draft.md`](brainlift_draft.md).
>
> **Kept from v1 (validator "keep these"):** one shared falsifiable boolean across
> gen/filter/eval/inference; two separated eval instruments; three model families;
> fix-in-data discipline; teacher-ToS gate; the spec-compliance checklist.

---

## 0. Changes from plan_v1 (validator fixes)

| # (issue) | Validator item | Resolution in plan_v2 |
| :--- | :--- | :--- |
| **1** (C1,M7) | Input contract inconsistent; notes not wired/eval'd | **Narrowed (option a):** input = *provided text primary SOURCE + OPTIONAL steering note*. Consistent across title, §2, §3.4, §5B, §7 demo. `{{NOTE}}` slot re-added to the gen prompt; note-conditioned items in TRAIN; **note-augmented slice in EVAL_HELDOUT + 5B**. Notes-only (note→source retrieval) = explicit **v2 rung** (§9). Inference requires `source_text + attribution + source_date`. |
| **2** (C2) | Grounding asserted, not enforced; free recall allowed | Gen prompt now **injects a period-windowed candidate set**; answer + all 3 distractors chosen **by `development_id`**; free-recall clause **removed**; Stage A **hard-rejects** any `development_id ∉ injected set`. **`prompts/data_gen_prompt.md` edited accordingly.** (§3.3, §4) |
| **3** (C3,M7) | Corpus 14 primary (not 22); splits/volume don't close | Corpus **sized by target-kept ÷ cap** (≤6/(stimulus,archetype)), not the funnel. **Primary-only** split counts (§3.2). v1 target reduced to the **600 floor** → ~110 TRAIN primary. Dedup now tracks **(development, archetype) novelty**. |
| **4** (C3,M4) | A3 not gated | **A3 (14 → ~150 primary, license-provenanced) is a HARD gate before M3** (§10); owners named. |
| **5** (C4) | Table too sparse to be the grounding set | **A6 (84 → ~150–200, dense mechanisms + background, `keyable` vs `distractor_only` roles) is a HARD gate before M3**; every TRAIN/EVAL stimulus verified to have ≥1 groundable most-direct CAUSE and EFFECT. |
| **6** (M1) | No calibration gate before bulk spend | New **BLOCKING calibration gate (G-cal, M2.5):** `data/gold/` (≥10/archetype); judge + key-verifier agreement vs gold **≥90%** on `key_valid` AND single-best; human slice audits double-key. |
| **7** (M2) | Item bootstrap over-optimistic | 5B uses a **source-level cluster bootstrap**; EVAL_HELDOUT **=28 disjoint primary sources**; win judged under that method. |
| **8** (M3) | SC-KEY kill conflates raw vs production | Kill = **production (verifier-on) SC-KEY < 85%** after v2; raw target ≥0.80 (not a kill trigger); "raw <0.85" wording **deleted**; §4 ↔ glance box reconciled. |
| **9** (M5) | Funnel yields assumed | New **yield-calibration batch (G-yield, M2.5):** ~150 REAL items → measured A/B/C yields → **re-derive** bulk volume + budget before the spend. |
| **10** (M4) | Timeline under-resources pre-M3 artifacts | **Re-sequenced:** A3+A4+A6 built Day 1–2, gated at M2.5; **M3 exit depends on them**; historian/legal owner named; v1 volume cut to fit the week. |
| **11** (M6) | Litmus P1/P2 on full instrument, thin causation N | Build gate computed on the **causation-pair subset** (litmus archetype list restricted to CAUSE/EFFECT on the 10 primary LITMUS sources): **~90 items/archetype/model**. |
| **12** | Preserve spec compliance | Re-confirmed in Appendix C (unchanged wins intact). |
| minor | glance WIN/+25; "840 margin"; dedup; infer-judge cost; DPO store | All folded in (§1, §3.2, §5B, §7, A8). |

---

## 1. Plan at a glance

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ GOAL       Reliably turn a provided text PRIMARY SOURCE (+ optional study      │
│            note) into an expert-grade APUSH stimulus-based MCQ, 2 archetypes.  │
│ INPUT      source_text + attribution + source_date (REQUIRED) + optional NOTE  │
│            that steers the target development. Notes-only path = v2 rung (§9).  │
│ SCOPE      CAUSE_OF_SOURCE (anchor) + EFFECT_OF_SOURCE. Text primary only (P7). │
│ BASE       unsloth/Qwen3-4B-Instruct-2507 (non-thinking), QLoRA 4-bit.         │
│ TEACHER    frontier (ToS-gated); Judge = DIFFERENT family; Key-verifier =      │
│            THIRD family + programmatic date-check.                              │
│ GROUNDING  Answer AND all 3 distractors chosen BY development_id from a         │
│            period-windowed candidate set INJECTED into the gen prompt; Stage A  │
│            HARD-REJECTS any ungrounded id (P5, mechanically enforced).          │
│ DATA       v1 target = 600 kept/archetype (P3 floor). Sized by target ÷ cap     │
│            (≤6 items/(stimulus,archetype)) → ~110 TRAIN primary stimuli. Bulk   │
│            volume + budget RE-DERIVED from measured yields at G-yield.          │
│ GATES      3-stage filter (programmatic → judge → key-verifier), reused at      │
│            inference. Calibration (G-cal) + yield (G-yield) BLOCK bulk gen.     │
│ EVAL       (A) LITMUS build-gate on the CAUSATION SUBSET, BEFORE training.      │
│            (B) base-vs-tuned on 28 held-out sources, 3 runs, SOURCE-CLUSTER     │
│            bootstrap; incl. a note-augmented slice.                             │
│ WIN        Tuned ≥80% expert-grade; delta ≥ +25 pts over prompted base with     │
│            source-cluster 95% CI lower-bound > 0; lower run-to-run variance;    │
│            both archetypes ≥78%; production key_valid ≥90%.                     │
│ KILL       Base ≥80% (DON'T BUILD) · teacher key_valid <70% (RETHINK) ·         │
│            production (verifier-on) SC-KEY <85% after v2 (RETHINK scope).       │
└──────────────────────────────────────────────────────────────────────────────┘
```

**One-week arc (re-sequenced):** Day 1 M0 (setup + Brainlift + **kick off A3/A6**)
· Day 2 M1 (harness/smoke) + M2 (**litmus build-gate, causation subset**) ·
**Day 2→3 M2.5 (BLOCKING: A3+A4+A6 done, G-cal, G-yield)** · Day 3 M3 (bulk gen +
first train + base-vs-tuned) · Day 4 M4 (data iteration) · Day 5 M5 (ship) · M6
stretch.

---

## 2. Behavior spec (falsifiable, one paragraph)

> Given a **provided, legally-sourced, date-tagged text PRIMARY SOURCE**
> (`source_text` + `attribution` + `source_date`) **and an OPTIONAL study note**
> (which, when present, steers *which* development to test; when absent, the model
> picks the best candidate for the stem), and a causation command phrase
> (`cause_of` → the answer is a CAUSE; `effect_immediate` → a short-term EFFECT),
> the model emits a **single strict-JSON APUSH stimulus-based MCQ** whose keyed
> answer is the **one development — chosen BY `development_id` from the
> period-windowed candidate set drawn from
> [`data/apush_key_developments.json`](../../data/apush_key_developments.json),
> never free-recalled — that (a) is DATE-CONSISTENT** with the stem's time
> direction (a cause dated strictly *before* `source_date`; an effect strictly
> *after*) **and (b) is the SPECIFIC, most-direct mechanism**, not a broad
> background condition and not a merely topical match; and whose **three
> distractors are each exactly one of the four named College Board traps**
> (`wrong_era`, `true_but_irrelevant`, `scope_mismatch`, `partially_true`), each
> also chosen by `development_id` from that set, spanning **≥2 distinct trap
> types**. **An item PASSES iff:** valid JSON, 4 homogeneous options, exactly one
> key; **every option's `development_id` is in the injected candidate set**; the
> key **requires outside knowledge** (not a paraphrase of the source) in **≥2
> reasoning hops**; the date-check holds **and** ≥1 distractor is a genuine
> `wrong_era` violation; and **exactly one** option is defensibly best (no
> distractor is *also* "most directly" correct). Any single violation FAILS the
> item — the identical boolean whether it is **generated** (data-gen rubric),
> **scored** (eval), or **served** (inference guard).

Same wording as [`brainlift_draft.md`](brainlift_draft.md) so thesis, data, and
metric cannot drift. The only v2 change vs v1 is that grounding is now **stated as
a mechanical `development_id` membership test**, not an aspiration.

---

## 3. Data generation

### 3.1 Model roles (three DIFFERENT families — anti-correlated errors)

| Role | Family | Job | Why distinct |
| :--- | :--- | :--- | :--- |
| **Teacher** | Frontier A | Generate the item (choosing answer + distractors by `development_id`) via [`data_gen_prompt.md`](../../prompts/data_gen_prompt.md) | Highest ceiling. **ToS precondition (A7): confirm outputs may train another model before any bulk gen.** |
| **Judge** | Frontier B | Score every disqualifying `quality_check` + rubric + single-best | Different family → uncorrelated blind spots. |
| **Key-verifier** | Frontier C **+ programmatic date-check** | Independently solve k-of-n; double-correct probe; deterministic date-check | SC-KEY needs an independent solver + a rule gate; the date-check is **necessary-not-sufficient**. |

### 3.2 Seeds, firewall & corpus sizing — `data/splits.json`

P6 firewall: **no `stimulus_id` in more than one partition.** Counts are
**primary-only** (the causation pair is text-primary; the 8 secondary seeds are
F5, OUT of v1 — validator M7).

**Corpus sizing is driven by the kept-item target and a hard per-source cap, NOT
by the raw-gen funnel (C3):**

```
cap  c      = 6 kept items per (stimulus, archetype)      # ≤6–8 band; 6 = conservative for SC-KEY
target K    = 600 kept per archetype                      # P3 floor (reduced from v1's 840 to fit the week; M4)
TRAIN_min   = ceil(K / c) = ceil(600/6) = 100  → budget 110  (10% for under-fill / non-groundable)
```

| Partition | Purpose | Primary sources | Notes |
| :--- | :--- | ---: | :--- |
| **LITMUS** | Build-gate only (§5A); never gen'd | **10** primary (+3 secondary +2 adversarial for the full instrument) | P1/P2 computed on the 10 primary × causation subset |
| **EVAL_HELDOUT** | Product eval only (§5B) | **28** primary | ≥25–30 for a stable source-cluster CI (M2); ≥6 themes; 8 also run **note-augmented** |
| **TRAIN** | Data generation only | **~110** primary | serves BOTH archetypes; cap 6/(stimulus,archetype) |
| **TOTAL required** | | **~148 (≈150)** | current corpus = **14 primary** → **A3 must build 14 → ~150** |

**Fallback if A3 slips** (still clears the 600 floor): raise cap to **8**, TRAIN
→ ~80, EVAL → 26, LITMUS → 10 (**≈116 primary**). If even that is unreachable by
M2.5, drop to **`CAUSE_OF_SOURCE`-only** (feasibility ~92%; same stimulus count,
half the gen volume).

- **Note-seeds / note-conditioning.** ~25–30% of TRAIN items are generated with an
  optional study note (CC-BY textbook prose paired to a PD stimulus) in the
  `{{NOTE}}` slot, so the model learns to *use* a note when present and ignore it
  gracefully when absent. Note-seeds inherit their stimulus's split (no leakage).
- **Dedup + contamination (minor fix).** Embed `(stimulus_id + stem + answer)`;
  drop intra-split cosine **≥0.92**; cross-split **≥0.90**. Because the key space
  is a finite table, ALSO report held-out **`(development, archetype)` novelty**
  (fraction of EVAL key-pairs unseen in TRAIN) as the real contamination metric —
  held-out *sources* are always unseen even when a development recurs.

### 3.3 Prompts (grounding now mechanical — C2)

Use the **edited** [`data_gen_prompt.md`](../../prompts/data_gen_prompt.md)
(v1-scope archetypes = {`CAUSE_OF_SOURCE`, `EFFECT_OF_SOURCE`}). The orchestrator:

1. For each `(stimulus, archetype)`, **injects `{{CANDIDATE_DEVELOPMENTS}}`** — a
   period-windowed slice of the table (rows: `development_id | name | year |
   period | role`), spanning the source's period ±1–2 so the set contains
   correct-direction **keyable** developments AND off-direction/off-era ones for
   the traps.
2. Requires the answer **and all 3 distractors** to be chosen **by
   `development_id`** from that set; the free-recall clause is **removed**; if no
   defensible key exists, the teacher returns `{"skip": true}` (logged, not a
   failure).
3. Passes `{{SOURCE_DATE}}` and the optional `{{NOTE}}`.

Seed with the `CAUSE_OF_SOURCE` litmus few-shot + hand-verified
`CAUSE`/`EFFECT` gold items (A4). One item (or one `SET_OF_THREE`) per call.

### 3.4 Training-example schema

```json
{
  "stimulus_id": "monroe_doctrine_1823",
  "source_text": "<verbatim stimulus>",
  "attribution": "President James Monroe, ... 1823",
  "source_date": 1823,                 // REQUIRED — anchors the date-check
  "note": "<optional steering note, or null>",
  "note_conditioned": false,
  "archetype": "CAUSE_OF_SOURCE",
  "stem_template": "cause_of",
  "period": 4, "theme": "WOR",
  "stem": "Which of the following contributed most directly to ...?",
  "options": ["...", "...", "...", "..."],
  "answer": "C",
  "answer_dating": "<keyed candidate's year + why it obeys the direction>",
  "options_meta": {
    "A": {"development_id": "<MUST be in the injected candidate set>", "verdict": "wrong_era|true_but_irrelevant|scope_mismatch|partially_true|correct", "why": "<named error>"},
    "B": {"...": "..."}, "C": {"...": "..."}, "D": {"...": "..."}
  },
  "trap_types": ["scope_mismatch", "wrong_era", "true_but_irrelevant"],
  "requires_outside_knowledge": "<the outside candidate the answer depends on>",
  "reasoning_hops": 2,
  "_prov": {"teacher": "...", "candidate_set_hash": "...", "judge_pass": true, "keyverify": {"votes": "3/3", "double_correct": false}}
}
```

**Model input** = `source_text + attribution + source_date + optional note +
candidate set`. **Training target** = `archetype … reasoning_hops` (loss on the
assistant JSON only, §6). `source_*`, `note`, `_prov` are context/bookkeeping.

### 3.5 Filter funnel (PLACEHOLDER — re-derived at G-yield, M5/M9)

Planning estimate only; **the bulk-gen volume and budget are re-derived from the
measured A/B/C yields of the G-yield calibration batch (§10 M2.5) before the full
spend.** Net keep ≈ 0.80 × 0.65 × 0.72 ≈ **0.39**.

| Stage | v1 target (kept ≈1,200 total) | Yield (placeholder) |
| :--- | ---: | :--- |
| Raw teacher generations | ~3,200 | — |
| After **Stage A** (programmatic incl. grounding hard-reject) | ~2,560 | ~80% |
| After **Stage B** (judge) | ~1,664 | ~65% of A |
| After **Stage C** (key-verifier) | **~1,200** (~600/archetype) | ~72% of B |
| Trap-labeled rejects → `data/rejects/` (A8, DPO pool) | ~2,000 | free byproduct |

Generation is **generate-to-target-with-cap** (stop a `(stimulus,archetype)` at 6
kept or a max-attempts ceiling), so spend is bounded even if yields sag.

---

## 4. Quality gate (3 stages)

Implemented once in `slm/verifier.py`, reused at inference (§7). Cheapest-first;
any disqualifying failure drops the item.

### Stage A — Programmatic (no API cost)

| Check | Rule | Disq? |
| :--- | :--- | :---: |
| valid JSON / schema | parses; required fields; 4 options; one key; `source_date` present | ✅ |
| **grounding membership (C2)** | **every `options_meta.*.development_id` ∈ injected candidate set** — else hard-reject | ✅ |
| `reasoning_hops ≥ 2` | integer ≥ 2 | ✅ |
| no absolute / all-none | regex `all of the above|none of the above|always|never` | ✅ |
| **anachronism date-check** | keyed id's year obeys direction (cause `< source_date`, effect `> source_date`) vs the table; ≥1 distractor genuinely `wrong_era` | ✅ |
| trap-diversity ≥ 2 | 3 distractors span ≥2 trap ids | ➖ |
| option homogeneity | same category; key not the longest by >X% | ➖ |
| source-leak | answer not a verbatim span of `source_text` | ✅ |

### Stage B — LLM judge (different family)

Taxonomy `quality_checks` + spec rubric (0/1/2: Spec adherence, Distractor craft,
Outside-knowledge/skill-fit). Disqualifying: `requires_outside_knowledge` (para-
phrase), `every_distractor_named_trap` (filler), `single_best_answer`,
`skill_matches_command_phrase`. Reports historical-accuracy + single-best as
`key_valid`. Dominant killers: single-best + requires-outside-knowledge.

### Stage C — Key-verifier (third family + probe)

- **k-of-n solve:** third-family model solves n=3 without the key; keep if it
  picks the keyed option **≥2/3**.
- **Double-correct probe:** reject if >1 option is defensibly "most directly"
  correct (the SC-KEY tail the date-check cannot see).
- **Human spot-check:** ≥30-item slice per batch audited for accuracy AND
  single-best/double-key (M1).

### SC-KEY targets & kill (reconciled — M3)

| Archetype | Raw `key_valid` (target, **not** a kill trigger) | Production (verifier-on, target) |
| :--- | :---: | :---: |
| `CAUSE_OF_SOURCE` | ≥ 0.80 | ≥ 0.92 |
| `EFFECT_OF_SOURCE` | ≥ 0.80 | ≥ 0.92 |
| `CONTEXT_SITUATION` (stretch) | ≥ 0.85 | ≥ 0.93 |

Raw ~0.80 matches the feasibility SC-KEY ceiling at 4B (§2) and is **acceptable**.
**KILL criterion (unambiguous): production (verifier-on) SC-KEY `< 85%` after v2
data iteration → RETHINK scope** (drop to `CAUSE`-only / candidate-set-only /
repair-grade output unit; feasibility §5). The prior v1 "raw <0.85 = kill" wording
is **deleted**; glance box and this section now agree.

---

## 5. TWO eval instruments (do not conflate)

### 5A. LITMUS build-gate — causation subset, BEFORE training (M6 fix)

Run [`litmus_generation_prompt.md`](../../prompts/litmus_generation_prompt.md)
with the **archetype list restricted to {`CAUSE_OF_SOURCE`, `EFFECT_OF_SOURCE`}**
over the **10 primary LITMUS sources**, **6 causation items/source (3 CAUSE + 3
EFFECT) × 3 runs = 180 items/model (~90/archetype)** — an adequate N for a stable
P1/P2 estimate. Models: Qwen3-{0.6B,1.7B,4B}-Instruct + frontier teacher,
with/without few-shot. (The 3 secondary + 2 adversarial sources still run for the
full litmus record but **do not feed P1/P2**.)

| Gate | Metric (causation subset) | Threshold | Fail → |
| :--- | :--- | :--- | :--- |
| **P1** | frontier teacher expert-grade **and** `key_valid_rate` | **≥ 70–75%** | `key_valid` <70% → **RETHINK** (no clean labels) |
| **P2** | prompted base **4B** expert-grade | **≤ 45–55%** | ≥80% → **DON'T BUILD**; 55–80% → narrow further |

Output `docs/02b_litmus_results.md` (A5). **No training until P1 ∧ P2 hold.** The
most decision-relevant number is the teacher `key_valid_rate` on the pair.

### 5B. Product eval — base-vs-tuned, source-cluster bootstrap (M2 fix)

Base = same Qwen3-4B-Instruct + maximal litmus prompt (honest bar). Tuned = the
QLoRA model. Both generate on the **28 EVAL_HELDOUT sources**, **6 items/source ×
3 runs** (504 items/model), same judge + key-verifier. **Of the 28, 8 sources are
ALSO run note-augmented** → report source-only and source+note separately (proves
the optional-note path works).

| Success target | Metric | Bar |
| :--- | :--- | :--- |
| **Reliability** | tuned expert-grade pass rate | **≥ 80%** |
| **Delta over base** | tuned − base | **≥ +25 pts**, and **source-cluster bootstrap 95% CI lower-bound > 0** |
| **Per-archetype** | `CAUSE`, `EFFECT` each | **≥ 78%** |
| **SC-KEY** | production `key_valid_rate` (verifier-on) | **≥ 90%** |
| **Note robustness** | source+note vs source-only pass rate | note slice **not worse** than source-only |
| **Variance** | run-to-run std (indicative only; 3 runs) | tuned < base |
| **Ablation** | verifier-off vs verifier-on key correctness | report the lever size |

**CI method (explicit):** resample the 28 **sources** with replacement, then items
within each sampled source (cluster bootstrap, ≥2,000 resamples) — effective N ≈ 28
clusters, not 504 items. Run-to-run std is reported but treated as indicative (3
runs is thin). Report mean per rubric dimension (base vs tuned) + an error-analysis
paragraph (spec Appendix A). Do **not** stake the project on beating a prompted
frontier (secondary bar).

---

## 6. Training config (Unsloth QLoRA) — unchanged from v1

| Knob | Value | Rationale |
| :--- | :--- | :--- |
| Base | `unsloth/Qwen3-4B-Instruct-2507` (non-thinking) | clears the reliability cliff [arith-2025]; deterministic JSON emitter |
| Quant | 4-bit NF4, bf16 compute | fits one 24–40GB GPU |
| LoRA | r=16, α=32, dropout=0 | narrow distribution → modest rank |
| Targets | `q,k,v,o,gate,up,down_proj` | standard Unsloth coverage |
| Epochs | 2–3, early-stop on held-out pass rate | small set → avoid key memorization |
| LR / sched | 2e-4 cosine, 5–10% warmup | Unsloth default band |
| Batch | effective 16–32 | stability |
| Max seq len | 2048 (source + candidate set + JSON fit) | — |
| `enable_thinking` | **False** (train & infer identically) | avoids mode-dependent format collapse; no visible CoT needed |
| Loss masking | assistant JSON only (`train_on_responses_only`) | learn the emission |
| Artifacts | LoRA adapter + merged 16-bit + optional GGUF Q4_K_M | reproducibility + HF demo |

Mix note-conditioned (~25–30%) and note-free items so the model handles both
inputs. Fixed seed; identical base/tuned generation configs for a fair 5B.

---

## 7. Inference verifier (reject-and-regenerate)

**Same `slm/verifier.py` as the training filter.** The HF demo **requires
`source_text + attribution + source_date`** and accepts an **optional note**
(matching the trained input contract — C1). The orchestrator injects the same
period-windowed candidate set at serve time.

```
generate item → Stage A programmatic (JSON, grounding-membership, date-check,
                trap-diversity, absolutes, source-leak, homogeneity)
   ├─ fail → regenerate (≤ k=4 tries; then return best + flag)
   └─ pass → single-best check + programmatic date-check
        ├─ fail → regenerate
        └─ pass → emit item + verification receipt
```

- The programmatic **grounding + date-check** run free/deterministically every
  serve. The **single-best** check is the SC-KEY guard the date-check can't cover.
- **Cost/fallback (minor fix):** a per-serve frontier judge adds latency/cost. A
  **cheaper distilled single-best checker** is a fallback, but is used **only after
  it is validated** against the frontier judge on a held-out slice (agreement ≥
  target); until then the frontier judge is used and its per-serve cost is
  budgeted (Appendix B).

---

## 8. Iteration strategy — fix failures in DATA, not hyperparameters

Every 5B failure routes to a **data** change; hyperparameters frozen after M3.

| Failure mode | Symptom | Root cause in DATA | Data fix (v2) |
| :--- | :--- | :--- | :--- |
| **Double-key** | `key_valid`/single-best low | subtle double-keys passed | key-verifier 3/3; add contrastive specific-vs-background `scope_mismatch` pairs from the table |
| **Wrong-era key** | date-check fail | candidate window too wide | tighten the injected window; add `wrong_era` hard negatives |
| **Filler distractor** | distractor-craft 0 | trap mix skewed | rebalance; oversample `true_but_irrelevant`/`scope_mismatch`; DPO negatives |
| **Echoes source** | requires-outside fail | weak items slipped | raise `reasoning_hops`; judge harder; drop 1-hop |
| **Broken JSON** | programmatic fail | too few schema examples | more examples; confirm `enable_thinking=False`; loss-on-JSON-only |
| **Collapses on note/terse input** | note slice or robustness low | too few note-conditioned items | add note-conditioned + terse in-scope items |

Each v2 cycle fixes **one** named mode and re-runs 5B (Day-4 exit).

---

## 9. Stretch ladder

1. **DPO from `data/rejects/` (A8).** Pair kept (chosen) vs matched trap-labeled
   reject (rejected) on the same stimulus+archetype; ~500–800 pairs; measure gain
   over SFT ([ccot] +12.5%).
2. **Adversarial / robustness eval.** Terse fragments, multi-development sources,
   ±1-year boundary developments (stress date-check), double-key bait.
3. **Notes-only input path (the deferred C1 option b).** Add a **note→PD-source
   retrieval** step (select a legal stimulus for a raw student note), then train +
   eval on notes-only inputs — the true "notes" product, promoted to v2 because it
   needs its own retrieval + eval.
4. **Add `CONTEXT_SITUATION`** (sanctioned 3rd archetype; re-run 5B, ~89%).
5. **F5 crown jewel later** (`EVIDENCE_SUPPORTS_CLAIM`) — needs secondary sources +
   support/undermine judge; v2+ (feasibility marks F5 OUT of v1).

---

## 10. Milestones (re-sequenced — M4 fix)

| # | Day | Focus | Exit criterion (gradeable) |
| :--- | :--- | :--- | :--- |
| **M0** | 1 | Setup, research, Brainlift, **kick off A3/A6** | Qwen3-4B-Instruct runs locally; **teacher ToS confirmed (A7)**; `splits.json` schema drafted (A1); Brainlift POV written; **A3 (corpus) + A6 (table) builds STARTED** (owners: historian + legal/researcher). |
| **M1** | 2 AM | Harness + pipeline + smoke test | Full loop generate→filter→train→eval on **50 junk items**; `verifier.py` + `eval_harness.py` + gen orchestrator scaffolded (A2). |
| **M2** | 2 PM | **LITMUS build-gate (causation subset)** | `02b_litmus_results.md` (A5): **P1 (teacher ≥70–75% + key_valid ≥70–75%)** and **P2 (base ≤45–55%)** on ~90 items/archetype → BUILD; else kill/RETHINK. |
| **M2.5** | 2→3 | **BLOCKING pre-bulk-gen gate** | **(i) A3 done** (~150 primary, license-provenanced, disjoint splits committed); **(ii) A6 done** (~150–200 devs, roles tagged, every TRAIN/EVAL stimulus has ≥1 groundable CAUSE + EFFECT); **(iii) A4 gold** (≥10/archetype); **(iv) G-cal:** judge + key-verifier ≥90% agreement vs gold on `key_valid` AND single-best; **(v) G-yield:** ~150-item real batch → measured A/B/C yields → bulk volume + budget re-derived. **All five must pass before any bulk spend.** |
| **M3** | 3 | v1 bulk gen + first real numbers | **Depends on M2.5.** Bulk-gen to 600/archetype (cap 6); first QLoRA; **base-vs-tuned numbers on the board** (5B, source-cluster CI); tuned > base on Spec adherence. |
| **M4** | 4 | v2 dataset (data iteration) | **One** failure mode (§8) fixed in data; retrain; report improvement + delta CI. |
| **M5** | 5 | Ship & defend | Final 5B + error analysis; **dataset published**; **model on HF + verifier-on demo** (requires source+attribution+date, optional note); **eval harness + base-vs-tuned table**; **Brainlift final**; **3–5 min demo video**. |
| **M6** | 5+ | Stretch | ≥1 rung of §9 (DPO or adversarial) yields a gradeable result. |

---

## Appendix A — Blocking artifacts & owners

| ID | Artifact | Blocks | Owner | Gate |
| :--- | :--- | :--- | :--- | :--- |
| **A1** | `data/splits.json` (primary-only, disjoint counts §3.2) | all gen + eval (P6) | data lead (eng) | M0 draft → M2.5 committed |
| **A2** | `slm/verifier.py` + `slm/eval_harness.py` + gen orchestrator (candidate-set injector) | M1, filtering, §7 | eng | M1 |
| **A3** | **Corpus 14 → ~150 text primary**, per-chunk license provenance, disjoint splits | TRAIN/EVAL volume (P3, C3) | **historian + legal/researcher** | **HARD gate at M2.5, before M3** |
| **A4** | `data/gold/` ≥10 human-keyed items/archetype | G-cal calibration, few-shots | **historian review** | **HARD gate at M2.5** |
| **A5** | `docs/02b_litmus_results.md` | M2 build-gate | eng | M2 |
| **A6** | **Developments table 84 → ~150–200**, date-reverified, `keyable` vs `distractor_only` roles, dense mechanisms+background/core period | grounding set (C4) | **historian review** | **HARD gate at M2.5, before M3** |
| **A7** | Teacher-ToS confirmation | any bulk gen | project lead | M0 |
| **A8** | `data/rejects/` trap-labeled reject / DPO preference store (minor fix) | DPO stretch (§9) | eng | M3 (byproduct) |

## Appendix B — API / compute budget (placeholder; re-derived at G-yield)

Frontier ~\$3/1M in, ~\$15/1M out; SLM inference local. Volume is **generate-to-
target-with-cap** at the 600-floor, so lower than v1.

| Line | Volume (placeholder) | Est. |
| :--- | :--- | ---: |
| Teacher generation (incl. ~1.3× regen) | ~3,700 calls | ~\$65 |
| Judge (Stage B + 20% double) | ~2,700 calls | ~\$34 |
| Key-verifier (n=3 solves) | ~1,664 × 3 | ~\$37 |
| Calibration G-cal + G-yield (~150 items full stack) | small | ~\$12 |
| Litmus (causation subset: gen + judge; SLMs local) | ~360 gen + judge | ~\$25 |
| Product eval 5B (judge + verifier; gen local) × 2 iters | ~1,000 judge calls | ~\$22 |
| Inference-demo judge (per-serve) + slack (v2 regen, DPO) | — | ~\$55 |
| **Frontier subtotal** | | **~\$250** |
| GPU (QLoRA 1× A100/H100, ~3–5 runs) | ~\$2–4/h | **~\$40–80** |

**Total ≈ \$290–330** — re-confirmed against measured yields at M2.5 before the
bulk spend.

## Appendix C — Spec-compliance checklist (preserved — criterion 12)

| Spec non-negotiable | Where |
| :--- | :--- |
| Dataset is the deliverable (published) | §3, M5, A-artifacts |
| Eval built **before** training | §5A litmus at M2, before M3 |
| Base-vs-tuned comparison | §5B, §1 WIN |
| QLoRA/Unsloth on small open base | §6 |
| No broad domains | §1 scope = causation pair |
| Fix failures in DATA | §8 |
| Behavior fails the prompt test | §5A P2; kill if base ≥80% |
| Model on HF + inference demo | M5, §7 |
| Eval harness + results table | §5B, A2 |
| Brainlift + 3–5 min video | M5, [`brainlift_draft.md`](brainlift_draft.md) |
| **Inherited:** grounding to table | §2, §3.3, §4 Stage A (P5, now mechanical) |
| **Inherited:** inference verifier | §7 (P4) |
| **Inherited:** confirmed teacher `key_valid_rate` | §5A P1 (M2) |
| **Inherited:** text primary only (v1) | §3.2 (P7) |
| **Inherited:** no College Board content; MMLU = eval-only | §3.2 (Deliverable 5) |

---

## Approval criteria for `plan_v2` — validator checklist (all met)

- [x] **1. Input contract fixed & consistent.** Narrowed to "provided primary
  source (+ optional note)" across title, §2, §3.4, §5B, §7 demo; `{{NOTE}}` slot
  re-added to `data_gen_prompt.md`; note-conditioned items in TRAIN (~25–30%);
  note-augmented slice in EVAL_HELDOUT (8/28) + 5B; inference requires
  `source_text + attribution + source_date`. *(C1, M7)*
- [x] **2. Grounding enforced mechanically.** Period-windowed candidate set
  **injected**; answer + all distractors by `development_id`; free-recall clause
  **removed**; Stage A **hard-rejects** ungrounded ids. `data_gen_prompt.md`
  edited. *(C2)*
- [x] **3. splits.json — real, disjoint, primary-only counts + item cap.**
  LITMUS 10 + EVAL 28 + TRAIN 110 = ~148 ≤ built corpus; cap **≤6/(stimulus,
  archetype)** stated and tied to the 600/archetype target. *(C3)*
- [x] **4. A3 corpus expansion gated before M3.** 14 → ~150 primary,
  license-provenanced, owners named; **HARD gate at M2.5**; fallback stated. *(C3, M4)*
- [x] **5. A6 developments table gated before M3.** → ~150–200, date-reverified,
  `keyable`/`distractor_only` roles, per-core-period mechanisms + background;
  **every TRAIN/EVAL stimulus verified to have ≥1 groundable CAUSE and EFFECT**;
  HARD gate at M2.5. *(C4)*
- [x] **6. Judge + key-verifier calibrated (BLOCKING).** G-cal vs `data/gold/`
  (≥10/archetype), **≥90% agreement on `key_valid` AND single-best**, human slice
  audits double-key — before bulk gen. *(M1)*
- [x] **7. 5B CI = source-level cluster bootstrap.** EVAL_HELDOUT = 28 disjoint
  primary sources; win (lower-bound > 0, +25 pts) judged under cluster bootstrap
  (≥2,000 resamples). *(M2)*
- [x] **8. SC-KEY kill unambiguous.** Production (verifier-on) SC-KEY **< 85%** =
  kill; raw target ≥0.80 (not a trigger); "raw <0.85" deleted; §4 ↔ glance box
  reconciled. *(M3)*
- [x] **9. Real-gen calibration batch.** G-yield (~150 items) measures actual
  A/B/C yields; bulk volume + budget re-derived before the spend; funnel marked
  placeholder. *(M5)*
- [x] **10. Timeline re-sequenced.** A3/A4/A6 built Day 1–2, gated at **M2.5**;
  **M3 exit depends on them**; historian/legal owner named; v1 volume cut to the
  600 floor. *(M4)*
- [x] **11. Litmus P1/P2 on causation subset.** Archetype list restricted to
  CAUSE/EFFECT on 10 primary sources → ~90 items/archetype/model. *(M6)*
- [x] **12. Spec compliance preserved.** Appendix C intact: eval-before-training,
  base-vs-tuned, dataset published, QLoRA/Unsloth, litmus separate from product
  eval, teacher-ToS gate.
