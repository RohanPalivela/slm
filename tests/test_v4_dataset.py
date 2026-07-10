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
from source_utils import source_genre  # noqa: E402


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


class V4DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = load_jsonl(ROOT / "data/generated/train_v4_clean.jsonl")
        cls.sources = {
            row["id"]: row for row in load_jsonl(ROOT / "data/seed_stimuli.jsonl")
        }
        cls.splits = json.loads((ROOT / "data/splits.json").read_text(encoding="utf-8"))["splits"]
        cls.policy = json.loads(
            (ROOT / "data/training_archetype_policy.json").read_text(encoding="utf-8")
        )

    def test_split_firewall_and_distribution(self) -> None:
        source_ids = {row["source_id"] for row in self.rows}
        heldout = set(self.splits["LITMUS"]["source_ids"]) | set(
            self.splits["EVAL_HELDOUT"]["source_ids"]
        )
        self.assertFalse(source_ids & heldout)
        self.assertGreaterEqual(len(source_ids), 60)
        archetypes = Counter(row["archetype"] for row in self.rows)
        self.assertGreaterEqual(min(archetypes.values()) / max(archetypes.values()), 0.9)

    def test_all_records_pass_programmatic_checks(self) -> None:
        for row in self.rows:
            result = checks.run_checks(row, self.sources[row["source_id"]])
            self.assertTrue(result["disqualifying_ok"], row["source_id"])
            self.assertTrue(result["craft_ok"], row["source_id"])
            self.assertTrue(result["homogeneous_length"], row["source_id"])

    def test_generic_speech_effects_are_absent(self) -> None:
        overrides = self.policy["source_overrides"]
        for row in self.rows:
            if row["archetype"] != "EFFECT_OF_SOURCE":
                continue
            source = self.sources[row["source_id"]]
            if source_genre(source) == "speech_or_argument":
                self.assertIn("EFFECT_OF_SOURCE", overrides.get(row["source_id"], []))

    def test_curated_anchor_count(self) -> None:
        self.assertEqual(
            sum(row.get("quality_tier") == "curated_causal_anchor" for row in self.rows),
            65,
        )

    def test_training_notebook_pins_current_sft_hash(self) -> None:
        sft_path = ROOT / "data/generated/train_sft_v4.jsonl"
        expected = hashlib.sha256(sft_path.read_bytes()).hexdigest()
        notebook = json.loads(
            (ROOT / "train/qlora_qwen3_4b.ipynb").read_text(encoding="utf-8")
        )
        code = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook["cells"]
            if cell.get("cell_type") == "code"
        )
        match = re.search(r'EXPECTED_PROVISIONAL_DATASET_SHA256 = "([0-9a-f]{64})"', code)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), expected)

    def test_prompt_fewshots_use_only_closed_archetypes(self) -> None:
        prompt = (ROOT / "prompts/litmus_generation_prompt.md").read_text(encoding="utf-8")
        self.assertNotIn("EVIDENCE_SUPPORTS_CLAIM", prompt)
        self.assertIn("EXAMPLE - archetype EFFECT_OF_SOURCE", prompt)

    def test_legacy_outside_knowledge_is_concise_and_traceable(self) -> None:
        legacy_rows = [
            row for row in self.rows if row.get("quality_tier") == "legacy_v3_strict_survivor"
        ]
        self.assertEqual(len(legacy_rows), 57)
        for row in legacy_rows:
            key_index = "ABCD".index(row["answer"])
            self.assertEqual(row["requires_outside_knowledge"], row["options"][key_index])
            self.assertTrue(row.get("legacy_requires_outside_knowledge"))
            self.assertEqual(
                row.get("field_provenance", {}).get("requires_outside_knowledge"),
                "normalized_from_keyed_development",
            )


if __name__ == "__main__":
    unittest.main()
