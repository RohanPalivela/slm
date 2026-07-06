# Validator Approval — `plan_v2.md` (Deliverable 4, approval pass)

> **Role:** VALIDATOR in the brainstormer↔validator loop. This is the approval
> pass over [`plan_v2.md`](plan_v2.md), verifying it against my own 12-item
> checklist in [`validator_feedback_v1.md`](validator_feedback_v1.md) and
> confirming the two artifact changes actually landed.
>
> **Binding, not relitigated:** scope = `CAUSE_OF_SOURCE` + `EFFECT_OF_SOURCE`;
> Qwen3-4B-Instruct; QLoRA + distillation; ~91% conditional; SC-KEY crux;
> date-check necessary-not-sufficient.

---

## VERDICT: **APPROVE**

`plan_v2` genuinely closes **all four critical** and **all seven major** gaps from
the v1 REVISE (major). Every one of the 12 approval criteria PASSES on the plan's
own text, and both artifact edits landed as claimed. The corpus math now closes
(600 ÷ cap-6 → 110 TRAIN primary; 10 + 28 + 110 = 148 ≤ ~150 built by A3), the
timeline is credible with explicit fallbacks, and the litmus P1/P2 subset N (~90
items/archetype) is adequate for a go/no-go gate.

The sanity-check surfaced **two localized data-detail findings** (date-check
granularity on same-year causes; a `role`-vs-`kind` field-naming mismatch). Neither
is execution-breaking: both are bounded by the plan's own **M2.5 blocking gates**
(the "every TRAIN/EVAL stimulus has ≥1 groundable CAUSE+EFFECT" check and G-cal),
have bounded blast radius (the generate-to-target-with-cap + `{"skip":true}`
mechanism caps spend), and have localized fixes. I record them as **required
refinements to resolve at M2.5**, not as approval blockers.

**Execution-ready, pending empirical litmus P1/P2 confirmation.** The whole
build still rests on the Day-2 litmus (§5A): teacher expert-grade **and**
`key_valid_rate` ≥70–75% on the causation pair (P1) and prompted base 4B ≤45–55%
(P2). The plan correctly gates all training on that empirical result; approval here
is of the *plan as an execution recipe*, not a guarantee the litmus will pass.

---

## Artifact verification (both changes landed)

**1. `prompts/data_gen_prompt.md` — all four required edits confirmed:**

| Required change | Landed? | Evidence |
| :--- | :---: | :--- |
| Injects a period-windowed candidate development set | ✅ | USER block: `{{CANDIDATE_DEVELOPMENTS}}` "period-windowed around the source … includes both correct-direction keyable developments and off-direction/off-era ones for the traps." |
| Answer **and all 3 distractors** chosen BY `development_id` | ✅ | SYSTEM "GROUNDING (HARD RULE)": keyed answer AND all 3 distractors "MUST each be chosen from the injected CANDIDATE_DEVELOPMENTS set, referenced BY `development_id`"; `options_meta.*.development_id` "MUST be a development_id from CANDIDATE_DEVELOPMENTS." |
| Removed the free-recall / "standard APUSH-level knowledge" clause | ✅ | "There is NO 'standard APUSH-level knowledge' fallback and NO free recall." (v1 escape hatch is gone; replaced by a `{"skip": true, "reason": …}` return when nothing is keyable.) |
| Re-added optional `{{NOTE}}` slot | ✅ | USER block "STUDY NOTE (OPTIONAL — if non-empty, steer … if empty, ignore it)" with `{{NOTE}}`; schema carries `note_conditioned`. |

Bonus: the downstream filter now specifies the **Stage-A grounding hard-reject**
("every `options_meta.*.development_id` MUST be present in the injected
CANDIDATE_DEVELOPMENTS set … reject if any option cites an id absent"), mechanically
enforcing P5. Good.

**2. `data/apush_key_developments.json` — expansion confirmed:**

- **Count = 167** (verified: 84 original + 79 [`aztec_inca_conquest` … `great_recession`] + 4 [the Monroe/Truman causes]). In A6's stated `~150–200` band. ✅
- **Optional `kind` tag** (`mechanism|background|event`) present on the new entries; schema `fields` + `kind_note` updated ("keep ≥1 mechanism and ≥1 background per core-period episode" — this is exactly the specific-vs-background lever C4 asked for). ✅
- **Monroe Doctrine (1823) causes added:** `holy_alliance_threat` [1815–1823] `kind=mechanism` ("European monarchist bloc … Monroe warned against") + `latin_american_independence` [1808–1825] `kind=background`. The specific(mechanism)-vs-background `scope_mismatch` pairing is **fully supportable** for Monroe. ✅
- **Truman Doctrine (1947) causes added:** `soviet_pressure_greece_turkey` (1947) `kind=mechanism` ("most directly prompted the Truman Doctrine") + `british_withdrawal_1947` (1947) `kind=background`. The pairing developments exist (see finding F1 for the date-granularity caveat). ✅

**A6-gate consistency:** the delivered table matches A6's "dense mechanisms +
background" via `kind`, and the 167 count is in-band. The "keyable vs
distractor_only" half of A6's wording is the per-injection computed attribute, not a
static column — see finding F2.

---

## The 12 criteria — PASS/FAIL

| # | Criterion | Result | One-line justification (grounded in plan_v2) |
| :--- | :--- | :---: | :--- |
| 1 | Input contract fixed & consistent | **PASS** | Narrowed to "primary source (+ optional note)" across title, §1 INPUT, §2 spec, §3.4 schema (`source_date` REQUIRED + `note`), §5B (8/28 note-augmented slice), §7 demo; `{{NOTE}}` re-added to the gen prompt; notes-only → §9 stretch. |
| 2 | Grounding enforced mechanically | **PASS** | Candidate set injected; answer + all distractors by `development_id`; free-recall clause removed; Stage A hard-rejects any `development_id ∉ injected set` (confirmed in the artifact + §4). |
| 3 | splits.json real/disjoint/primary + item cap | **PASS** | §3.2 primary-only: LITMUS 10 + EVAL 28 + TRAIN 110 = 148 ≤ ~150; cap ≤6/(stimulus,archetype) tied to the 600/archetype target; A1 committed at M2.5. Math closes (110×6 = 660 ≥ 600). |
| 4 | A3 corpus expansion gated before M3 | **PASS** | A3 = 14 → ~150 primary, license-provenanced, owners (historian + legal/researcher); HARD gate at M2.5; explicit fallbacks (cap-8 → ~116; CAUSE-only). |
| 5 | A6 table gated before M3; groundability verified | **PASS** | Table → 167 with `kind` mechanisms/background, Monroe+Truman causes added; "every TRAIN/EVAL stimulus has ≥1 groundable CAUSE+EFFECT" is a HARD M2.5 gate. *(See F1: the date-check must handle same-year causes so Truman-CAUSE actually clears this gate.)* |
| 6 | Judge/key-verifier calibration BLOCKING | **PASS** | G-cal (M2.5): `data/gold/` ≥10/archetype; judge + key-verifier ≥90% agreement on `key_valid` AND single-best; human slice audits double-key; before any bulk spend. |
| 7 | 5B = source-level cluster bootstrap | **PASS** | §5B resamples the 28 sources then items within (≥2,000 resamples, effective N≈28); EVAL_HELDOUT = 28 disjoint primary; win (+25 pts, CI lower-bound > 0) judged under that method. |
| 8 | SC-KEY kill unambiguous | **PASS** | §4: kill = **production (verifier-on) SC-KEY < 85%**; raw target ≥0.80 explicitly *not* a trigger; "raw <0.85" wording deleted; glance box ↔ §4 reconciled. |
| 9 | Real-gen calibration batch before full spend | **PASS** | G-yield (~150 real items) → measured A/B/C yields → bulk volume + budget re-derived; §3.5 funnel + Appendix B both marked PLACEHOLDER. |
| 10 | Timeline re-sequenced | **PASS** | A3/A4/A6 kicked off M0, gated at M2.5; M3 exit depends on M2.5; owners named; volume cut to the 600 floor + fallbacks. Credible-with-fallbacks (A6 already delivered de-risks it). |
| 11 | Litmus P1/P2 on causation subset | **PASS** | §5A restricts the archetype list to CAUSE/EFFECT on the 10 primary sources → 180 items/model (~90/archetype) — adequate for a coarse go/no-go gate. |
| 12 | Spec compliance preserved | **PASS** | Appendix C intact: eval-before-training, base-vs-tuned, dataset published, QLoRA/Unsloth, litmus separate from product eval, teacher-ToS gate. |

**12 / 12 PASS.**

---

## Sanity-check: new inconsistencies introduced by the revision

Two genuine findings (not invented nitpicks). Both are **non-blocking** and land
inside the plan's existing M2.5 gates; fixing them is a localized data/prompt detail.

**F1 — Date-check granularity can't accept same-year (or table-straddling) causes.**
Stage A's rule is `cause year < source_date` and `source_date` is an **integer
year** (§3.4 schema). The Truman Doctrine (1947) causes that were just added
(`soviet_pressure_greece_turkey` = 1947, `british_withdrawal_1947` = 1947) are the
**same year** as the source, so `1947 < 1947` is false → Stage A would reject them →
Truman-**CAUSE** is **not groundable** under the literal rule, contradicting the A6
guarantee in criterion 5. Monroe's `holy_alliance_threat` [1815–1823] and
`latin_american_independence` [1808–1825] are **year-ranges** that end at / straddle
the 1823 source date, and the plan doesn't say whether a range is compared by its
start or end. *Fix (at M2.5/A2/A6):* give the date-check sub-year resolution (full
dates) **or** a documented "predates/postdates" partial order with a range tie-break
(e.g., compare range-start for causes), then re-run the M2.5 groundability check.
*Why non-blocking:* the M2.5 "≥1 groundable CAUSE+EFFECT per stimulus" gate is
exactly the check that surfaces this before bulk gen; blast radius is a few same-year
stimuli (mainly Truman); Truman-**EFFECT** is groundable, so only the CAUSE half is
affected.

**F2 — `role[keyable|distractor_only]` (plan/prompt) vs `kind[mechanism|background|event]` (table).**
Plan §3.3 and the `data_gen_prompt.md` candidate-row spec list
`development_id | name | year | period | role[keyable|distractor_only]`, and A6 says
"keyable vs distractor_only roles" — but the delivered table has **`kind`**, not
`role`, and no keyable/distractor_only column. These are actually two different
things: `keyable` vs `distractor_only` is inherently **per-(stimulus, archetype)**
(date-direction-dependent → computed by the orchestrator at injection), while `kind`
is the **static** mechanism/background signal that powers the specific-vs-background
`scope_mismatch`. As written, the injected row surfaces `role` but **not** `kind`, so
the teacher lacks the static signal it needs to build the specific-vs-background
pairing the plan asks for. *Fix (at M2.5/A2):* have the orchestrator inject **both**
`kind` (from the table) and a computed date-legality/`keyable` flag, and reconcile
the field names in §3.3 + the prompt + A6. *Why non-blocking:* grounding-by-id (C2)
is unaffected; the specific-vs-background pairing is a judge-enforced quality nicety
(programmatic Stage A only requires trap-diversity ≥2), and A2 can attach both fields.

**Light notes (not tracked as blockers):**
- Only the **83 new** developments carry `kind`; the original 84 are unlabeled. For
  a core-period episode whose mechanism *and* background both live in the original
  84, there's no `kind` to key the pairing off — A6's date-reverification pass should
  backfill `kind` on the core-period originals it relies on.
- Litmus P1/P2 items are clustered in 10 sources (same source-clustering caveat as
  5B); fine for a coarse gate, but the effective N is ~10 sources, not 90 items —
  read P1/P2 as a screen, not a tight estimate.
- **A3 (14 → ~150 legally-verified PD primary sources) is the main residual
  execution risk** for a one-week build; it is well-mitigated by the stated cap-8
  (~116) and CAUSE-only fallbacks, and by A6 already being delivered.

---

## Approval rationale & the "pending" note

Every gap that drove the v1 REVISE (major) is closed with a concrete, checkable
mechanism, not a restated aspiration: grounding is now a `development_id` membership
test with a Stage-A hard-reject; the corpus is sized by target ÷ cap with numbers
that close; A3/A4/A6 are hard M2.5 gates ahead of any bulk spend; calibration
(G-cal) and yield (G-yield) block the budget; the SC-KEY kill is unambiguously on
the production number; and the eval CI is a source-cluster bootstrap on 28 held-out
sources. The two sanity-check findings are localized data/prompt refinements that the
plan's own M2.5 gates are designed to catch.

**Status: execution-ready, pending litmus P1/P2 empirical confirmation.** Proceed
with M0–M2 as written. Before crossing the M2.5 blocking gate into bulk generation,
resolve F1 (date-check sub-year/range handling) and F2 (inject `kind` + reconcile the
`role` naming) — both fall naturally inside the M2.5 checklist. Approval of the plan
does not presume the litmus passes; if P1 (teacher `key_valid_rate` ≥70–75%) or P2
(base ≤45–55%) fails on the causation subset, the plan's own kill/RETHINK branches
apply.

---

*Reviewed against `plan_v2.md`, the v1 checklist in `validator_feedback_v1.md`, the
edited `prompts/data_gen_prompt.md`, and `data/apush_key_developments.json` (verified
167 developments; `kind` tags; Monroe + Truman cause developments present).*
