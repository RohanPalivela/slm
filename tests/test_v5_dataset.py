from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import checks  # noqa: E402
from prompt_loader import extract_items  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class V5DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = load_jsonl(ROOT / "data/generated/train_v5_clean.jsonl")
        cls.sft = load_jsonl(ROOT / "data/generated/train_sft_v5.jsonl")
        cls.sources = {
            row["id"]: row
            for row in load_jsonl(ROOT / "data/seed_stimuli.jsonl")
        }
        cls.splits = json.loads(
            (ROOT / "data/splits.json").read_text(encoding="utf-8")
        )["splits"]

    def test_v5_is_small_balanced_and_heldout_disjoint(self) -> None:
        self.assertEqual(len(self.rows), 64)
        self.assertEqual(len(self.sft), 64)
        self.assertEqual(Counter(row["archetype"] for row in self.rows), {
            "CAUSE_OF_SOURCE": 32,
            "EFFECT_OF_SOURCE": 32,
        })
        self.assertEqual(Counter(row["answer"] for row in self.rows), {
            "A": 16,
            "B": 16,
            "C": 16,
            "D": 16,
        })
        source_ids = {row["source_id"] for row in self.rows}
        heldout = set(self.splits["LITMUS"]["source_ids"]) | set(
            self.splits["EVAL_HELDOUT"]["source_ids"]
        )
        self.assertFalse(source_ids & heldout)

    def test_every_target_is_independently_reviewed_curated_expert_grade(self) -> None:
        pairs = set()
        for row in self.rows:
            self.assertEqual(row["dataset_version"], "v5")
            self.assertEqual(row["quality_tier"], "curated_causal_anchor")
            self.assertEqual(row["sft_repeats"], 1)
            self.assertTrue(row["review"]["current_rubric_complete"])
            judgment = row["judge"]
            for key in (
                "requires_outside_knowledge",
                "every_distractor_named_trap",
                "distractors_period_plausible",
                "skill_matches_command_phrase",
                "key_historically_correct",
                "key_uniquely_best",
                "single_best_answer",
            ):
                self.assertIs(judgment[key], True, (row["source_id"], key))
            for key in (
                "spec_adherence",
                "distractor_craft",
                "outside_knowledge_skill_fit",
            ):
                self.assertEqual(judgment[key], 2, (row["source_id"], key))
            pair = (row["source_id"], row["archetype"])
            self.assertNotIn(pair, pairs)
            pairs.add(pair)

    def test_every_target_passes_current_programmatic_contract(self) -> None:
        for row in self.sft:
            items = extract_items(row["messages"][-1]["content"])
            self.assertEqual(len(items), 1, row["source_id"])
            item = items[0]
            result = checks.run_checks(
                item,
                self.sources[row["source_id"]],
                row["archetype"],
            )
            self.assertTrue(result["schema_valid"], row["source_id"])
            self.assertTrue(result["trap_rationales_align"], row["source_id"])
            self.assertTrue(result["craft_ok"], row["source_id"])
            self.assertTrue(result["disqualifying_ok"], row["source_id"])

    def test_training_notebook_pins_v5_dataset_and_lower_intensity(self) -> None:
        expected_hash = hashlib.sha256(
            (ROOT / "data/generated/train_sft_v5.jsonl").read_bytes()
        ).hexdigest()
        notebook = json.loads(
            (ROOT / "train/qlora_qwen3_4b.ipynb").read_text(encoding="utf-8")
        )
        code = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook["cells"]
            if cell.get("cell_type") == "code"
        )
        match = re.search(r'EXPECTED_DATASET_SHA256 = "([0-9a-f]{64})"', code)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), expected_hash)
        self.assertIn('RUN_NAME = "qwen3-4b-apush-v5-semantic-preservation"', code)
        self.assertIn('"data/generated/train_sft_v5.jsonl"', code)
        self.assertIn("r=8", code)
        self.assertIn("lora_alpha=16", code)
        self.assertIn("gradient_accumulation_steps=2", code)
        self.assertIn("num_train_epochs=1", code)
        self.assertIn("learning_rate=4e-5", code)


if __name__ == "__main__":
    unittest.main()
