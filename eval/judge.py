"""
LLM-as-judge for the litmus harness. Scores one generated item against the
taxonomy quality bar (docs/02 §4b). MUST be a different model family than the
model under test. Returns a normalized dict; `expert_grade` and `key_valid` are
computed in code from the judge's booleans for consistency.
"""
from __future__ import annotations
import json

import providers
from prompt_loader import extract_items

JUDGE_SYSTEM = """You are a senior AP U.S. History assessment expert grading a \
single machine-generated stimulus-based multiple-choice question. You are strict, \
fair, and you know U.S. history well. You are NOT the model that wrote the item.

You will receive the SOURCE (stimulus) and the ITEM (stem, 4 options, keyed \
answer, rationale). Judge ONLY against the source + standard APUSH knowledge.

Return ONLY a JSON object (no prose) with these fields:
{
  "requires_outside_knowledge": true|false,   // answering needs a development NOT stated in the source (not a paraphrase of it)
  "every_distractor_named_trap": true|false,  // each wrong option maps to a real error: wrong-era / true-but-irrelevant / scope-mismatch / partially-true
  "distractors_period_plausible": true|false, // each distractor is a real, era-plausible development a good student would consider (no absurd/off-topic filler)
  "skill_matches_command_phrase": true|false, // a "cause" stem is answered by a cause; "led to" by an effect; etc.
  "key_historically_correct": true|false,     // the keyed answer is factually correct history
  "key_uniquely_best": true|false,            // exactly one option is defensibly best; no second option is also correct
  "single_best_answer": true|false,           // overall: one clearly-best answer
  "spec_adherence": 0|1|2,                     // 0 violates >=1 disqualifying check; 1 minor wobble; 2 fully expert-grade
  "distractor_craft": 0|1|2,                   // 0 has filler/absurd option; 2 every distractor a named, plausible trap
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


def expert_grade(prog_ok: bool, j: dict) -> bool:
    """docs/02 §4b: all disqualifying checks pass (programmatic + judge) AND every
    graded dim >=1 AND spec_adherence==2 AND a valid key."""
    judge_disq = (j["requires_outside_knowledge"] and j["every_distractor_named_trap"]
                  and j["distractors_period_plausible"] and j["skill_matches_command_phrase"]
                  and j["single_best_answer"] and j["key_valid"])
    dims_ok = min(j["spec_adherence"], j["distractor_craft"], j["outside_knowledge_skill_fit"]) >= 1
    return bool(prog_ok and judge_disq and dims_ok and j["spec_adherence"] == 2)
