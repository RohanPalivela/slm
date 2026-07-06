# Validator Feedback — `plan_v1.md` (Deliverable 4 review)

> **Role:** VALIDATOR in the brainstormer↔validator loop. This is an
> execution-focused, deliberately skeptical review of
> [`plan_v1.md`](plan_v1.md) as a **one-week build recipe**, before any GPU time
> or bulk API spend.
>
> **Binding, NOT relitigated** (inherited from
> [`../03_feasibility_assessment.md`](../03_feasibility_assessment.md)): scope =
> `CAUSE_OF_SOURCE` + `EFFECT_OF_SOURCE`; base = Qwen3-4B-Instruct; QLoRA +
> frontier distillation; ~91% conditional on grounding + verifier + confirmed
> teacher `key_valid_rate`; SC-KEY is the crux; date-check is
> necessary-not-sufficient. I critique only whether the PLAN correctly and
> completely **operationalizes** that verdict.

---

## VERDICT: **REVISE (major)**

The plan is a genuine, well-structured first draft with strong bones (shared
falsifiable boolean, two separated eval instruments, three-family filtering,
teacher-ToS gate). But it has **four execution-breaking gaps** that would waste
the bulk-gen budget and/or produce an ungradeable deliverable if run as written:

1. The **input contract is inconsistent** — the product promises "notes," but
   training and eval both condition only on a provided primary **source**, and
   the bulk-gen prompt has **no note slot at all**. The eval does not reflect the
   claimed input distribution.
2. **Grounding (P5) is asserted, not enforced** — the actual gen prompt does not
   inject the developments table and explicitly permits "standard APUSH-level
   knowledge" (i.e. free recall), contradicting the plan's own non-negotiable.
3. **Corpus is insufficient and mis-counted** — the usable causation-pair pool is
   **14 primary** stimuli (not 22), the split sizes need ~83–108 primary, and the
   volume target implies 21–30 items/stimulus, which attacks SC-KEY and
   contamination.
4. The **developments table (84) is too sparse to be the grounding set** for
   correct keys (concrete failures on Monroe 1823 / Truman 1947), and its
   expansion (A6) is not gated before bulk gen.

None of these touch the binding verdict; all are about operationalization. They
are fixable and I give specific, checkable requirements for `plan_v2` below.

---

## What the plan gets right (keep these)

- **One shared falsifiable boolean** across generation, filtering, eval, and
  inference (§2) — the correct anti-drift design; thesis, data, and metric cannot
  silently diverge.
- **Two eval instruments cleanly separated** (§5A litmus build-gate *before*
  training; §5B base-vs-tuned on held-out sources) — satisfies
  "eval-before-training" and does not conflate the litmus with the product eval.
- **Three distinct model families** (teacher / judge / key-verifier) + a
  deterministic date-check; SC-KEY mechanisms are concrete (k-of-n independent
  solve, double-correct probe, per-batch human spot-check).
- **Teacher-ToS is a real gated precondition** (A7, M0 exit), not an afterthought
  — directly honors Deliverable 5 §4.2.
- **Fix-in-data discipline** (§8): every eval failure routes to a data change;
  hyperparameters frozen after M3; loss-on-response-only; `enable_thinking=False`
  is well-justified for a deterministic JSON emitter.
- **Honest about the corpus gap** (A3 flagged), and the filter-funnel arithmetic
  is internally consistent (1,800→1,440→936→674; 4,500→3,600→2,340→1,685).
- **One `verifier.py`** reused as train filter + inference guard (single source of
  truth), and a spec-compliance checklist mapping each non-negotiable.

---

## Critical issues (must fix)

| ID | Issue | Required fix |
| :--- | :--- | :--- |
| **C1 — Input definition: notes vs source; eval misses the true input distribution** | Title (`Notes/Source → …`), the product GOAL, `litmus_generation_prompt.md` ("notes/source → …"), and the feasibility framing `f(source, note)` all promise **notes** as input. But §2 behavior spec, the §3.4 schema, and **both prompts** condition on a *provided, date-tagged primary SOURCE*. Worse, the bulk-gen prompt (`prompts/data_gen_prompt.md`, USER block) **has no `{{NOTE}}` slot** — the litmus prompt's `{{NOTE}}` was dropped — so §3.2's "note-seed steers which development" is **not wired into generation**. Eval 5B runs only on EVAL_HELDOUT *sources*. Net: the notes-only (and even note-augmented) path is neither trained nor evaluated; the HF demo will accept student notes the model never saw, and the date-check needs a `source_date` a notes-only input does not carry. | Pick ONE and make the whole pipeline consistent. **(a) Recommended — narrow the input:** state the product input as "a provided text primary source (+ optional study note)"; scrub "notes" from the title/Brainlift/demo; require `source_text + attribution + source_date` at inference. **(b) Keep notes:** implement and eval the **note→source** step (retrieve/select a PD stimulus for a given note), re-add the `{{NOTE}}` slot to `data_gen_prompt.md`, TRAIN on note-conditioned items, and add a **notes / note-augmented slice** to EVAL_HELDOUT and 5B so the eval reflects the real input distribution. |
| **C2 — Grounding (P5) is asserted, not enforced; the gen prompt allows free recall** | §2 and §3.3 say the key is "SELECTED from the developments table, never free-recalled" (the single biggest SC-KEY lever; feasibility ~91%→~82% without it). But `data_gen_prompt.md` **does not inject** the developments list — it only tells the teacher to "use the table" and then **explicitly permits "standard APUSH-level knowledge … when unsure, choose a different development,"** an escape hatch that *is* free recall and contradicts P5. Stage A checks the keyed date "vs `apush_key_developments.json`" but nothing hard-rejects an option whose development is **absent** from the table, so ungrounded keys/distractors pass. | Inject the **period-filtered candidate set** (`development_id` + name + date) into the gen prompt; require the answer AND all three distractors to be chosen **by `development_id` from that injected set**; **remove** the "standard APUSH-level knowledge" clause; make Stage A **hard-reject** any option whose `development_id ∉ injected set`. (This also raises Stage-A yield, since ungrounded items won't be generated then discarded.) |
| **C3 — Corpus sufficiency: pool is 14 primary (not 22); splits + volume don't close** | Counted: **22 stimuli = 14 primary + 8 secondary**. v1 P7 = text primary only, and the 8 secondary are F5 (out of scope), so the causation-pair pool is **14 primary**. splits.json needs 10 (litmus primary) + ~18 (eval) + 55–80 (train) = **83–108 primary**, but A3 targets only **80–100 total** — at/below the requirement (TRAIN would get 52–72, under its own 55–80 floor). At the final target, 1,685 kept ÷ (55–80 train stimuli) = **21–30 items/stimulus (~10–15 per stimulus×archetype)**; if A3 slips and gen runs on today's 14 primaries it is ~120/stimulus. Only a handful of *defensibly single-best* most-direct causes/effects exist per source, so this pressure forces **near-duplicate keys or drift to weaker keys — directly attacking SC-KEY** and inflating contamination (the 0.92 dedup on `stimulus_id+stem+answer` will NOT catch same-key/reworded-stem pairs). | **Size the corpus by target-kept ÷ defensible-distinct-items-per-(stimulus,archetype)**, not by the raw-gen funnel. State an explicit **items-per-(stimulus,archetype) cap** (e.g. ≤6–8). Recompute the required primary count (≈100–160 primary to keep 840/archetype, OR drop to the 600 floor to reduce pressure). Report **primary-only** counts per split in splits.json; make **A3 a hard gate before M3** with per-chunk license provenance and dedicated build time. |
| **C4 — Developments table (84) is too sparse to be the GROUNDING SET for keys** | 84 developments; 73 in core periods (P3:12, P4:11, P5:10, P6:9, P7:17, P8:14). The plan uses ONE table for two roles (anachronism/distractor pool AND the set the correct key is drawn from). As a **grounding set it fails on real seed stimuli**: **Monroe Doctrine (1823)** — no "Latin American independence / fear of European intervention," so the most-direct cause is un-groundable; **Truman Doctrine (1947)** — no "Soviet pressure on Greece/Turkey / British withdrawal," so no groundable most-direct cause. The teacher must then pick a weaker in-table development (background/scope_mismatch) or free-recall — both hurt SC-KEY. Per-period pools of 9–10 also cap distractor diversity at volume. A6 (→150–200) exists but is treated as a **v2 fix (§8)** and is **not sequenced before M3 bulk gen**. | Make **A6 a hard gate before M3**: expand + date-reverify to ~150–200 with dense per-core-period coverage of **both specific mechanisms and background conditions** (so a specific-vs-background `scope_mismatch` pair exists per stimulus). Before generating on any stimulus, **verify it has ≥1 groundable most-direct cause AND effect in the table**. Consider separating the "distractor pool" table from the "keyable developments" set. |

---

## Major issues

| ID | Issue | Fix |
| :--- | :--- | :--- |
| **M1 — Judge/key-verifier calibration is not a blocking pre-gen gate** | A4 "blocks judge calibration" and Stage C has a *per-batch* human spot-check, but there is **no gate** requiring judge + key-verifier to hit an agreement threshold vs a human-keyed gold set **before** the bulk spend. LLM judges err on history (docs/02 §4b); a miscalibrated judge passes bad keys and silently contaminates the whole dataset after the budget is gone. | Add a **blocking gate**: build `data/gold/` (≥6–10 human-keyed items/archetype), measure judge & key-verifier agreement vs gold (target e.g. **≥90% on `key_valid` and single-best**), start bulk gen only if it clears. Include a human slice that specifically audits **single-best / double-key**, not just factual accuracy. |
| **M2 — Held-out CI is over-optimistic (item bootstrap, thin N)** | 5B bootstraps "over items" on ~18 sources × 6 items × 3 runs. Items within a source are correlated (shared stimulus), so item-level bootstrap **understates variance**; effective N ≈ 18 sources, not 324 items. The win condition (delta 95% CI lower-bound > 0) can look satisfied under item-bootstrap yet fail under a proper **source-cluster** bootstrap. 3 runs is also too few to trust "std ≤ 5 pts." | Use a **source-level cluster bootstrap** (resample sources, then items within). Size EVAL_HELDOUT to **≥25–30 disjoint primary sources** for a stable delta CI. Report run-to-run std but treat it as indicative; state the CI method explicitly. |
| **M3 — SC-KEY kill threshold conflates raw vs production** | §4 says "If **raw** stays **<0.85** after v2 … AND the verifier is on → kill," but the SC-KEY table sets the **raw target at ≥0.80** (feasibility caps raw ~0.80). So "raw <0.85 = kill" would fire on the *expected/acceptable* raw value. The glance box instead says "tuned SC-KEY <85% **after v2 + verifier**" (production). The two disagree. | State the kill criterion on **production (verifier-on) SC-KEY < 85%** (matching feasibility §5); keep raw target ≥0.80; delete the contradictory "raw <0.85" wording. Reconcile §4 and the glance box. |
| **M4 — One-week timeline under-resources the pre-M3 blocking artifacts** | A3 (14→80–100 primary, legally verified, provenance-segregated), A6 (84→~150–200 date-reverified), and A4 (human-keyed gold) all need substantial historian/legal effort and are (or should be) gated before M3 (Day 3). Doing all three by end of Day 2 alongside splits + verifier + harness + litmus is not credible — owners are listed as "historian review / data lead," likely one person. | Re-sequence: allot an **explicit corpus/table-building block before M3**, or **reduce v1 volume** (fewer stimuli, 600 floor) to fit one week. Make the **M3 exit depend on A3 + A4 + A6** (not just "A3/A4 in place"). Name the historian/legal owner. |
| **M5 — Filter-funnel yields are assumed; no real-gen calibration before full spend** | Net keep 0.39 (0.80×0.65×0.72) drives the ~4,500-gen (~$325) budget, but the yields are asserted; the M1 smoke test uses **50 *junk* examples** (plumbing only). If grounding isn't injected (C2) or the table is sparse (C4), Stage-A yield could fall far below 80%, blowing budget and timeline. | After judge calibration, run a **small REAL calibration batch (~100–200 items)**, measure actual A/B/C yields, and **re-derive** raw-gen volume/budget from measured yields **before** the bulk spend. Update the funnel table with measured numbers. |
| **M6 — Litmus P1/P2 must be computed on the causation-pair subset with adequate N** | 5A runs the full litmus instrument (docs/02: 6 items/source cycling in-scope archetypes across 15 sources incl. 3 secondary + 2 adversarial), but the BUILD gate P1/P2 is defined on `CAUSE`/`EFFECT`. If items cycle many archetypes, only a fraction per source are causation-pair, so the decisive teacher `key_valid_rate` rests on few items. | For the build gate, run the litmus with the **archetype list restricted to the causation pair** on the primary sources (or explicitly compute P1/P2 on the causation subset and confirm the item count yields a stable estimate). |
| **M7 — Note-seed mechanism described but not wired; secondary stimuli mis-counted** | §3.2 defines note-seeds as a steering input, but `data_gen_prompt.md` has no `{{NOTE}}` slot (ties to C1). Separately, "22 stimuli" can read as if all 22 seed the causation pool; 8 are secondary/F5 and cannot seed `CAUSE`/`EFFECT` in v1. | Either wire the note slot into the gen prompt AND train on note-conditioned items, or **drop note-seeds from v1** and the input contract. In splits.json and all counts, report **primary-only** numbers for the causation pair. |

---

## Minor issues (nice-to-fix)

- **Glance-box WIN omits the "+25 pts"** delta stated in §5B — align the two.
- **"Final ~840/archetype clears the P3 floor of 600–1,000 with margin"** — 840 is
  mid-band, not "with margin" above 1,000; reword.
- **Cross-split dedup (0.90 cosine on `stimulus_id+stem+answer`)** won't catch
  **shared keyed-development leakage** across splits; with only 84 developments the
  key space is near-fully covered by TRAIN, so held-out "novelty" exists only at the
  stimulus level. Track held-out `(development, archetype)` novelty as a
  contamination check.
- **Inference verifier "Stage B/C-lite: judge single-best"** adds per-serve frontier
  latency/cost; the "cheaper distilled check" fallback's accuracy is unmeasured —
  note how it will be validated.
- **No artifact ID/owner for the reject/DPO store** (fine for stretch, but name it
  if DPO in §9 is planned).

---

## Approval criteria for `plan_v2` (checklist — all must be met)

- [ ] **1. Input contract fixed & consistent** across title, §2 spec, BOTH prompts,
  §3.4 schema, §5B, and the demo. If "note" stays in scope: `{{NOTE}}` slot present
  in `data_gen_prompt.md`, note-conditioned items in TRAIN, and a notes /
  note-augmented slice in EVAL_HELDOUT + 5B. If narrowed: title/Brainlift/demo say
  "provided primary source (+ optional note)" and inference requires
  `source_text + attribution + source_date`. *(C1, M7)*
- [ ] **2. Grounding enforced mechanically:** period-filtered candidate development
  set **injected** into the gen prompt; answer + all distractors chosen **by
  `development_id`** from that set; "standard APUSH-level knowledge" clause removed;
  Stage A **hard-rejects** any option whose `development_id ∉ injected set`. *(C2)*
- [ ] **3. splits.json committed** with real, **disjoint, primary-only** counts;
  `LITMUS_primary + EVAL_HELDOUT + TRAIN ≤ actual primary corpus`; an explicit
  **items-per-(stimulus,archetype) cap** stated and consistent with the kept-item
  target. *(C3)*
- [ ] **4. A3 corpus expansion** to the recomputed primary count (with per-chunk
  license provenance) **completed and gated before M3**; actual counts shown. *(C3, M4)*
- [ ] **5. A6 developments table** expanded + date-reverified (~150–200) with
  per-core-period coverage of specific mechanisms AND background conditions; **every
  TRAIN/EVAL stimulus verified to have ≥1 groundable most-direct cause and effect** in
  the table; **A6 gated before M3**. *(C4)*
- [ ] **6. Judge + key-verifier calibrated** vs a human-keyed `data/gold/` set with a
  stated agreement threshold (e.g. ≥90% `key_valid` & single-best) as a **BLOCKING
  gate before bulk gen**; human slice audits single-best/double-key. *(M1)*
- [ ] **7. 5B CI = source-level cluster bootstrap**; EVAL_HELDOUT sized (≥~25–30
  disjoint primary sources) for a stable delta CI; win condition (lower-bound > 0,
  +25 pts) evaluated under that method. *(M2)*
- [ ] **8. SC-KEY kill criterion** stated unambiguously on **production (verifier-on)
  SC-KEY < 85%**, raw target ≥0.80; §4 and glance box reconciled. *(M3)*
- [ ] **9. Real-gen calibration batch (~100–200 items)** measures actual A/B/C yields
  after judge calibration; bulk-gen volume/budget re-derived from measured yields;
  funnel numbers updated. *(M5)*
- [ ] **10. Timeline re-sequenced** so A3/A4/A6 precede M3; M3 exit depends on them;
  historian/legal owner named; v1 volume reduced if needed to fit the week. *(M4)*
- [ ] **11. Litmus build gate P1/P2** computed on the **causation-pair subset** with a
  stated, adequate item count. *(M6)*
- [ ] **12. Spec-compliance preserved** (already good — keep and confirm still holds
  after the above): eval-before-training, base-vs-tuned, dataset published,
  QLoRA/Unsloth, litmus separate from product eval, teacher-ToS gate.

---

*Reviewed against `plan_v1.md`, `03_feasibility_assessment.md`,
`Train Your Own Small Learning Model.md`, `02_litmus_test_prompt.md`,
`05_data_sourcing_and_legal.md`, `taxonomy/apush_question_archetypes.json`,
`prompts/data_gen_prompt.md`, `prompts/litmus_generation_prompt.md`, and the data
files (`seed_stimuli.jsonl` = 22 stimuli / 14 primary; `apush_key_developments.json`
= 84 developments; `apush_periods_themes.json`).*
