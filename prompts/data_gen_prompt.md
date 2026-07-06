# Data Generation Prompt (v1)

> **Purpose.** Teacher-model prompt for bulk SFT dataset generation. Forked from
> [`litmus_generation_prompt.md`](litmus_generation_prompt.md) with the deltas
> below. The exact in-scope archetype list is set by the feasibility verdict
> ([`docs/03_feasibility_assessment.md`](../docs/03_feasibility_assessment.md))
> and locked in the training plan
> ([`docs/planning/plan_v2.md`](../docs/planning/plan_v2.md) §2.3).
>
> | Litmus | Data gen |
> | :--- | :--- |
> | All in-scope archetypes listed | **Only the v1 scope archetypes** (per Deliverable 3) |
> | JSON **array** of N items | **Single JSON object** per call (or one 3-item stimulus set) |
> | Light self-labeling | **Full `answer_dating` + per-option `trap` labels** (mandatory) |
> | Batch generation | **One item (or one SET_OF_THREE) per call** |

---

## SYSTEM

Same as the litmus SYSTEM **except:**

1. Replace the archetype list with **only the v1-scope archetypes** named in the
   feasibility verdict (the closed stem menu and the 4-trap distractor menu are
   unchanged — they are the whole point).
2. Add, after gate 7:

```text
CLOSED MENUS (mandatory, self-label every item):
- STEM comes from the closed stem menu; name the stem_template id you used.
- EACH of the 3 distractors MUST be one of: WRONG_ERA | TRUE_BUT_IRRELEVANT |
  SCOPE_MISMATCH | PARTIALLY_TRUE, and the 3 must span >=2 distinct types.
- The keyed answer is derived as: (a claim licensed by the SOURCE) + (exactly one
  outside development from the developments table) whose date obeys the stem's
  time direction (cause < source_date < effect; "reflects/illustrates" is
  contemporaneous). State that date reasoning in `answer_dating`.
- Do NOT invent historical facts not attributable to the source or to standard
  APUSH-level knowledge; when unsure, choose a different development.
```

3. Replace OUTPUT FORMAT with a **single JSON object** carrying the verification
   fields the filter pipeline needs:

```text
OUTPUT FORMAT. Return ONLY a single JSON object, no prose before or after:
{
  "stimulus_id": "<id from data/seed_stimuli.jsonl>",
  "archetype": "<one v1-scope archetype id>",
  "stem_template": "<stem_template id>",
  "period": <1-9>,
  "theme": "<NAT|WXT|GEO|MIG|PCE|WOR|ARC|SOC>",
  "stem": "<full stem, referencing the source>",
  "options": ["...", "...", "...", "..."],
  "answer": "A|B|C|D",
  "answer_dating": "<keyed development's date + why it obeys the stem time direction>",
  "options_meta": {
    "A": {"development": "<named development or id>", "verdict": "correct | WRONG_ERA | TRUE_BUT_IRRELEVANT | SCOPE_MISMATCH | PARTIALLY_TRUE", "why": "<the named error, or why correct>"},
    "B": {...}, "C": {...}, "D": {...}
  },
  "requires_outside_knowledge": "<the outside development the answer depends on, not stated in the source>",
  "reasoning_hops": <integer >= 2>
}
```

Include the two litmus few-shot exemplars (`CAUSE_OF_SOURCE` + `EVIDENCE_SUPPORTS_CLAIM`)
plus any hand-verified gold items in `data/gold/` when available.

---

## USER

```text
SOURCE (the stimulus the question must hang on):
"""
{{SOURCE_TEXT}}
"""
ATTRIBUTION: {{ATTRIBUTION}}   (author, type, date)
STIMULUS_ID: {{STIMULUS_ID}}
PERIOD/THEME: {{PERIOD}} / {{THEME}}

Archetype: {{ARCHETYPE}}
Difficulty: {{DIFFICULTY}}

Generate exactly ONE expert-grade APUSH stimulus-based MCQ (or one SET_OF_THREE if
requested). Verify all gates, the anachronism date rule, and that every distractor
is labeled with a trap type before returning. Output ONLY the JSON object.
```

---

## Downstream filter (the closed menus make this cheap)

The generated object is designed so the filter stack can run mostly
**programmatically** (the SLM-feasibility lever):

1. **Programmatic:** valid JSON; 4 options; one key; `reasoning_hops >= 2`; no
   `all/none/always/never`; option homogeneity; **anachronism date-check** on
   `answer_dating` + `options_meta` dates vs
   [`../data/apush_key_developments.json`](../data/apush_key_developments.json);
   trap-diversity (>=2 distinct trap types); source-leak (answer not a verbatim
   span of the source).
2. **LLM judge (different model family):** the `quality_checks` rubric +
   historical-accuracy / single-best-answer (`key_valid`).
3. **Key verifier (third family + self-consistency vote):** independent k-of-n
   solve of the item; reject on disagreement or double-correct. This is the SC-KEY
   crux gate (see Deliverable 3).
