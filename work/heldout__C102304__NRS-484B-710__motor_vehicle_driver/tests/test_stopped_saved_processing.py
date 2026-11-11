"""Complete saved-only proof for the first stopped drive-to exact case."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(ROOT / ".runtime-work/adapter/fire-stopped-saved-tests")
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
sys.path.insert(1, str(ROOT / "runtime/python"))

from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources, run as process_saved


class StoppedSavedProcessingTests(unittest.TestCase):
    def test_center_stream_is_derived_from_raw_stopped_sources(self):
        work = ROOT / ".runtime-work"
        work.mkdir(exist_ok=True)
        case = FOLDER.name + "__stopped_drive_to_450ft"
        with tempfile.TemporaryDirectory(prefix="fire-stopped-saved-", dir=work) as temp:
            root = Path(temp)
            fixture = root / "fixture"
            make_fixture(ROOT, FOLDER / "cases/stopped_drive_to_450ft/diagnostic-recipe.json", fixture)
            decoder = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"
            self.assertTrue(decoder.is_file(), "Build the pinned Lean decoder first")
            for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
                with self.subTest(candidate=candidate):
                    attempt, output = (root / (candidate + suffix)
                                       for suffix in ("-attempt", "-processed"))
                    make_attempt(FOLDER / "execution-manifest.json", case, attempt,
                                 candidate=candidate)
                    copy_sources(fixture, attempt)
                    self.assertFalse((attempt / "fire_centre_distance_ft.jsonl").exists())
                    receipt = process_saved(FOLDER / "execution-manifest.json", case,
                                            attempt, output, ROOT / "runtime/library", decoder)
                    self.assertTrue(receipt["passed"])
                    self.assertEqual(receipt["candidate_id"], candidate)
                    self.assertFalse(receipt["missing_evidence"])
                    self.assertTrue(receipt["originals_preserved"])
                    self.assertTrue(receipt["final_video_checks"]["passed"])
                    self.assertEqual(receipt["timestamp_joins"]["frames"], 9)
                    self.assertFalse((attempt / "fire_centre_distance_ft.jsonl").exists())
                    stage = Path(receipt["analysis_directory"])
                    rows = [json.loads(line) for line in
                            (stage / "fire_centre_distance_ft.jsonl").read_text().splitlines()]
                    self.assertEqual(len(rows), 9)
                    self.assertAlmostEqual(min(row["value"] for row in rows), 450)
                    result = json.loads((stage / "result.json").read_text())
                    observed = result["measured_values"]["fire_boundary_observation"]
                    self.assertEqual(observed["boundary_measurement"], "centre_distance_ft")
                    self.assertGreater(observed["active_frame_count"], 0)
                    self.assertFalse(result["physical_acceptance_claimed"])


if __name__ == "__main__":
    unittest.main()
