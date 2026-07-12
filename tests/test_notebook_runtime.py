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
    matched_candidate_exclusions,
    runs_for_model,
    score_key,
    source_clustered_paired_ci,
    stable_hash,
)
from source_utils import source_genre  # noqa: E402


class NotebookRuntimeTests(unittest.TestCase):
    @staticmethod
    def _gpu_notebook_code() -> str:
        notebook = json.loads(
            (ROOT / "notebooks/eval_hf_gpu.ipynb").read_text(encoding="utf-8")
        )
        return "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook["cells"]
            if cell.get("cell_type") == "code"
        )

    @staticmethod
    def _selected_notebook_nodes(code: str, names: set[str]) -> object:
        tree = ast.parse(code)
        selected = []
        for node in tree.body:
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in names
            ):
                selected.append(node)
            elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id in names
                for target in node.targets
            ):
                selected.append(node)
        return compile(
            ast.Module(body=selected, type_ignores=[]),
            "selected_notebook.py",
            "exec",
        )

    def test_gpu_notebook_uses_batched_resumable_execution(self) -> None:
        code = self._gpu_notebook_code()
        compile(code, "eval_hf_gpu.ipynb", "exec")
        self.assertIn("RUNS = 2", code)
        self.assertIn("TEACHER_RUNS = 1", code)
        self.assertNotIn("num_return_sequences", code)
        self.assertIn("run_generation_preflight", code)
        self.assertIn("PREFLIGHT_PASSED", code)
        self.assertNotIn("PREFLIGHT_SOURCE_LIMIT", code)
        self.assertIn("if execution_failures:", code)
        self.assertNotIn("if outcome_failures:", code)
        self.assertIn("if protocol_failures:", code)
        self.assertIn("'outcome_reasons':sorted(set(outcome_reasons))", code)
        self.assertNotIn("if failures:\n", code)
        self.assertIn("ThreadPoolExecutor(max_workers=API_MAX_WORKERS)", code)
        self.assertIn("append_jsonl_group(generation_path, new_attempts)", code)
        self.assertIn("load_jsonl_groups(scoring_path)", code)
        self.assertIn("aggregate_attempt_metrics", code)
        self.assertIn("source_clustered_paired_ci", code)
        self.assertNotIn("statistics.mean", code)
        self.assertIn("import huggingface_hub._snapshot_download", code)
        self.assertIn("'--force-reinstall'", code)
        self.assertIn("do_shutdown(restart=True)", code)
        self.assertNotIn("INSTALL_DEPS", code)
        self.assertIn("from hf_local import HFLocalEngine", code)
        self.assertNotIn("KEEP_NO_THINK_PREFILL", code)
        self.assertNotIn("FORCE_JSON_ARRAY_PREFIX", code)
        self.assertNotIn("USE_NO_THINK_SOFT_SWITCH", code)
        self.assertNotIn("RUN_NO_THINK_ABLATION", code)
        self.assertIn("keep_no_think_prefill=True", code)
        self.assertIn("force_json_array_prefix=False", code)
        self.assertIn("use_no_think_soft_switch=False", code)
        self.assertIn("stopping_enabled=True", code)
        self.assertIn("MAX_CONTRACT_ATTEMPTS = 8", code)
        self.assertIn("ensure_contract_valid_attempt", code)
        self.assertIn("first_pass_contract_valid", code)
        self.assertIn("generation_trials", code)
        self.assertIn("v5-denominator-correction-v7", code)
        self.assertIn("exclude_matched_candidate_prompt_and_continue", code)
        self.assertNotIn("raise RuntimeError(f\"Contract-valid generation exhausted", code)
        self.assertIn("if attempt['judging_excluded']: continue", code)
        self.assertIn("judging_excluded_attempts_by_model", code)
        self.assertIn(
            "os.environ['APUSH_GITHUB_REF'] = "
            "'REPLACE_WITH_FULL_40_CHARACTER_COMMIT_SHA'",
            code,
        )
        self.assertIn("re.fullmatch(r'[0-9a-f]{40}', GITHUB_REF)", code)
        self.assertIn("training_run_metadata.json", code)
        self.assertIn(
            "APUSH_ADAPTER_ID = 'rohanpalviela/qwen3-4b-apush-v5-semantic-preservation-lora'",
            code,
        )
        self.assertIn(
            "EXPECTED_ADAPTER_TRAINING_DATA_SHA256 = "
            "'06cfe7196256efaa94aca36550355b67deb54b42c418f9037e24cce7f0a21e44'",
            code,
        )
        self.assertIn("TRAINING_RUN_METADATA.get('dataset_version') != 'v5'", code)
        self.assertIn("independent_current_rubric_expert_curated_only_v1", code)
        self.assertIn("semantic_preservation_with_contract_learning", code)
        self.assertIn("Near/all (LB)", code)
        self.assertIn("Near/eligible", code)
        self.assertIn("aggregate_attempt_metrics(calls, model_scored)", code)
        self.assertIn("eligible_generation = aggregate_attempt_metrics", code)
        self.assertIn("V5 acceptance gate:", code)

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
        years = [
            int(re.search(r"(\d{4})$", source_id).group(1))
            for source_id in cohort
        ]
        for start, end in (
            (1776, 1800),
            (1801, 1848),
            (1849, 1877),
            (1878, 1945),
            (1946, 1980),
        ):
            self.assertTrue(any(start <= year <= end for year in years))

    def test_contract_validation_feedback_is_mechanical_only(self) -> None:
        code = self._gpu_notebook_code()
        namespace = {
            "json": json,
            "generation_format_diagnostics": lambda raw: {
                "exact_contract_valid": True,
                "no_think_tags": True,
            },
            "extract_items": lambda raw: [{"period": 2}],
            "canonicalize_item_archetype": lambda item, requested_archetype: item,
            "run_checks": lambda item, source, requested_archetype: {
                "schema_valid": False,
                "period_matches_source": False,
                **{
                    key: True
                    for key in (
                        "required_fields_present",
                        "field_types_exact",
                        "four_string_options",
                        "answer_key_valid",
                        "rationale_mapping_complete",
                        "rationale_correct_present",
                        "rationale_marks_answer",
                        "archetype_matches_request",
                        "theme_valid",
                        "nonempty_string_fields",
                        "trap_types_are_strings",
                        "trap_rationales_align",
                    )
                },
            },
        }
        exec(
            self._selected_notebook_nodes(
                code,
                {
                    "SCHEMA_VALIDATION_KEYS",
                    "contract_constrained_user",
                    "inspect_contract_trace",
                },
            ),
            namespace,
        )
        trace = {"raw": '[{"period": 2}]', "finish_reason": "json_stop"}
        validation = namespace["inspect_contract_trace"](
            trace,
            {"period": 3},
            "CAUSE_OF_SOURCE",
        )
        self.assertFalse(validation["contract_valid"])
        self.assertEqual(validation["failed_schema_checks"], ["period_matches_source"])
        retry = namespace["contract_constrained_user"](
            "original prompt",
            {"period": 3},
            "CAUSE_OF_SOURCE",
            validation,
        )
        self.assertIn("period integer 3", retry)
        self.assertIn("CAUSE_OF_SOURCE", retry)
        self.assertNotIn("correct answer", retry.lower())

    def test_contract_retry_selects_first_valid_and_preserves_trials(self) -> None:
        code = self._gpu_notebook_code()
        generated = iter([{"raw": "valid"}])
        seen_namespaces = []
        seen_token_limits = []

        def make_attempt(model, run_idx, source, arch, trace, batch_repetitions):
            valid = trace["raw"] == "valid"
            return {
                "model": model["name"],
                "run": run_idx,
                "source_id": source["id"],
                "archetype": arch,
                "seed": trace.get("seed"),
                "finish_reason": "json_stop",
                "generated_token_count": 1,
                "prompt_token_count": 1,
                "rendered_prompt_sha256": "hash",
                "n_items": 1 if valid else 0,
                "contract_valid": valid,
                "contract_reasons": [] if valid else ["token_ceiling"],
                "failed_schema_checks": [],
                "format": {},
                "schema": {"schema_valid": valid},
                "raw_preview": trace["raw"],
                "raw": trace["raw"],
            }

        def attempt_seed(base_seed, run_idx, source_id, arch, namespace):
            seen_namespaces.append(namespace)
            return 123

        def generate_model(model, system, user, seed, max_new_tokens):
            seen_token_limits.append(max_new_tokens)
            return next(generated)

        namespace = {
            "MAX_CONTRACT_ATTEMPTS": 3,
            "MAX_NEW_TOKENS": 768,
            "EVAL_SEED": 1,
            "make_attempt": make_attempt,
            "attempt_seed": attempt_seed,
            "generate_model": generate_model,
            "contract_constrained_user": lambda user, source, arch, validation: "retry",
        }
        exec(
            self._selected_notebook_nodes(
                code,
                {"contract_trial_snapshot", "ensure_contract_valid_attempt"},
            ),
            namespace,
        )
        result = namespace["ensure_contract_valid_attempt"](
            {"name": "base"},
            0,
            {"id": "source"},
            "CAUSE_OF_SOURCE",
            "system",
            "user",
            {"raw": "invalid"},
            2,
        )
        self.assertTrue(result["contract_valid"])
        self.assertFalse(result["first_pass_contract_valid"])
        self.assertEqual(result["generation_attempt_count"], 2)
        self.assertEqual(len(result["generation_trials"]), 2)
        self.assertEqual(seen_namespaces, ["contract-retry-1"])
        self.assertEqual(seen_token_limits, [1536])

    def test_contract_exhaustion_excludes_the_matched_candidate_prompt(self) -> None:
        attempts = [
            {
                "model": "base",
                "run": 0,
                "source_id": "s1",
                "archetype": "CAUSE_OF_SOURCE",
                "contract_valid": False,
            },
            {
                "model": "tuned",
                "run": 0,
                "source_id": "s1",
                "archetype": "CAUSE_OF_SOURCE",
                "contract_valid": True,
            },
            {
                "model": "base",
                "run": 0,
                "source_id": "s2",
                "archetype": "CAUSE_OF_SOURCE",
                "contract_valid": True,
            },
            {
                "model": "tuned",
                "run": 0,
                "source_id": "s2",
                "archetype": "CAUSE_OF_SOURCE",
                "contract_valid": True,
            },
        ]
        exclusions = matched_candidate_exclusions(attempts, ["base", "tuned"])
        self.assertEqual(
            exclusions,
            {
                (0, "s1", "CAUSE_OF_SOURCE"): {
                    "reason": "matched_candidate_contract_exhaustion",
                    "invalid_models": ["base"],
                }
            },
        )

    def test_unjudged_valid_attempt_retains_contract_metrics(self) -> None:
        attempt = {
            "model": "base",
            "run": 0,
            "source_id": "s1",
            "archetype": "CAUSE_OF_SOURCE",
            "n_items": 1,
            "finish_reason": "json_stop",
            "schema": {"schema_valid": True},
            "format": {
                "strict_top_level_array": True,
                "exact_contract_valid": True,
            },
            "judging_excluded": True,
        }
        outcome = attempt_contract_outcome(attempt)
        self.assertTrue(outcome["exact_contract"])
        self.assertTrue(outcome["schema_valid"])
        self.assertTrue(outcome["product_contract_valid"])
        self.assertFalse(outcome["judge_available"])

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
