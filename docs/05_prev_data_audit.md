# Prior Data Audit (`prev_data/`)

> Inventory of legally scraped assets from the Speedrun MCAT fork, mapped to the
> notes→questions SLM pipeline. Provenance is documented in
> `prev_data/build_question_bank.py`.

---

## Legal status

| Source | License | In repo | Use in SLM pipeline |
| :--- | :--- | :--- | :--- |
| **OpenMCAT** | AGPL-3.0 | Referenced by build script; bank may be gzipped elsewhere | Few-shot gold for F2/F3/F4; **stem blocklist** required to prevent memorization |
| **MMLU** (MCAT-relevant subsets) | MIT | Referenced by build script | Flat recall negatives / anti-pattern examples for DPO stretch |
| **First-principles cards** | AGPL-3.0 (project) | `speedrun_first_principles.json` | Primary **note seeds** (82 cards) |
| **Concept taxonomy** | Project | `speedrun_concepts.json` | Content vocabulary (56 concepts, 7 topics) |
| **Paraphrase set** | Project | `speedrun_paraphrase.json` | Transfer/novelty eval probe (30 cards × 2 rewordings) |

**Excluded by design:** Jack Westin (copyright), Khan Academy MCAT (NC-SA incompatible with AGPL app).

OpenMCAT content is **AI-generated** (noted in build script). Items can be strong (LDH-R kinetics passage) but must pass the same quality gates as teacher output.

---

## File-by-file

### `speedrun_first_principles.json`

- **82 hand-authored cards** across 7 topics: biochem 15, bio 14, physics 13, gen-chem 13, psych 11, o-chem 10, soc 6
- Each card: `front` (question about the principle), `back` (the principle text = **note input** for generation)
- Deliberately **not** derived from any served question in the question bank
- **Pipeline role:**
  - Training seeds: `back` field as SOURCE NOTE
  - Eval holdout: 20 cards stratified (never used as generation seeds)
  - Litmus: 10 of the 15 fixed test notes

### `speedrun_concepts.json`

- **56 concepts** (kebab-case `id`), 7 topics: biochemistry, biology, general-chemistry, organic-chemistry, physics, psychology, sociology
- Maps to AAMC Foundational Concepts (see taxonomy §3)
- **In-scope for v1** (~10 per archetype):
  - **MECH_PERT (enzyme/bioenergetics focus):** enzyme-regulation, glycolysis, oxidative-phosphorylation, bioenergetics, acid-base-equilibria, kinetics-equilibrium-mech
  - **THEORY_PLUS_STUDY:** evolution-ecology, associative-learning, social-psychology, theoretical-approaches, social-class, culture-socialization, developmental-psychology, personality, emotion-motivation, cognition-language

> **Note:** `physiology-as-model` was listed in plan_v1 but does **not** exist in the taxonomy file. Removed from v1 scope. `kinetics-equilibrium` is split into mech vs theory slugs in plan_v2 to avoid label conflicts.

### `speedrun_paraphrase.json`

- **30 cards**, each with 2 reworded MCQ stems testing the same principle
- Card `bc1` is competitive inhibition — directly on-archetype for MECH_PERT
- **~12–15 cards** align with v1 in-scope concepts; remainder (optics, stereochemistry, mendelian genetics, etc.) are **out-of-scope** for v1 eval reporting
- **Pipeline role:** fidelity + novelty probe — does generated item test the principle in new words/scenario?

### `build_question_bank.py`

- Dev-time fetcher for OpenMCAT + MMLU → normalized `SpeedrunQuestion` shape
- Output path in original project: `speedrun_question_bank.json.gz`
- **Not present as gz in this repo slice**; taxonomy references it for archetype exemplars
- Records per-choice explanations + “Common mistake” lines on OpenMCAT items (~169)
- Held-out split: deterministic 1-in-5 modulus

---

## Coverage vs v1 archetypes

| Archetype | Native gold in bank | FP seed coverage | Gap |
| :--- | :--- | :--- | :--- |
| MECHANISM_PERTURBATION | ~26 OpenMCAT items (Km/Vmax, feedback) | Strong (enzyme-reg, glycolysis, OXPHOS) | Non-enzyme menus need truth tables or scope narrow |
| THEORY_PLUS_STUDY | ~15–20 theory/data items | Moderate (psych/soc theories) | Need ~10 hand-verified THEORY few-shots before bulk gen |

---

## Contamination firewall (plan_v2)

1. Blocklist: 20 eval-heldout FP uids + 30 paraphrase card_ids + litmus 15-note uids
2. Embedding dedup: cosine < **0.85** vs any eval artifact (pre-registered threshold)
3. OpenMCAT stem blocklist: all 169 stems (when bank available)
4. Train-synthetic notes: teacher-authored, deduped against eval pools

---

## Recommended immediate artifacts

| Artifact | Purpose |
| :--- | :--- |
| `data/splits.json` | Frozen train/eval/litmus partitions |
| `data/blocklists/openmcat_stems.txt` | Prevent few-shot memorization |
| `data/gold/theory_plus_study_fewshots.json` | 10 hand-verified items (Day 1–2) |
