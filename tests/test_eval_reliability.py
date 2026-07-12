from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import judge  # noqa: E402
import generate as dataset_generate  # noqa: E402
import checks  # noqa: E402
import repair  # noqa: E402
import verifier  # noqa: E402
from date_utils import direction_against_source  # noqa: E402
from prompt_loader import (  # noqa: E402
    canonicalize_item_archetype,
    generation_format_diagnostics,
)


VALID_JUDGMENT = {
    "requires_outside_knowledge": True,
    "every_distractor_named_trap": True,
    "distractors_period_plausible": True,
    "skill_matches_command_phrase": True,
    "key_historically_correct": True,
    "key_uniquely_best": True,
    "single_best_answer": True,
    "spec_adherence": 2,
    "distractor_craft": 2,
    "outside_knowledge_skill_fit": 2,
    "notes": "clean",
}


class FormatDiagnosticsTests(unittest.TestCase):
    def test_detects_v3_object_with_trailing_array_bracket(self) -> None:
        raw = '{"archetype":"EFFECT_OF_SOURCE","options":["a","b","c","d"]}]'
        result = generation_format_diagnostics(raw)
        self.assertEqual(result["bucket"], "object_with_trailing_array_bracket")
        self.assertFalse(result["strict_array_contract"])

    def test_strict_array_is_product_success(self) -> None:
        result = generation_format_diagnostics('[{"archetype":"CAUSE_OF_SOURCE"}]')
        self.assertEqual(result["bucket"], "strict_array")
        self.assertTrue(result["strict_array_contract"])
        self.assertTrue(result["strict_top_level_array"])
        self.assertEqual(result["exact_item_count"], 1)
        self.assertTrue(result["exact_one_dictionary"])
        self.assertTrue(result["no_think_tags"])
        self.assertTrue(result["exact_contract_valid"])

    def test_markdown_fenced_array_violates_product_contract(self) -> None:
        result = generation_format_diagnostics(
            '```json\n[{"archetype":"CAUSE_OF_SOURCE"}]\n```'
        )
        self.assertEqual(result["bucket"], "markdown_fenced_array")
        self.assertFalse(result["strict_array_contract"])
        self.assertFalse(result["exact_contract_valid"])

    def test_detects_complete_item_followed_by_truncated_repeat(self) -> None:
        raw = '[{"archetype":"CAUSE_OF_SOURCE"},{"archetype":"CAUSE'
        result = generation_format_diagnostics(raw)
        self.assertEqual(result["bucket"], "complete_item_then_unclosed_trailing_output")
        self.assertEqual(result["tolerant_item_count"], 1)

    def test_exact_contract_rejects_non_dictionary_and_multiple_items(self) -> None:
        scalar = generation_format_diagnostics("[1]")
        multiple = generation_format_diagnostics('[{"a":1},{"b":2}]')
        self.assertTrue(scalar["strict_top_level_array"])
        self.assertFalse(scalar["exact_one_dictionary"])
        self.assertFalse(scalar["exact_contract_valid"])
        self.assertEqual(multiple["exact_item_count"], 2)
        self.assertFalse(multiple["exact_contract_valid"])

    def test_exact_contract_rejects_trailing_content_and_think_tags(self) -> None:
        trailing = generation_format_diagnostics('[{"a":1}] trailing prose')
        malformed_suffix = generation_format_diagnostics('"]}]"')
        thinking = generation_format_diagnostics('<think>reasoning</think>[{"a":1}]')
        self.assertFalse(trailing["exact_contract_valid"])
        self.assertFalse(malformed_suffix["exact_contract_valid"])
        self.assertFalse(thinking["no_think_tags"])
        self.assertFalse(thinking["exact_contract_valid"])


class ItemSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = {"period": 5, "text": "source", "year": 1863}
        self.item = {
            "archetype": "CAUSE_OF_SOURCE",
            "period": 5,
            "theme": "PCE",
            "stem": "Which development most directly caused the source's position?",
            "options": ["one", "two", "three", "four"],
            "answer": "A",
            "answer_dating": "The development occurred before the 1863 source.",
            "rationale": {
                "correct": "The development directly caused the source position.",
                "A": "correct",
                "B": "SCOPE_MISMATCH: too broad",
                "C": "PARTIALLY_TRUE: wrong mechanism",
                "D": "TRUE_BUT_IRRELEVANT: wrong theme",
            },
            "trap_types": [
                "SCOPE_MISMATCH",
                "PARTIALLY_TRUE",
                "TRUE_BUT_IRRELEVANT",
            ],
            "requires_outside_knowledge": "A prior development.",
        }

    def check(self, item=None):
        emitted = canonicalize_item_archetype(
            item or self.item,
            requested_archetype="CAUSE_OF_SOURCE",
        )
        return checks.run_checks(
            emitted,
            self.source,
            requested_archetype="CAUSE_OF_SOURCE",
        )

    def test_complete_exact_schema_passes(self) -> None:
        result = self.check()
        self.assertTrue(result["schema_valid"])
        self.assertTrue(result["schema_ok"])
        self.assertTrue(result["trap_rationales_align"])

    def test_trap_types_must_match_wrong_option_rationale_order(self) -> None:
        item = dict(self.item)
        item["trap_types"] = list(reversed(self.item["trap_types"]))
        result = self.check(item)
        self.assertFalse(result["trap_rationales_align"])
        self.assertFalse(result["schema_valid"])

    def test_missing_field_and_wrong_exact_type_fail(self) -> None:
        missing = dict(self.item)
        missing.pop("requires_outside_knowledge")
        wrong_type = dict(self.item, period=True)
        self.assertFalse(self.check(missing)["required_fields_present"])
        self.assertFalse(self.check(wrong_type)["field_types_exact"])

    def test_invalid_theme_wrong_period_and_archetype_fail(self) -> None:
        self.assertFalse(self.check(dict(self.item, theme="POL"))["theme_valid"])
        self.assertFalse(self.check(dict(self.item, period=7))["period_matches_source"])
        mismatch = canonicalize_item_archetype(
            dict(self.item, archetype="EFFECT_OF_SOURCE"),
            requested_archetype="CAUSE_OF_SOURCE",
        )
        result = checks.run_checks(mismatch, self.source)
        self.assertFalse(result["archetype_matches_request"])
        self.assertFalse(result["schema_valid"])
        self.assertTrue(result["schema_ok"])

    def test_options_answer_and_rationale_require_exact_contract_types(self) -> None:
        bad_options = dict(self.item, options=["one", "two", "three", 4])
        bad_answer = dict(self.item, answer="A.")
        bad_rationale = dict(
            self.item,
            rationale={**self.item["rationale"], "D": 4},
        )
        self.assertFalse(self.check(bad_options)["four_string_options"])
        self.assertFalse(self.check(bad_answer)["answer_key_valid"])
        self.assertFalse(self.check(bad_rationale)["rationale_mapping_complete"])


class DateDirectionTests(unittest.TestCase):
    def test_same_year_directional_language_is_checked(self) -> None:
        causes = {"CAUSE_OF_SOURCE"}
        effects = {"EFFECT_OF_SOURCE"}
        self.assertEqual(
            direction_against_source(
                "CAUSE_OF_SOURCE",
                "The dispute arose before the court's 1957 ruling.",
                1957,
                causes,
                effects,
            ),
            "pass",
        )
        self.assertEqual(
            direction_against_source(
                "EFFECT_OF_SOURCE",
                "The policy expanded after its enactment in 1957.",
                1957,
                causes,
                effects,
            ),
            "pass",
        )
        self.assertEqual(
            direction_against_source(
                "CAUSE_OF_SOURCE",
                "The development occurred after the 1957 source.",
                1957,
                causes,
                effects,
            ),
            "fail",
        )


class JudgeRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = {"provider": "openai_compatible", "parse_attempts": 3}
        self.source = {"attribution": "source", "text": "text"}
        self.item = {
            "archetype": "CAUSE_OF_SOURCE",
            "stem": "stem",
            "options": ["a", "b", "c", "d"],
            "answer": "A",
            "answer_dating": "dating",
            "rationale": {},
        }

    @patch("judge.providers.generate")
    def test_retries_parse_failure_and_saves_raw(self, generate) -> None:
        generate.side_effect = ["not json", json.dumps(VALID_JUDGMENT)]
        result = judge.judge_item(self.cfg, self.source, self.item)
        self.assertEqual(result["_status"], "ok")
        self.assertEqual(result["_attempts"], 2)
        self.assertEqual(result["_raw_responses"], ["not json", json.dumps(VALID_JUDGMENT)])
        self.assertTrue(result["key_valid"])

    @patch("judge.providers.generate", return_value="not json")
    def test_unresolved_judge_is_inconclusive(self, _generate) -> None:
        result = judge.judge_item(self.cfg, self.source, self.item)
        self.assertEqual(result["_status"], "unparseable")
        self.assertIsNone(result["key_valid"])
        self.assertIsNone(judge.near_grade(True, result))
        self.assertIsNone(judge.expert_grade(True, result))
        self.assertEqual(len(result["_raw_responses"]), 3)


class TrainingGenerationTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = {"name": "model", "provider": "mock", "model": "mock"}
        self.source = {"attribution": "source", "text": "text"}
        self.item = {
            "archetype": "CAUSE_OF_SOURCE",
            "stem": "Which development most directly caused the source's position?",
            "options": ["a", "b", "c", "d"],
            "answer": "A",
            "answer_dating": "The keyed development came before the source.",
            "rationale": {"correct": "because", "A": "correct", "B": "x", "C": "y", "D": "z"},
            "trap_types": ["PARTIALLY_TRUE", "SCOPE_MISMATCH", "TRUE_BUT_IRRELEVANT"],
            "requires_outside_knowledge": "outside fact",
        }

    @patch("repair.providers.generate")
    def test_repair_trace_preserves_raw_response(self, generate) -> None:
        raw = json.dumps(self.item)
        generate.return_value = raw
        repaired, trace = repair.repair_item_with_trace(
            self.cfg,
            self.source,
            self.item,
            temperature=0.2,
        )
        self.assertTrue(trace["accepted"])
        self.assertEqual(trace["raw"], raw)
        self.assertTrue(repaired["_repaired"])

    @patch("verifier.providers.generate")
    def test_verifier_trace_preserves_every_vote_and_requires_unanimity(self, generate) -> None:
        generate.side_effect = [
            '{"answer":"A","confidence":0.9}',
            '{"answer":"A","confidence":0.9}',
            '{"answer":"B","confidence":0.6}',
        ]
        result = verifier.verify_item(self.cfg, self.source, self.item)
        self.assertFalse(result["verified"])
        self.assertEqual(result["threshold"], 1.0)
        self.assertEqual(len(result["attempts"]), 3)
        self.assertEqual(result["attempts"][0]["raw"], '{"answer":"A","confidence":0.9}')

    @patch("verifier.providers.generate")
    def test_verifier_fails_closed_when_a_vote_is_unparseable(self, generate) -> None:
        generate.side_effect = [
            '{"answer":"A","confidence":0.9}',
            '{"answer":"A","confidence":0.9}',
            "I cannot determine a unique answer.",
        ]
        result = verifier.verify_item(
            self.cfg,
            self.source,
            self.item,
            threshold=2 / 3,
        )
        self.assertFalse(result["verified"])
        self.assertEqual(result["n_solved"], 2)

    def test_model_metadata_redacts_literal_credentials(self) -> None:
        metadata = dataset_generate._model_metadata({
            **self.cfg,
            "api_key": "secret-value",
            "api_key_env": "MODEL_API_KEY",
            "headers": {"access_token": "nested-secret"},
        })
        self.assertEqual(metadata["config"]["api_key"], "<redacted>")
        self.assertEqual(metadata["config"]["api_key_env"], "MODEL_API_KEY")
        self.assertEqual(metadata["config"]["headers"]["access_token"], "<redacted>")

    def test_verifier_fallback_requires_an_explicit_answer(self) -> None:
        self.assertIsNone(verifier._parse_letter("I cannot determine a unique answer."))
        self.assertEqual(verifier._parse_letter("Answer: C"), "C")
        self.assertEqual(verifier._parse_letter('{"answer":"D","confidence":0.8}'), "D")


if __name__ == "__main__":
    unittest.main()
