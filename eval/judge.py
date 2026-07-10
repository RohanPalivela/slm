"""
LLM-as-judge for the eval harness. Scores one generated item against the APUSH
quality bar. Use a different model family than the model under test when possible.
Returns a normalized dict; `expert_grade` and `key_valid` are
computed in code from the judge's booleans for consistency.
"""
from __future__ import annotations
import json

import providers
from prompt_loader import extract_items

JUDGE_SYSTEM = """You are a senior AP U.S. History assessment expert grading a \
single machine-generated stimulus-based multiple-choice question. You know U.S. \
history well and you are NOT the model that wrote the item.

Grade like a real test-development reviewer: be STRICT about correctness (is the \
keyed answer right, is it uniquely best, does the skill match the command phrase) \
but FAIR about craft. An item a real APUSH exam would actually use is expert-grade \
even if a distractor could be marginally stronger. Do NOT invent flaws or hold \
items to a standard of perfection the operational test itself does not meet.

You will receive the SOURCE (stimulus) and the ITEM (stem, 4 options, keyed \
answer, rationale). Judge ONLY against the source + standard APUSH knowledge.

CALIBRATION — apply these two most-misjudged fields exactly as written:
- distractors_period_plausible is TRUE unless a distractor is genuinely absurd,
  fabricated (not real history), or off-topic FILLER with no real connection to the
  question's theme. A distractor is STILL plausible if it is a real development that
  is merely from a NEIGHBORING era, somewhat weaker, or slightly off — those are
  legitimate traps that test chronology/theme discrimination. Mark FALSE only when a
  distractor is (a) not real history, or (b) so obviously wrong-century AND off-theme
  that essentially every student eliminates it instantly. ONE soft-but-real
  distractor among the three does NOT make the set implausible.
- spec_adherence: 2 = operationally usable on a real test (correct, uniquely-best
  key + right skill + no disqualifying flaw), EVEN IF one distractor is soft. 1 = a
  genuine craft weakness short of disqualifying (e.g. two weak/filler distractors, a
  length or grammar tell, or a borderline second-best option). 0 = a DISQUALIFYING
  flaw only (wrong or non-unique key, more than one defensible answer, the answer
  merely echoes the source, or an all/none-of-the-above option). Do NOT drop to 1
  just because a single distractor could be stronger.

Return ONLY a JSON object (no prose) with these fields:
{
  "requires_outside_knowledge": true|false,   // answering needs a development NOT stated in the source (not a paraphrase of it)
  "every_distractor_named_trap": true|false,  // each wrong option maps to a real error: wrong-era / true-but-irrelevant / scope-mismatch / partially-true
  "distractors_period_plausible": true|false, // per CALIBRATION above: FALSE only for absurd/fabricated/off-topic filler, not for a merely-soft or neighboring-era trap
  "skill_matches_command_phrase": true|false, // a "cause" stem is answered by a cause; "led to" by an effect; etc.
  "key_historically_correct": true|false,     // the keyed answer is factually correct history
  "key_uniquely_best": true|false,            // exactly one option is defensibly best; no second option is also correct
  "single_best_answer": true|false,           // overall: one clearly-best answer
  "spec_adherence": 0|1|2,                     // per CALIBRATION above: 2 = usable on a real test (a single soft distractor is still a 2); 1 = real craft weakness; 0 = disqualifying flaw
  "distractor_craft": 0|1|2,                   // 2 = every distractor a real tempting trap (one soft-but-real one is fine); 1 = a couple are weak; 0 = a genuinely absurd/fabricated/filler option
  "outside_knowledge_skill_fit": 0|1|2,        // 0 echoes the source or answer mismatches the skill; 2 genuine outside knowledge + right skill
  "notes": "<one sentence: the main flaw, or 'clean'>"
}"""

JUDGE_USER_TMPL = """SOURCE ({attribution}):
\"\"\"
{source_text}
\"\"\"

ITEM:
archetype: {archetype}
stem: {stem}
options:
{options}
keyed answer: {answer}
answer_dating: {answer_dating}
rationale: {rationale}

Grade it. Return ONLY the JSON object."""


def _fmt_options(opts):
    out = []
    for i, o in enumerate(opts or []):
        out.append(f"  {'ABCD'[i] if i < 4 else '?'}) {o}")
    return "\n".join(out)


def build_judge_prompt(source: dict, item: dict) -> tuple[str, str]:
    user = JUDGE_USER_TMPL.format(
        attribution=source.get("attribution", ""),
        source_text=source.get("text", ""),
        archetype=item.get("archetype", ""),
        stem=item.get("stem", ""),
        options=_fmt_options(item.get("options", [])),
        answer=item.get("answer", ""),
        answer_dating=item.get("answer_dating", ""),
        rationale=json.dumps(item.get("rationale", {}), ensure_ascii=False),
    )
    return JUDGE_SYSTEM, user


def _mock_judgment(role: str) -> dict:
    # dry-run: make the teacher clearly pass and candidates wobble, so the
    # base-vs-tuned/decision logic visibly exercises.
    strong = role in ("teacher",)
    return {
        "requires_outside_knowledge": True,
        "every_distractor_named_trap": True,
        "distractors_period_plausible": True,
        "skill_matches_command_phrase": True,
        "key_historically_correct": True,
        "key_uniquely_best": strong,
        "single_best_answer": strong,
        "spec_adherence": 2 if strong else 1,
        "distractor_craft": 2 if strong else 1,
        "outside_knowledge_skill_fit": 2 if strong else 1,
        "notes": "mock",
    }


def _normalize(j: dict) -> dict:
    b = lambda k: bool(j.get(k, False))
    g = lambda k: int(j.get(k, 0)) if str(j.get(k, 0)).isdigit() else 0
    out = {
        "requires_outside_knowledge": b("requires_outside_knowledge"),
        "every_distractor_named_trap": b("every_distractor_named_trap"),
        "distractors_period_plausible": b("distractors_period_plausible"),
        "skill_matches_command_phrase": b("skill_matches_command_phrase"),
        "key_historically_correct": b("key_historically_correct"),
        "key_uniquely_best": b("key_uniquely_best"),
        "single_best_answer": b("single_best_answer"),
        "spec_adherence": g("spec_adherence"),
        "distractor_craft": g("distractor_craft"),
        "outside_knowledge_skill_fit": g("outside_knowledge_skill_fit"),
        "notes": str(j.get("notes", ""))[:300],
    }
    out["key_valid"] = out["key_historically_correct"] and out["key_uniquely_best"]
    return out


def judge_item(judge_cfg: dict, source: dict, item: dict, *, role: str = "") -> dict:
    if judge_cfg.get("provider") == "mock":
        return _normalize(_mock_judgment(role))
    system, user = build_judge_prompt(source, item)
    raw = providers.generate(judge_cfg, system, user, temperature=0.0, role="judge")
    parsed = extract_items(raw)
    if not parsed:
        return _normalize({"notes": "judge returned unparseable output"})
    return _normalize(parsed[0])


def near_grade(prog_ok: bool, j: dict) -> bool:
    """Near-miss tier: passes every expert-grade gate EXCEPT the strict
    spec_adherence==2 (i.e. all disqualifiers clean + every graded dim >=1 + a
    valid key). Separates 'one distractor is soft' (spec_adherence==1) from
    'fundamentally broken', so the report doesn't collapse both into 0."""
    judge_disq = (j["requires_outside_knowledge"] and j["every_distractor_named_trap"]
                  and j["distractors_period_plausible"] and j["skill_matches_command_phrase"]
                  and j["single_best_answer"] and j["key_valid"])
    dims_ok = min(j["spec_adherence"], j["distractor_craft"], j["outside_knowledge_skill_fit"]) >= 1
    return bool(prog_ok and judge_disq and dims_ok)


def expert_grade(prog_ok: bool, j: dict) -> bool:
    """All disqualifying checks pass (programmatic + judge) AND every
    graded dim >=1 AND spec_adherence==2 AND a valid key."""
    return bool(near_grade(prog_ok, j) and j["spec_adherence"] == 2)
