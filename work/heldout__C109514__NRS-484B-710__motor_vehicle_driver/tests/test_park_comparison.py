"""Independent source-bound below/at/above audit for stopped parking."""
from hashlib import sha256
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(ROOT / ".runtime-work/adapter/c109514-comparison-tests")
sys.path.insert(0, str(FOLDER))
sys.path.insert(1, str(ROOT / "runtime/scenario_pipeline"))

import fire_branch
import fire_comparison_audit
from worker_exchange.fixture_recipe import materialize


class ParkingComparisonTests(unittest.TestCase):
    def test_exact_three_case_boundary_and_changed_original_rejection(self):
        work = ROOT / ".runtime-work"
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="fire-comparison-", dir=work) as temp:
            base = Path(temp)
            rows = []
            expected = {}
            for target, bin_name in ((499, "below"), (500, "at"), (501, "above")):
                case_id = FOLDER.name + "__stopped_park_" + str(target) + "ft"
                recipe = FOLDER / "cases" / f"stopped_park_{target}ft" / "diagnostic-recipe.json"
                fixture = base / str(target)
                materialize(ROOT, recipe, fixture)
                context = json.loads((fixture / "fire_context.json").read_text())
                count = len((fixture / "video_frames.jsonl").read_text().splitlines())
                measurement = fire_branch.measure_branch(
                    fixture / "participant_footprints.jsonl",
                    fixture / "participant_state.jsonl",
                    count, "stopped_park", context)
                path = fixture / "fire-measurement.json"
                path.write_text(json.dumps(measurement, indent=2) + "\n")
                rows.append({"case_id": case_id, "measurement_path": str(path),
                             "measurement_sha256": sha256(path.read_bytes()).hexdigest(),
                             "participant_path": str(fixture / "participant_footprints.jsonl"),
                             "state_path": str(fixture / "participant_state.jsonl")})
                expected[case_id] = bin_name
            spec = {"comparison_id": "stopped_park_500_boundary",
                    "cases": rows,
                    "fixed_conditions": ["branch", "apparatus_answered_alarm",
                                         "authorized_emergency", "official_business"],
                    "deliberate_difference": "boundary_bin",
                    "expected_values": expected}
            self.assertTrue(fire_comparison_audit.audit(spec)["passed"])
            path = Path(rows[0]["participant_path"])
            path.write_text(path.read_text().replace('"ego_id":"ego"', '"ego_id":"changed"', 1))
            with self.assertRaisesRegex(ValueError, "participant source hash mismatch"):
                fire_comparison_audit.audit(spec)


if __name__ == "__main__":
    unittest.main()
