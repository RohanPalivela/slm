from __future__ import annotations

import ast
import json
import re
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from notebook_runtime import (  # noqa: E402
    aggregate_attempt_metrics,
    append_jsonl_group,
    attempt_contract_outcome,
    attempt_key,
    attempt_seed,
    dedupe_rows,
    load_jsonl_groups,
    runs_for_model,
    score_key,
    source_clustered_paired_ci,
    stable_hash,
)
from source_utils import source_genre  # noqa: E402


class NotebookRuntimeTests(unittest.TestCase):
    def test_gpu_notebook_uses_batched_resumable_execution(self) -> None:
        notebook = json.loads(
            (ROOT / "notebooks/eval_hf_gpu.ipynb").read_text(encoding="utf-8")
        )
        code = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook["cells"]
            if cell.get("cell_type") == "code"
        )
        compile(code, "eval_hf_gpu.ipynb", "exec")
        self.assertIn("RUNS = 2", code)
        self.assertIn("TEACHER_RUNS = 1", code)
        self.assertNotIn("num_return_sequences", code)
        self.assertIn("run_generation_preflight", code)
        self.assertIn("PREFLIGHT_PASSED", code)
        self.assertNotIn("PREFLIGHT_SOURCE_LIMIT", code)
        self.assertIn("if execution_failures:", code)
        self.assertIn("if outcome_failures:", code)
        self.assertIn("'outcome_reasons':sorted(set(outcome_reasons))", code)
        self.assertNotIn("if failures:\n", code)
        self.assertIn("ThreadPoolExecutor(max_workers=API_MAX_WORKERS)", code)
        self.assertIn("append_jsonl_group(generation_path, new_attempts)", code)
        self.assertIn("load_jsonl_groups(scoring_path)", code)
        self.assertIn("aggregate_attempt_metrics", code)
        self.assertIn("source_clustered_paired_ci", code)
        self.assertNotIn("statistics.mean", code)
        self.assertIn("from hf_local import HFLocalEngine", code)
        self.assertNotIn("KEEP_NO_THINK_PREFILL", code)
        self.assertNotIn("FORCE_JSON_ARRAY_PREFIX", code)
        self.assertNotIn("USE_NO_THINK_SOFT_SWITCH", code)
        self.assertNotIn("RUN_NO_THINK_ABLATION", code)
        self.assertIn("keep_no_think_prefill=True", code)
        self.assertIn("force_json_array_prefix=False", code)
        self.assertIn("use_no_think_soft_switch=False", code)
        self.assertIn("stopping_enabled=True", code)
        self.assertIn(
            "os.environ['APUSH_GITHUB_REF'] = "
            "'REPLACE_WITH_FULL_40_CHARACTER_COMMIT_SHA'",
            code,
        )
        self.assertIn("re.fullmatch(r'[0-9a-f]{40}', GITHUB_REF)", code)
        self.assertIn("training_run_metadata.json", code)
        self.assertIn(
            "APUSH_ADAPTER_ID = 'rohanpalviela/qwen3-4b-apush-v4-semantic-audited-lora'",
            code,
        )
        self.assertIn(
            "EXPECTED_ADAPTER_TRAINING_DATA_SHA256 = "
            "'fb49a00b5edb413cfd004f398261cc409a193da6d1afd8a2187166b206a8e608'",
            code,
        )
        self.assertIn("TRAINING_RUN_METADATA.get('use_audited_data') is not True", code)

        tree = ast.parse(code)
        cohort = next(
            ast.literal_eval(node.value)
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "REPRESENTATIVE_EVAL_SOURCE_IDS"
                for target in node.targets
            )
        )
        splits = json.loads((ROOT / "data/splits.json").read_text(encoding="utf-8"))
        heldout = set(splits["splits"]["EVAL_HELDOUT"]["source_ids"])
        self.assertEqual(len(cohort), 14)
        self.assertEqual(len(set(cohort)), 14)
        self.assertLessEqual(set(cohort), heldout)
        stimuli = {
            row["id"]: row
            for row in (
                json.loads(line)
                for line in (ROOT / "data/seed_stimuli.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
                if line.strip()
            )
        }
        self.assertEqual(
            Counter(source_genre(stimuli[source_id]) for source_id in cohort),
            Counter(
                {
                    "law_or_constitution": 6,
                    "court_opinion": 3,
                    "executive_action": 2,
                    "other_primary_text": 1,
                    "treaty_or_compact": 1,
                    "speech_or_argument": 1,
                }
            ),
        )
        years = [int(re.search(r"(\d{4})$", source_id).group(1)) for source_id in cohort]
        for start, end in ((1776, 1800), (1801, 1848), (1849, 1877), (1878, 1945), (1946, 1980)):
            self.assertTrue(any(start <= year <= end for year in years))

    def test_canonical_cell_hashes_match_function_definitions_only(self) -> None:
        notebook = json.loads(
            (ROOT / "notebooks/eval_hf_gpu.ipynb").read_text(encoding="utf-8")
        )
        cells = ["".join(cell.get("source", [])) for cell in notebook["cells"]]
        for function_name in (
            "generate_model_repetitions",
            "run_generation_preflight",
        ):
            definition = re.compile(
                rf"(?m)^def\s+{re.escape(function_name)}\s*\("
            )
            self.assertEqual(
                sum(bool(definition.search(cell)) for cell in cells),
                1,
            )

        provenance_cell = next(
            cell for cell in cells if "def canonical_cell_sha256" in cell
        )
        self.assertIn("definition.search", provenance_cell)
        self.assertNotIn(
            "canonical_cell_sha256('def generate_model_repetitions')",
            provenance_cell,
        )

    def test_shared_hf_engine_pins_base_tokenizer_and_independent_row_seeds(self) -> None:
        source = (ROOT / "eval/hf_local.py").read_text(encoding="utf-8")
        compile(source, "eval/hf_local.py", "exec")
        self.assertIn("AutoTokenizer.from_pretrained(\n            self.base_model_id", source)
        self.assertIn("revision=self.base_model_revision", source)
        self.assertNotIn("num_return_sequences", source)
        self.assertIn("value.repeat(repetitions, 1)", source)
        self.assertIn("torch.Generator(device=device).manual_seed(seed)", source)
        for finish_reason in ("json_stop", "eos", "max_new_tokens", "unknown"):
            self.assertIn(f'finish_reason = "{finish_reason}"', source)

    def test_checkpoint_round_trip_is_grouped_and_deduplicated(self) -> None:
        first = {
            "model": "base",
            "run": 0,
            "source_id": "source",
            "archetype": "CAUSE_OF_SOURCE",
            "raw": "first",
        }
        replacement = {**first, "raw": "replacement"}
        second = {**first, "run": 1, "raw": "second"}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.jsonl"
            append_jsonl_group(path, [first, second])
            append_jsonl_group(path, [replacement])
            rows, ignored = load_jsonl_groups(path)

        self.assertEqual(ignored, 0)
        self.assertEqual(len(pathlib_free_json(rows)), 3)
        deduped = dedupe_rows(rows, attempt_key)
        self.assertEqual(deduped[attempt_key(first)]["raw"], "replacement")
        self.assertEqual(deduped[attempt_key(second)]["raw"], "second")

    def test_truncated_final_group_is_ignored(self) -> None:
        row = {
            "model": "base",
            "run": 0,
            "source_id": "source",
            "archetype": "CAUSE_OF_SOURCE",
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.jsonl"
            append_jsonl_group(path, [row])
            with path.open("a", encoding="utf-8") as handle:
                handle.write('{"rows": [')
            rows, ignored = load_jsonl_groups(path)

        self.assertEqual(rows, [row])
        self.assertEqual(ignored, 1)

    def test_model_specific_run_counts_and_score_keys(self) -> None:
        self.assertEqual(runs_for_model({"kind": "hf_base"}, 3, 1), 3)
        self.assertEqual(runs_for_model({"kind": "api_teacher"}, 3, 1), 1)
        row = {
            "model": "base",
            "run": 2,
            "source_id": "source",
            "archetype": "EFFECT_OF_SOURCE",
            "item_index": 0,
            "item_sha256": "abc123",
        }
        self.assertEqual(score_key(row), (*attempt_key(row), 0, "abc123"))

    def test_stable_hash_ignores_mapping_order(self) -> None:
        self.assertEqual(
            stable_hash({"a": 1, "b": 2}),
            stable_hash({"b": 2, "a": 1}),
        )

    def test_attempt_seeds_are_matched_and_independently_run_indexed(self) -> None:
        first = attempt_seed(7, 0, "source", "CAUSE_OF_SOURCE")
        repeated = attempt_seed(7, 0, "source", "CAUSE_OF_SOURCE")
        second_run = attempt_seed(7, 1, "source", "CAUSE_OF_SOURCE")
        self.assertEqual(first, repeated)
        self.assertNotEqual(first, second_run)

    def test_attempt_contract_fails_closed_on_multiple_items(self) -> None:
        attempt = {
            "model": "base",
            "run": 0,
            "source_id": "source",
            "archetype": "CAUSE_OF_SOURCE",
            "n_items": 2,
            "finish_reason": "json_stop",
            "format": {
                "strict_top_level_array": True,
                "exact_contract_valid": False,
            },
        }
        passing_row = {
            **attempt,
            "item_index": 0,
            "prog": {"schema_valid": True},
            "judge": {"_status": "ok"},
            "near_miss": True,
            "expert_grade": True,
            "key_valid": True,
            "label_clean": True,
        }
        outcome = attempt_contract_outcome(attempt, [passing_row, passing_row])
        self.assertFalse(outcome["exact_contract"])
        self.assertFalse(outcome["product_contract_valid"])
        self.assertFalse(outcome["near_miss"])

    def test_legacy_attempt_diagnostics_still_reject_thinking_tags(self) -> None:
        attempt = {
            "model": "base",
            "run": 0,
            "source_id": "source",
            "archetype": "CAUSE_OF_SOURCE",
            "n_items": 1,
            "format": {
                "strict_array_contract": True,
                "contains_think_tag": True,
            },
        }
        self.assertFalse(attempt_contract_outcome(attempt)["exact_contract"])

    def test_attempt_aggregation_uses_attempt_denominator_and_tracks_judge_failure(self) -> None:
        good_attempt = {
            "model": "base",
            "run": 0,
            "source_id": "good",
            "archetype": "CAUSE_OF_SOURCE",
            "n_items": 1,
            "finish_reason": "json_stop",
            "format": {
                "strict_top_level_array": True,
                "exact_contract_valid": True,
                "bucket": "strict_array",
            },
        }
        malformed_attempt = {
            **good_attempt,
            "source_id": "bad",
            "n_items": 0,
            "format": {
                "strict_top_level_array": False,
                "exact_contract_valid": False,
                "bucket": "invalid_json",
            },
        }
        unavailable_attempt = {**good_attempt, "source_id": "unavailable"}
        good_row = {
            **good_attempt,
            "prog": {"schema_valid": True},
            "judge": {"_status": "ok"},
            "expert_grade": True,
            "near_miss": True,
            "key_valid": True,
            "label_clean": True,
        }
        unavailable_row = {
            **unavailable_attempt,
            "prog": {"schema_valid": True},
            "judge": {"_status": "unparseable"},
            "expert_grade": None,
            "near_miss": None,
            "key_valid": None,
            "label_clean": None,
        }
        result = aggregate_attempt_metrics(
            [good_attempt, malformed_attempt, unavailable_attempt],
            [good_row, unavailable_row],
        )
        self.assertEqual(result["attempted_prompts"], 3)
        self.assertEqual(result["successfully_judged_attempts"], 1)
        self.assertEqual(result["judge_unavailable_attempts"], 1)
        self.assertEqual(result["attempted_prompt_near_miss_rate"], 1 / 3)
        self.assertEqual(result["near_miss_per_successfully_judged_attempt"], 1.0)
        self.assertEqual(
            result["attempted_prompt_distillable_item_valid_rate"],
            result["attempted_prompt_label_clean_rate"],
        )

    def test_source_clustered_ci_averages_within_source(self) -> None:
        base = {
            (0, "s1", "CAUSE_OF_SOURCE"): False,
            (1, "s1", "CAUSE_OF_SOURCE"): True,
            (0, "s2", "CAUSE_OF_SOURCE"): False,
        }
        tuned = {key: True for key in base}
        result = source_clustered_paired_ci(base, tuned, draws=200, seed=3)
        self.assertEqual(result["paired_prompts"], 3)
        self.assertEqual(result["sources"], 2)
        self.assertEqual(result["mean_delta"], 0.75)


def pathlib_free_json(rows: list[dict]) -> list[dict]:
    """Assert checkpoint rows remain plain JSON data."""
    return json.loads(json.dumps(rows))


if __name__ == "__main__":
    unittest.main()
