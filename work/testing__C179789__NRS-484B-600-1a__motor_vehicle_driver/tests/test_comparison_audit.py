import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from comparison_audit import DIRECTION, OBSERVED, audit
from saved_conditions import seal
from test_saved_conditions import rows


VARIABLES = {
    "ego_speed_request_mps": 10.0,
    "leader_initial_gap_m": 30.0,
    "surface_wetness_request": .2,
    "highway_width_m": 8.0,
    "native_precipitation_request": 20.0,
    "native_fog_request": 10.0,
}


def setup(attempt, case_id, variables, **changed):
    document = {"case_id": case_id, "variables": variables,
                "vehicle_blueprint": "vehicle.mock", "travel_direction": "forward",
                "paved_road": True, "camera_profile": "four-view", "duration_frames": 4,
                **changed}
    data = (json.dumps(document, sort_keys=True) + "\n").encode()
    (attempt / "authored-setup.json").write_bytes(data)
    (attempt / "authored-setup-seal.json").write_text(json.dumps({
        "format": "c179789-authored-setup-v1", "case_id": case_id,
        "sha256": hashlib.sha256(data).hexdigest()}))


class ComparisonAuditTests(unittest.TestCase):
    def run_pair(self, comparison_id, *, extra_variable=None, no_observation=False,
                 diagnostic=False, fixed_change=None, tamper=False,
                 reverse_observation=False, reverse_authored=False):
        plan_path = HERE / "case-plan.json"
        plan = json.loads(plan_path.read_text())
        item = next(item for item in plan["comparisons"] if item["comparison_id"] == comparison_id)
        variable = item["deliberate_differences"][0]
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory) / "first", Path(directory) / "second"
            first.mkdir()
            second.mkdir()
            base = copy.deepcopy(VARIABLES)
            changed = copy.deepcopy(base)
            changed[variable] += -1 if reverse_authored else DIRECTION[comparison_id]
            if extra_variable:
                changed[extra_variable] += 1
            setup(first, item["case_ids"][0], base)
            setup(second, item["case_ids"][1], changed,
                  **({"travel_direction": fixed_change} if fixed_change else {}))
            source = rows()
            altered = copy.deepcopy(source)
            if not no_observation:
                for row in altered:
                    row[OBSERVED[comparison_id]] += (-DIRECTION[comparison_id] if reverse_observation
                                                     else DIRECTION[comparison_id]) * .1
                    if comparison_id == "width":
                        row["roadway_driving_width_m"] += (-DIRECTION[comparison_id]
                                                             if reverse_observation else DIRECTION[comparison_id]) * .1
            seal(first, item["case_ids"][0], source, diagnostic_fixture=diagnostic)
            seal(second, item["case_ids"][1], altered, diagnostic_fixture=diagnostic)
            if tamper:
                with (second / "authored-setup.json").open("ab") as stream:
                    stream.write(b" ")
            return audit(plan_path, comparison_id, first, second)

    def test_each_exact_comparison_has_isolated_source_bound_pair(self):
        for comparison_id in OBSERVED:
            with self.subTest(comparison_id=comparison_id):
                result = self.run_pair(comparison_id)
                self.assertTrue(result["fixed_setup_passed"])
                self.assertTrue(result["observed_difference_passed"])
                self.assertEqual(result["legal_judgment"], "unresolved")

    def test_unplanned_authored_change_rejected(self):
        with self.assertRaisesRegex(ValueError, "not isolated"):
            self.run_pair("speed", extra_variable="leader_initial_gap_m")

    def test_fixed_condition_change_rejected(self):
        with self.assertRaisesRegex(ValueError, "fixed authored setup"):
            self.run_pair("traffic", fixed_change="reverse")

    def test_request_without_measured_difference_rejected(self):
        with self.assertRaisesRegex(ValueError, "absent from original measured"):
            self.run_pair("surface", no_observation=True)

    def test_diagnostic_evidence_rejected(self):
        with self.assertRaisesRegex(ValueError, "diagnostic condition samples"):
            self.run_pair("width", diagnostic=True)

    def test_tampered_setup_rejected(self):
        with self.assertRaisesRegex(ValueError, "setup seal"):
            self.run_pair("weather", tamper=True)

    def test_wrong_authored_direction_rejected(self):
        with self.assertRaisesRegex(ValueError, "authored comparison direction"):
            self.run_pair("speed", reverse_authored=True)

    def test_wrong_measured_direction_rejected(self):
        with self.assertRaisesRegex(ValueError, "measured comparison direction"):
            self.run_pair("traffic", reverse_observation=True)


if __name__ == "__main__":
    unittest.main()
