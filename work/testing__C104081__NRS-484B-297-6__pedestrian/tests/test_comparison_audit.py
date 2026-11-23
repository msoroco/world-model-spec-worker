import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import audit


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.plan = json.loads((ROOT / "case-plan.json").read_text())
        self.sources = {}
        for case in self.plan["cases"]:
            case_id = case["case_id"]
            params = case["construction_parameters"]
            packet = {
                "source_kind": "original_saved_acquisition", "case_id": case_id,
                "cell_id": "C104081", "actor": "pedestrian", "map_id": "surveyed-map",
                "pedestrian_blueprint": "pedestrian-blueprint", "traffic_plan_sha256": "t" * 64,
                "camera_profile_sha256": "c" * 64, "duration_frames": 900,
                "intervening_barrier_present": params["area_blocked"],
                "designated_lane_used": params["area_blocked"],
                "pedestrian_direction": params["direction"],
                "sidewalk_obstruction_end_m": params["sidewalk_end_m"],
                "sidewalk_obstruction_kind": params["obstruction_kind"],
            }
            self._write(case_id, packet)

    def _write(self, case_id, packet):
        path = Path(self.temp.name) / (case_id + ".json")
        raw = (json.dumps(packet, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        self.sources[case_id] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}

    def _mutate(self, case_id, key, value):
        packet = json.loads(Path(self.sources[case_id]["path"]).read_text())
        packet[key] = value
        self._write(case_id, packet)

    def test_all_four_comparisons_with_source_bindings(self):
        result = audit(self.plan, self.sources)
        self.assertEqual(len(result["findings"]), 4)
        self.assertEqual(result["physical_acceptance"], "not_assessed")

    def test_missing_case_rejected(self):
        self.sources.pop(self.plan["cases"][0]["case_id"])
        with self.assertRaisesRegex(ValueError, "cover"):
            audit(self.plan, self.sources)

    def test_wrong_source_digest_rejected(self):
        first = self.plan["cases"][0]["case_id"]
        self.sources[first]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "digest"):
            audit(self.plan, self.sources)

    def test_fixture_label_rejected(self):
        first = self.plan["cases"][0]["case_id"]
        self._mutate(first, "source_kind", "synthetic_fixture")
        with self.assertRaisesRegex(ValueError, "original"):
            audit(self.plan, self.sources)

    def test_changed_fixed_traffic_plan_rejected(self):
        second = self.plan["cases"][1]["case_id"]
        self._mutate(second, "traffic_plan_sha256", "x" * 64)
        with self.assertRaisesRegex(ValueError, "fixed condition"):
            audit(self.plan, self.sources)

    def test_missing_measured_lane_use_rejected(self):
        second = self.plan["cases"][1]["case_id"]
        self._mutate(second, "designated_lane_used", None)
        with self.assertRaisesRegex(ValueError, "missing measured"):
            audit(self.plan, self.sources)

    def test_wrong_comparison_difference_rejected(self):
        second = self.plan["cases"][1]["case_id"]
        self._mutate(second, "pedestrian_direction", -1)
        with self.assertRaisesRegex(ValueError, "wrong variables"):
            audit(self.plan, self.sources)


if __name__ == "__main__":
    unittest.main()
