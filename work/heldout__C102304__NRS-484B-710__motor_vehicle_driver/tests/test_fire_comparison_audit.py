import importlib.util
from hashlib import sha256
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


branch = load("fire_branch")
audit_module = load("fire_comparison_audit")


def box(x0, x1):
    return [(x0, -1), (x1, -1), (x1, 1), (x0, 1)]


class FireComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def case(self, case_id, gap_ft, authorized=False):
        directory = self.root / case_id
        directory.mkdir()
        participants = directory / "participants.jsonl"
        states = directory / "states.jsonl"
        measurements = directory / "measurements.json"
        for frame in range(2):
            x = 4 + gap_ft / branch._distance.FEET_PER_METRE + frame
            participant = {"frame": frame, "time_s": frame / 20,
                           "ego_id": "ego", "apparatus_id": "apparatus",
                           "ego_corners": box(frame, frame + 4),
                           "apparatus_corners": box(x, x + 6)}
            state = {"frame": frame, "time_s": frame / 20,
                     "apparatus_moving": True, "ego_moving": True,
                     "ego_following": True, "ego_parked": False,
                     "warning_lamp": True, "siren": True}
            with participants.open("a") as stream:
                stream.write(json.dumps(participant) + "\n")
            with states.open("a") as stream:
                stream.write(json.dumps(state) + "\n")
        context = {"alarm_response_source": "authored dispatch context",
                   "apparatus_answered_alarm": True,
                   "subject_authorized_emergency": authorized,
                   "subject_official_business": authorized}
        value = branch.measure_branch(participants, states, 2, "traveling_follow", context)
        measurements.write_text(json.dumps(value))
        return {"case_id": case_id, "measurement_path": str(measurements),
                "measurement_sha256": sha256(measurements.read_bytes()).hexdigest(),
                "participant_path": str(participants), "state_path": str(states)}

    def test_boundary_comparison_passes_with_retained_sources(self):
        cases = [self.case("below", 499), self.case("at", 500), self.case("above", 501)]
        spec = {"comparison_id": "traveling_boundary", "cases": cases,
                "fixed_conditions": ["branch", "authorized_emergency", "official_business",
                                     "apparatus_answered_alarm"],
                "deliberate_difference": "boundary_bin",
                "expected_values": {"below": "below", "at": "at", "above": "above"}}
        self.assertTrue(audit_module.audit(spec)["passed"])
        cases[1]["measurement_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "stale measurement hash"):
            audit_module.audit(spec)

    def test_rejects_missing_source_and_changed_fixed_condition(self):
        cases = [self.case("ordinary", 499), self.case("emergency", 501, True)]
        spec = {"comparison_id": "bad_fixed", "cases": cases,
                "fixed_conditions": ["branch", "authorized_emergency"],
                "deliberate_difference": "boundary_bin",
                "expected_values": {"ordinary": "below", "emergency": "above"}}
        with self.assertRaisesRegex(ValueError, "Fixed condition changed"):
            audit_module.audit(spec)
        spec["fixed_conditions"] = ["branch"]
        cases[0]["participant_path"] = str(self.root / "missing.jsonl")
        with self.assertRaises(FileNotFoundError):
            audit_module.audit(spec)

    def test_exception_comparison_requires_identical_distance_bin(self):
        cases = [self.case("ordinary", 499), self.case("emergency", 499, True)]
        spec = {"comparison_id": "exception", "cases": cases,
                "fixed_conditions": ["branch", "apparatus_answered_alarm", "boundary_bin"],
                "deliberate_difference": "authorized_emergency",
                "expected_values": {"ordinary": False, "emergency": True}}
        self.assertTrue(audit_module.audit(spec)["passed"])
        spec["expected_values"]["emergency"] = False
        with self.assertRaisesRegex(ValueError, "declared difference absent"):
            audit_module.audit(spec)

    def test_rejects_rehashed_measurement_that_disagrees_with_native_source(self):
        cases = [self.case("near", 499), self.case("far", 501)]
        spec = {"comparison_id": "tampered", "cases": cases,
                "fixed_conditions": ["branch", "authorized_emergency"],
                "deliberate_difference": "boundary_bin",
                "expected_values": {"near": "below", "far": "above"}}
        path = Path(cases[0]["measurement_path"])
        value = json.loads(path.read_text())
        value["observations"][0]["nearest_footprint_gap_ft"] = 498.0
        path.write_text(json.dumps(value))
        cases[0]["measurement_sha256"] = sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "measurement differs from retained sources"):
            audit_module.audit(spec)


if __name__ == "__main__":
    unittest.main()
