import hashlib
import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speed_measurement import measure


CASE = "testing__C10307__LVMC-11-40-130__cycle_or_scooter_operator__reference"


class SpeedMeasurementTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.docs = {
            "frame_map": {"frames": [{"frame": 0, "time_s": 0.0}, {"frame": 1, "time_s": 0.05}, {"frame": 2, "time_s": 0.1}]},
            "bicycle_motion": {"case_id": CASE, "samples": [{"frame": i, "time_s": i * 0.05, "velocity_mps": [3.0, 0, 0]} for i in range(3)]},
            "context": {"case_id": CASE, "jurisdiction": {"city_of_las_vegas": True, "source": "map review"}, "bicycle_classification": {"human_powered": True, "moped": False, "source": "actor review"}, "alley_route": {"source": "map geometry"}, "rack_geometry": {"source": "spawn geometry"}, "samples": [{"frame": i, "time_s": i * .05, "weather": "clear", "surface": "dry", "visibility": "clear", "pedestrians": "none", "curvature": "straight"} for i in range(3)]},
        }
        self.inventory = {"case_id": CASE, "source_kind": "original_native", "sources": {}}
        for key in self.docs:
            self.save(key)

    def save(self, key):
        path = self.root / (key + ".json")
        data = json.dumps(self.docs[key], sort_keys=True).encode()
        path.write_bytes(data)
        self.inventory["sources"][key] = {"path": path.name, "sha256": hashlib.sha256(data).hexdigest()}

    def test_speed_and_unresolved_judgment(self):
        result = measure(self.root, self.inventory, CASE)
        self.assertEqual(result["summary"]["mean_speed_mps"], 3.0)
        self.assertEqual(len(result["samples"]), 3)
        self.assertEqual(result["legal_prudence"], "unresolved")

    def test_missing_required_source_rejected(self):
        (self.root / "context.json").unlink()
        with self.assertRaisesRegex(ValueError, "missing required source"):
            measure(self.root, self.inventory, CASE)

    def test_stale_source_rejected(self):
        self.docs["bicycle_motion"]["samples"][0]["velocity_mps"][0] = 9
        (self.root / "bicycle_motion.json").write_text(json.dumps(self.docs["bicycle_motion"]))
        with self.assertRaisesRegex(ValueError, "stale required source"):
            measure(self.root, self.inventory, CASE)

    def test_frame_join_rejected(self):
        self.docs["bicycle_motion"]["samples"][1]["frame"] = 9
        self.save("bicycle_motion")
        with self.assertRaisesRegex(ValueError, "time join mismatch"):
            measure(self.root, self.inventory, CASE)

    def test_condition_time_join_rejected(self):
        self.docs["context"]["samples"][1]["frame"] = 9
        self.save("context")
        with self.assertRaisesRegex(ValueError, "condition/frame time join"):
            measure(self.root, self.inventory, CASE)

    def test_non_bicycle_rejected(self):
        self.docs["context"]["bicycle_classification"]["moped"] = True
        self.save("context")
        with self.assertRaisesRegex(ValueError, "bicycle classification"):
            measure(self.root, self.inventory, CASE)

    def test_original_position_and_velocity_join(self):
        self.docs["context"]["source_kind"] = "original_local_native_capture"
        self.save("context")
        for index, sample in enumerate(self.docs["bicycle_motion"]["samples"]):
            sample["x_m"] = -30.0 + index * .15
            sample["y_m"] = -.75
        self.save("bicycle_motion")
        self.assertEqual(measure(self.root, self.inventory, CASE)["summary"]["sample_count"], 3)
        self.docs["bicycle_motion"]["samples"][1]["x_m"] = -28.0
        self.save("bicycle_motion")
        with self.assertRaisesRegex(ValueError, "velocity disagrees with position"):
            measure(self.root, self.inventory, CASE)
        del self.docs["bicycle_motion"]["samples"][1]["x_m"]
        self.save("bicycle_motion")
        with self.assertRaisesRegex(ValueError, "missing finite original bicycle position"):
            measure(self.root, self.inventory, CASE)

    def test_outside_path_rejected(self):
        self.inventory["sources"]["context"]["path"] = "../context.json"
        with self.assertRaisesRegex(ValueError, "source path"):
            measure(self.root, self.inventory, CASE)

    def test_saved_cli_writes_once(self):
        inventory = self.root / "inventory.json"
        inventory.write_text(json.dumps(self.inventory))
        output = self.root / "measured.json"
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "speed_measurement.py"),
                   "--root", str(self.root), "--inventory", str(inventory),
                   "--case", CASE, "--output", str(output)]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual(json.loads(output.read_text())["summary"]["sample_count"], 3)
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)


if __name__ == "__main__":
    unittest.main()
