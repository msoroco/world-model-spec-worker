"""End-to-end saved-only proof for the first exact fire-apparatus case."""
import json
import sys
import tempfile
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
sys.path.insert(1, str(ROOT / "runtime/python"))

from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources, run as process_saved


class SavedProcessingTests(unittest.TestCase):
    def test_raw_fire_sources_survive_complete_saved_processing(self):
        case = FOLDER.name + "__traveling_follow_500ft"
        work = ROOT / ".runtime-work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="fire-saved-test-", dir=work) as temp:
            base = Path(temp)
            fixture = base / "fixture"
            make_fixture(ROOT, FOLDER / "diagnostic-recipe.json", fixture)
            decoder = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"
            self.assertTrue(decoder.is_file(), "Build the pinned Lean decoder first")
            for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
                with self.subTest(candidate=candidate):
                    attempt, output = base / (candidate + "-attempt"), base / (candidate + "-processed")
                    make_attempt(FOLDER / "execution-manifest.json", case, attempt,
                                 candidate=candidate)
                    copy_sources(fixture, attempt)
                    self.assertFalse((attempt / "fire_gap_ft.jsonl").exists())
                    receipt = process_saved(
                        FOLDER / "execution-manifest.json", case, attempt, output,
                        ROOT / "runtime/library", decoder)
                    self.assertTrue(receipt["passed"])
                    self.assertEqual(receipt["candidate_id"], candidate)
                    self.assertFalse(receipt["missing_evidence"])
                    self.assertTrue(receipt["originals_preserved"])
                    self.assertEqual(receipt["timestamp_joins"]["frames"], 9)
                    self.assertTrue(receipt["final_video_checks"]["passed"])
                    self.assertFalse((attempt / "fire_gap_ft.jsonl").exists())
                    stage = Path(receipt["analysis_directory"])
                    values = [json.loads(line)["value"] for line in
                              (stage / "fire_gap_ft.jsonl").read_text().splitlines()]
                    self.assertEqual(len(values), 9)
                    self.assertTrue(all(abs(v - 500) < 1e-6 for v in values))


if __name__ == "__main__":
    unittest.main()
