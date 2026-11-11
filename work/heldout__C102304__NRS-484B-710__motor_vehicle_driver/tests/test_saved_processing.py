"""End-to-end saved-only proof for the first exact fire-apparatus case."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(ROOT / ".runtime-work/adapter/fire-saved-tests")
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
sys.path.insert(1, str(ROOT / "runtime/python"))

from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources, run as process_saved


class SavedProcessingTests(unittest.TestCase):
    def test_authorized_emergency_context_survives_saved_processing(self):
        work = ROOT / ".runtime-work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="fire-exception-saved-", dir=work) as temp:
            base = Path(temp)
            case = FOLDER.name + "__authorized_emergency_at500"
            fixture = base / "fixture"
            recipe = FOLDER / "cases/authorized_emergency_at500/diagnostic-recipe.json"
            make_fixture(ROOT, recipe, fixture)
            decoder = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"
            for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
                with self.subTest(candidate=candidate):
                    attempt = base / (candidate + "-attempt")
                    output = base / (candidate + "-processed")
                    make_attempt(FOLDER / "execution-manifest.json", case, attempt,
                                 candidate=candidate)
                    copy_sources(fixture, attempt)
                    self.assertFalse((attempt / "fire_gap_ft.jsonl").exists())
                    receipt = process_saved(FOLDER / "execution-manifest.json", case,
                                            attempt, output, ROOT / "runtime/library", decoder)
                    self.assertTrue(receipt["passed"])
                    self.assertTrue(receipt["originals_preserved"])
                    self.assertTrue(receipt["final_video_checks"]["passed"])
                    self.assertFalse((attempt / "fire_gap_ft.jsonl").exists())
                    result = json.loads((Path(receipt["analysis_directory"]) / "result.json").read_text())
                    context = result["measured_values"]["fire_boundary_observation"]["exception_context"]
                    self.assertTrue(context["authorized_emergency"])
                    self.assertTrue(context["official_business"])
                    self.assertFalse(result["physical_acceptance_claimed"])

    def test_raw_fire_sources_survive_complete_saved_processing(self):
        work = ROOT / ".runtime-work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="fire-saved-test-", dir=work) as temp:
            base = Path(temp)
            decoder = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"
            self.assertTrue(decoder.is_file(), "Build the pinned Lean decoder first")
            for target in (499, 500, 501):
                case = FOLDER.name + "__traveling_follow_" + str(target) + "ft"
                case_folder = base / str(target)
                case_folder.mkdir()
                fixture = case_folder / "fixture"
                recipe = (FOLDER / "diagnostic-recipe.json" if target == 500
                          else FOLDER / "cases" / f"traveling_follow_{target}ft" / "diagnostic-recipe.json")
                make_fixture(ROOT, recipe, fixture)
                for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
                    with self.subTest(target=target, candidate=candidate):
                        attempt, output = (case_folder / (candidate + suffix)
                                           for suffix in ("-attempt", "-processed"))
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
                        self.assertTrue(all(abs(v - target) < 1e-6 for v in values))


if __name__ == "__main__":
    unittest.main()
