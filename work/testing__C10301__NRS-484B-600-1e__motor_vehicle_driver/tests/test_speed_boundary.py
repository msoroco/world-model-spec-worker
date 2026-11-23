import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speed_boundary import MPH_PER_MPS, compare, measure
from speed_capture import write_original_speed


ROOT = Path(__file__).resolve().parents[1]
ASSIGNMENT = ROOT.name


def make_attempt(root, suffix, mph, run_id, *, fixture=True, requested_mph=None):
    folder = root / suffix
    folder.mkdir()
    case_id = ASSIGNMENT + "__" + suffix
    rows = [{"frame": 100 + i, "time_s": i / 20, "speed_mps": mph / MPH_PER_MPS,
             "speed_uncertainty_mps": 0.02} for i in range(900)]
    raw = "".join(json.dumps(row) + "\n" for row in rows).encode()
    (folder / "original-speed.jsonl").write_bytes(raw)
    descriptor = {"format": "c10301-original-speed-source-v1", "case_id": case_id,
                  "source": "original-speed.jsonl", "sha256": hashlib.sha256(raw).hexdigest(),
                  "sample_rate_hz": 20.0, "sample_count": 900,
                  "source_frame_origin": 100, "native_run_id": run_id,
                  "diagnostic_fixture": fixture}
    (folder / "speed-source.json").write_text(json.dumps(descriptor))
    setup = {"case_id": case_id, "law_id": "NRS-484B-600-1e", "cell_id": "C10301",
             "actor": "motor_vehicle_driver", "layout": "alley", "control": "access_aisle",
             "maneuver": "travel", "requested_speed_mph": mph if requested_mph is None else requested_mph}
    (folder / "authored-setup.json").write_text(json.dumps(setup))
    return folder


class SpeedBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def triple(self):
        return {suffix: make_attempt(self.root, suffix, mph, suffix,
                                     requested_mph=80 if suffix == "equal" else mph)
                for suffix, mph in [("below", 74.95), ("equal", 79.73), ("above", 80.70)]}

    def test_source_bound_samples_and_no_equality_inference(self):
        attempts = self.triple()
        below = measure(attempts["below"], ASSIGNMENT + "__below")
        middle = measure(attempts["equal"], ASSIGNMENT + "__equal")
        above = measure(attempts["above"], ASSIGNMENT + "__above")
        self.assertEqual(below["sampled_relation"], "all_samples_below")
        self.assertEqual(middle["sampled_relation"], "all_samples_below")
        self.assertEqual(above["sampled_relation"], "all_samples_above")
        self.assertEqual(middle["between_sample_peaks"], "unobserved")
        self.assertTrue(middle["diagnostic_fixture"])
        self.assertFalse(above["physical_acceptance_claimed"])

    def test_comparison_checks_fixed_setup_and_order(self):
        attempts = self.triple()
        keyed = {ASSIGNMENT + "__" + key: value for key, value in attempts.items()}
        result = compare(ROOT / "case-plan.json", keyed)
        self.assertTrue(result["fixed_setup_passed"])
        self.assertTrue(result["observed_order_passed"])
        self.assertTrue(result["diagnostic_fixture"])
        self.assertEqual(result["sampled_relations"][1], "all_samples_below")
        setup_path = attempts["above"] / "authored-setup.json"
        altered = json.loads(setup_path.read_text())
        altered["control"] = "stop_sign"
        setup_path.write_text(json.dumps(altered))
        with self.assertRaisesRegex(ValueError, "fixed authored setup"):
            compare(ROOT / "case-plan.json", keyed)

    def test_rejects_missing_stale_and_noncanonical_source(self):
        attempt = make_attempt(self.root, "below", 75, "a")
        (attempt / "original-speed.jsonl").unlink()
        with self.assertRaises(FileNotFoundError):
            measure(attempt, ASSIGNMENT + "__below")
        attempt = make_attempt(self.root, "above", 81, "b")
        with (attempt / "original-speed.jsonl").open("ab") as stream:
            stream.write(b"\n")
        with self.assertRaisesRegex(ValueError, "hash differs"):
            measure(attempt, ASSIGNMENT + "__above")
        attempt = make_attempt(self.root, "equal", 80, "c")
        descriptor_path = attempt / "speed-source.json"
        descriptor = json.loads(descriptor_path.read_text())
        descriptor["sample_count"] = 899
        descriptor_path.write_text(json.dumps(descriptor))
        with self.assertRaisesRegex(ValueError, "descriptor incomplete"):
            measure(attempt, ASSIGNMENT + "__equal")

    def test_rejects_missing_case_and_duplicate_run(self):
        attempts = self.triple()
        keyed = {ASSIGNMENT + "__" + key: value for key, value in attempts.items()}
        with self.assertRaisesRegex(ValueError, "three distinct"):
            compare(ROOT / "case-plan.json", {key: value for key, value in keyed.items()
                                                if not key.endswith("__above")})
        descriptor_path = attempts["above"] / "speed-source.json"
        descriptor = json.loads(descriptor_path.read_text())
        descriptor["native_run_id"] = "equal"
        descriptor_path.write_text(json.dumps(descriptor))
        with self.assertRaisesRegex(ValueError, "reuses an original Native run"):
            compare(ROOT / "case-plan.json", keyed)

    def test_capture_writer_seals_original_samples_once(self):
        folder = self.root / "written"
        rows = [{"frame": 500 + i, "time_s": i / 20,
                 "speed_mps": 80 / MPH_PER_MPS,
                 "speed_uncertainty_mps": 0.01} for i in range(900)]
        case_id = ASSIGNMENT + "__equal"
        descriptor = write_original_speed(folder, case_id, "run-1", rows,
                                          diagnostic_fixture=True)
        self.assertEqual(descriptor["sample_count"], 900)
        self.assertEqual(measure(folder, case_id)["sampled_relation"],
                         "boundary_unresolved")
        with self.assertRaisesRegex(ValueError, "already exists"):
            write_original_speed(folder, case_id, "run-2", rows)
        rows[4]["frame"] += 1
        with self.assertRaisesRegex(ValueError, "frame sequence differs"):
            write_original_speed(self.root / "bad", case_id, "run-3", rows)


if __name__ == "__main__":
    unittest.main()
