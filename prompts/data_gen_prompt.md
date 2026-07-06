# Data Generation Prompt (v1)

> **Purpose.** Teacher-model prompt for bulk SFT dataset generation. Forked from
> [`litmus_generation_prompt.md`](litmus_generation_prompt.md) with these deltas:
>
> | Litmus | Data gen |
> | :--- | :--- |
> | All in-scope archetypes listed | **MECHANISM_PERTURBATION + THEORY_PLUS_STUDY only** |
> | JSON **array** of N items | **Single JSON object** per call |
> | No self-labeling | **`answer_derivation` + menu member labels per option** |
> | Batch generation | **One item per call** |
>
> Run protocol: [`docs/planning/plan_v2.md`](../docs/planning/plan_v2.md) §2.3.

---

## SYSTEM

Same as litmus SYSTEM **except:**

1. Replace archetype list with only `MECHANISM_PERTURBATION` and `THEORY_PLUS_STUDY`.
2. Replace OUTPUT FORMAT with:

```text
OUTPUT FORMAT. Return ONLY a single JSON object, no prose before or after:
{
  "archetype": "MECHANISM_PERTURBATION|THEORY_PLUS_STUDY",
  "concept": "<concept slug from note>",
  "stem": "<full question stem>",
  "options": ["...", "...", "...", "..."],
  "answer": "A|B|C|D",
  "answer_derivation": "<=2-hop chain from scenario fingerprint to unique menu label>",
  "menu_labels": {
    "A": {"label": "<menu member>", "signature": "<fingerprint>", "verdict": "correct|wrong: <named error>"},
    "B": {...}, "C": {...}, "D": {...}
  },
  "rationale": {"correct": "...", "A": "...", "B": "...", "C": "...", "D": "..."},
  "unfamiliar_scenario": "<one line>",
  "reasoning_hops": <integer >= 2>
}
```

3. Add after rule 7:

```text
CLOSED MENUS (mandatory):
- MECHANISM_PERTURBATION: competitive (Km↑ Vmax=) · uncompetitive (Km↓ Vmax↓) ·
  noncompetitive/mixed (Km= or ↑, Vmax↓) · allosteric activation (Vmax↑) ·
  dissociation/denaturation (ruled out by structural datum). For feedback loops:
  increased · decreased · unchanged · compensatory.
- THEORY_PLUS_STUDY: supports · weakens (in-scope) · consistent-but-not-diagnostic ·
  contradicts a different claim · requires bounded revision. Exactly one is correct;
  the other three options must be the other menu members.
```

Include the two few-shot exemplars from litmus (MECH_PERT + THEORY_PLUS_STUDY) plus
10 gold items from `data/gold/theory_plus_study_fewshots.json` when available.

---

## USER

```text
SOURCE NOTE:
"""
{{NOTE}}
"""

Archetype: {{ARCHETYPE}}
Concept slug: {{CONCEPT}}
Difficulty: {{DIFFICULTY}}

Generate exactly ONE expert-grade MCAT question. Verify all 7 quality rules and
closed-menu conformance before returning. Output ONLY the JSON object.
```
