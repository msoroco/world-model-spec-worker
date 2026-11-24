import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from comparison_audit import ASSIGNMENT, SUFFIXES, audit


class SavedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.packet = {"assignment_id": ASSIGNMENT, "cases": []}
        for suffix in SUFFIXES:
            case_id = ASSIGNMENT + "__" + suffix
            cause = {"traffic_14ft": "traffic_conflict_necessity",
                     "police_14ft": "police_direction_necessity",
                     "device_14ft": "device_direction_necessity"}.get(suffix, "ordinary_destination")
            observation = {"case_id": case_id, "frames": [0, 899], "cause_observed": cause}
            observation_name = "shared-observation.json" if cause == "ordinary_destination" else suffix + "-observation.json"
            observation_source = self._write(observation_name,
                {"frames": [0, 899], "cause_observed": cause})
            context = {"case_id": case_id, "map_sha256": "a" * 64,
                       "intersection_boundary_sha256": "b" * 64,
                       "vehicle_blueprint": "vehicle.test", "vehicle_length_m": 4.5,
                       "vehicle_width_m": 1.8, "approach": "east", "route_sha256": "c" * 64,
                       "camera_plan_sha256": "d" * 64, "duration_s": 45, "fps": 20,
                       "activity": "stand" if suffix == "stand_14ft" else "stop",
                       "halt_cause": cause,
                       "requested_front_body_gap_ft": 15 if suffix == "stop_15ft" else 16 if suffix == "stop_16ft" else 14,
                       "diagnostic_fixture": False, "observation_source": observation_source}
            measurement = {"case_id": case_id, "original_frame_count": 900,
                           "pose_sha256": suffix, "map_sha256": "a" * 64,
                           "halt_frame_count": 40, "halt_intervals": [{"first_frame": 800, "last_frame": 839}],
                           "minimum_halt_body_gap_m": context["requested_front_body_gap_ft"] * 0.3048}
            self.packet["cases"].append({"case_id": case_id,
                "measurement_source": self._write(suffix + "-measurement.json", measurement),
                "context_source": self._write(suffix + "-context.json", context)})
        self.packet_path = self.root / "packet.json"
        self._save()

    def _write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value) + "\n")
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def _save(self):
        self.packet_path.write_text(json.dumps(self.packet) + "\n")

    def _change_context(self, suffix, key, value):
        item = next(x for x in self.packet["cases"] if x["case_id"].endswith("__" + suffix))
        path = self.root / item["context_source"]["path"]
        obj = json.loads(path.read_text())
        obj[key] = value
        item["context_source"] = self._write(path.name, obj)
        self._save()

    def test_all_three_comparisons(self):
        result = audit(self.packet_path)
        self.assertEqual(result["case_count"], 7)
        self.assertFalse(result["legal_necessity_resolved"])

    def test_missing_case_rejected(self):
        self.packet["cases"].pop()
        self._save()
        with self.assertRaisesRegex(ValueError, "Seven exact"):
            audit(self.packet_path)

    def test_source_tamper_rejected(self):
        (self.root / "stop_14ft-measurement.json").write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            audit(self.packet_path)

    def test_fixed_condition_drift_rejected(self):
        self._change_context("stop_16ft", "route_sha256", "e" * 64)
        with self.assertRaisesRegex(ValueError, "Fixed condition"):
            audit(self.packet_path)

    def test_wrong_exception_cause_rejected(self):
        self._change_context("police_14ft", "halt_cause", "ordinary_destination")
        with self.assertRaisesRegex(ValueError, "Observed cause|Exception cause"):
            audit(self.packet_path)

    def test_rehashed_observation_disagrees_with_claimed_cause(self):
        item = next(x for x in self.packet["cases"] if x["case_id"].endswith("__police_14ft"))
        context_path = self.root / item["context_source"]["path"]
        context = json.loads(context_path.read_text())
        observation_path = self.root / context["observation_source"]["path"]
        observation = json.loads(observation_path.read_text())
        observation["cause_observed"] = "ordinary_destination"
        context["observation_source"] = self._write(observation_path.name, observation)
        item["context_source"] = self._write(context_path.name, context)
        self._save()
        with self.assertRaisesRegex(ValueError, "Observed cause"):
            audit(self.packet_path)

    def test_diagnostic_source_rejected(self):
        self._change_context("stand_14ft", "diagnostic_fixture", True)
        with self.assertRaisesRegex(ValueError, "Diagnostic"):
            audit(self.packet_path)

    def test_source_path_escape_rejected(self):
        self.packet["cases"][0]["measurement_source"]["path"] = "../outside.json"
        self._save()
        with self.assertRaisesRegex(ValueError, "within saved package"):
            audit(self.packet_path)


if __name__ == "__main__":
    unittest.main()
