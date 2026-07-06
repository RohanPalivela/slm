# Data Generation Prompt (v2)

> **Purpose.** Teacher-model prompt for bulk SFT dataset generation. Forked from
> [`litmus_generation_prompt.md`](litmus_generation_prompt.md) with the deltas
> below. The exact in-scope archetype list is set by the feasibility verdict
> ([`docs/03_feasibility_assessment.md`](../docs/03_feasibility_assessment.md))
> and locked in the training plan
> ([`docs/planning/plan_v2.md`](../docs/planning/plan_v2.md) §3.3).
>
> **v2 changes (validator C1/C2):** input is a provided primary SOURCE **+ optional
> study NOTE** (`{{NOTE}}` slot re-added); grounding is now **mechanical** — a
> period-windowed **`{{CANDIDATE_DEVELOPMENTS}}`** set is injected and the answer +
> all distractors must be chosen **by `development_id`** from it; the free-recall
> ("standard APUSH-level knowledge") escape hatch is **removed**; Stage-A filter
> **hard-rejects** any option whose `development_id` is not in the injected set.
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
CLOSED MENUS + GROUNDING (mandatory, self-label every item):
- STEM comes from the closed stem menu; name the stem_template id you used.
- GROUNDING (HARD RULE — no exceptions): the keyed answer AND all 3 distractors
  MUST each be chosen from the injected CANDIDATE_DEVELOPMENTS set (see USER
  block), referenced BY `development_id`. You may NOT introduce, name, or key any
  development that is absent from that set. There is NO "standard APUSH-level
  knowledge" fallback and NO free recall. If the candidate set contains no
  defensible most-direct answer for this stem, DO NOT invent one — return
  {"skip": true, "reason": "<why nothing in the set is keyable here>"} instead.
- The keyed answer is derived as: (a claim licensed by the SOURCE) + (exactly one
  candidate development, chosen by development_id) whose date obeys the stem's
  time direction (cause < source_date; effect > source_date). State that date
  reasoning in `answer_dating`, citing the candidate's year.
- EACH of the 3 distractors MUST be a candidate development labeled with exactly
  one trap: WRONG_ERA | TRUE_BUT_IRRELEVANT | SCOPE_MISMATCH | PARTIALLY_TRUE, and
  the 3 must span >=2 distinct trap types. At least one distractor should be a
  specific-vs-background SCOPE_MISMATCH or a WRONG_ERA date violation.
```

3. Replace OUTPUT FORMAT with a **single JSON object** carrying the verification
   fields the filter pipeline needs:

```text
OUTPUT FORMAT. Return ONLY a single JSON object, no prose before or after. Either a
generated item OR a skip object {"skip": true, "reason": "..."} when the candidate
set has no defensible most-direct answer:
{
  "stimulus_id": "<id from data/seed_stimuli.jsonl>",
  "note_conditioned": <true|false>,      // true if a STUDY NOTE steered this item
  "archetype": "<one v1-scope archetype id>",
  "stem_template": "<stem_template id>",
  "period": <1-9>,
  "theme": "<NAT|WXT|GEO|MIG|PCE|WOR|ARC|SOC>",
  "stem": "<full stem, referencing the source>",
  "options": ["...", "...", "...", "..."],
  "answer": "A|B|C|D",
  "answer_dating": "<keyed candidate's year + why it obeys the stem time direction>",
  "options_meta": {
    "A": {"development_id": "<id — MUST be a development_id from CANDIDATE_DEVELOPMENTS>", "verdict": "correct | WRONG_ERA | TRUE_BUT_IRRELEVANT | SCOPE_MISMATCH | PARTIALLY_TRUE", "why": "<the named error, or why correct>"},
    "B": {...}, "C": {...}, "D": {...}
  },
  "requires_outside_knowledge": "<the outside candidate development the answer depends on, not stated in the source>",
  "reasoning_hops": <integer >= 2>
}
```

Include the `CAUSE_OF_SOURCE` litmus few-shot exemplar plus hand-verified
`CAUSE_OF_SOURCE` / `EFFECT_OF_SOURCE` gold items from `data/gold/` when available
(the second litmus exemplar, `EVIDENCE_SUPPORTS_CLAIM`, is F5 and OUT of v1 scope —
do not use it here).

---

## USER

```text
SOURCE (the stimulus the question must hang on):
"""
{{SOURCE_TEXT}}
"""
ATTRIBUTION: {{ATTRIBUTION}}   (author, type, date)
STIMULUS_ID: {{STIMULUS_ID}}
SOURCE_DATE: {{SOURCE_DATE}}   (integer year — anchors the anachronism date-check)
PERIOD/THEME: {{PERIOD}} / {{THEME}}

STUDY NOTE (OPTIONAL — if non-empty, steer the item toward the development this
note points at; if empty, ignore it and pick the best candidate for the stem):
"""
{{NOTE}}
"""

CANDIDATE_DEVELOPMENTS (the CLOSED grounding set — choose the answer AND every
distractor BY development_id from THIS LIST ONLY; period-windowed around the source
from data/apush_key_developments.json, and includes both correct-direction keyable
developments and off-direction/off-era ones for the traps):
{{CANDIDATE_DEVELOPMENTS}}
(each row: development_id | name | year | period | role[keyable|distractor_only])

Archetype: {{ARCHETYPE}}
Difficulty: {{DIFFICULTY}}

Generate exactly ONE expert-grade APUSH stimulus-based MCQ (or one SET_OF_THREE if
requested), choosing the answer and every distractor BY development_id from
CANDIDATE_DEVELOPMENTS. Verify all gates, the anachronism date rule, and that every
distractor is labeled with a trap type before returning. If the candidate set has
no defensible most-direct answer for this stem, return {"skip": true, "reason": ...}.
Output ONLY the JSON object.
```

---

## Downstream filter (the closed menus make this cheap)

The generated object is designed so the filter stack can run mostly
**programmatically** (the SLM-feasibility lever):

1. **Programmatic:** valid JSON; 4 options; one key; `reasoning_hops >= 2`; no
   `all/none/always/never`; option homogeneity; **GROUNDING HARD-REJECT** — every
   `options_meta.*.development_id` MUST be present in the injected
   CANDIDATE_DEVELOPMENTS set for this stimulus; reject the item if any option
   cites an id absent from that set (this is what mechanically enforces P5 — no
   ungrounded key or distractor can pass); **anachronism date-check** on
   `answer_dating` + `options_meta` ids/dates vs
   [`../data/apush_key_developments.json`](../data/apush_key_developments.json);
   trap-diversity (>=2 distinct trap types); source-leak (answer not a verbatim
   span of the source). (`{"skip": true}` objects are logged, not counted as
   failures.)
2. **LLM judge (different model family):** the `quality_checks` rubric +
   historical-accuracy / single-best-answer (`key_valid`).
3. **Key verifier (third family + self-consistency vote):** independent k-of-n
   solve of the item; reject on disagreement or double-correct. This is the SC-KEY
   crux gate (see Deliverable 3).
