from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from notebook_runtime import (  # noqa: E402
    append_jsonl_group,
    attempt_key,
    dedupe_rows,
    load_jsonl_groups,
    runs_for_model,
    score_key,
    stable_hash,
)


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
        self.assertIn("TEACHER_RUNS = 1", code)
        self.assertIn("num_return_sequences': repetitions", code)
        self.assertIn("ThreadPoolExecutor(max_workers=API_MAX_WORKERS)", code)
        self.assertIn("append_jsonl_group(generation_path, new_attempts)", code)
        self.assertIn("load_jsonl_groups(scoring_path)", code)

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


def pathlib_free_json(rows: list[dict]) -> list[dict]:
    """Assert checkpoint rows remain plain JSON data."""
    return json.loads(json.dumps(rows))


if __name__ == "__main__":
    unittest.main()
