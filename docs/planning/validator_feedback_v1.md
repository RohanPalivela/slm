# Validator Feedback — plan_v1 (Revision 1)

> **Agent:** Validator subagent  
> **Input:** [`plan_v1.md`](plan_v1.md)  
> **Verdict:** **REVISE (major)** — do not start bulk generation or GPU training until plan_v2 closes critical issues.

---

## Summary

Plan_v1 correctly inherits the feasibility thesis (closed menus + verifier + base-vs-tuned) and maps to the spec’s final submission package. It fails as an execution recipe because:

1. The SC5 (answer-key correctness) story is only true for **enzyme Km/Vmax** items, not the full 12-concept MECH scope.
2. The one-week schedule assumes **~1,800 kept items by Day 3** (~23k frontier API calls) — belongs on Day 4–5.
3. Litmus protocol (`docs/02`) and product eval harness disagree on note sets, pass thresholds, and item counts.
4. Referenced artifacts (`data/splits.json`, `eval/harness.py`, truth tables, THEORY gold few-shots) do not exist; judge calibration is sequenced after bulk gen.

---

## Critical issues (must fix)

| ID | Issue | Required fix |
| :--- | :--- | :--- |
| C1 | MECH verifier only covers enzyme Km/Vmax; 12 concepts in scope | Narrow v1 MECH to enzyme/bioenergetics **or** ship truth tables per subdomain |
| C2 | THEORY has no symbolic SC5 rail; ≥90% raw key target unrealistic | Per-archetype targets; THEORY kill-criterion before bulk gen |
| C3 | Judge calibration (50/arch human check) not blocking bulk gen | **M1.5 Judge Calibration Gate** before M3 |
| C4 | D3 volume (~1,800 kept) not credible in one week | Phased: D3 = 300–400/arch; D4 = 600–900/arch |
| C5 | THEORY menu: 5 members in §1 vs “4 relations” in §3.1 | Unify to 5-item menu everywhere |
| C6 | Litmus (15 notes × 6 × 3 runs) ≠ plan eval (20+30+10) | Separate instruments: litmus for P1/P2; product eval for M3+ |

---

## Major issues

| ID | Issue | Fix |
| :--- | :--- | :--- |
| M1 | `physiology-as-model` not in concepts.json | Remove from v1 scope |
| M2 | Paraphrase eval mostly out-of-scope topics | Filter to ~12–15 in-scope cards; stratify metrics |
| M3 | `kinetics-equilibrium` on both archetypes | Split slug: `kinetics-equilibrium-mech` vs `-theory` |
| M4 | Missing artifacts (splits, harness, truth tables, THEORY gold) | M0.5 pre-flight checklist with blocking gates |
| M5 | Brainlift deferred to M6; spec requires D1 draft | M0 brainlift draft |
| M6 | `reasoning_hops < 2` not programmatically rejected | Add programmatic gate |
| M7 | Cover-the-options judge-only | Add stem-only solver probe |
| M8 | MMLU negatives cited but unused | Wire to DPO or remove claim |
| M9 | OpenMCAT few-shot memorization risk | Stem blocklist in firewall |
| M10 | 20-note eval → high variance on ±25 pt gate | Bootstrap CIs; ≥30 notes or aggregate 3-run items |
| M11 | “Reuse litmus SYSTEM verbatim” inaccurate | Fork `prompts/data_gen_prompt.md` |

---

## Validator approval criteria for plan_v2

Plan_v2 is **approved** when it:

- [x] Narrows MECH_PERT v1 to concepts with verifier rails (enzyme/bioenergetics cluster)
- [x] Adds M1.5 judge calibration + M2 litmus P1/P2 gates
- [x] Phases data volume (300–400 midweek, 600–900 final)
- [x] Unifies THEORY 5-item menu
- [x] Separates litmus vs product eval instruments
- [x] Lists blocking artifacts with owners
- [x] Adds OpenMCAT blocklist + dedup threshold 0.85
- [x] Defines per-archetype SC5 targets
- [x] Moves brainlift to M0 draft

**Resolution:** [`plan_v2.md`](plan_v2.md) — **APPROVED for execution** pending litmus P1/P2 empirical confirmation.
