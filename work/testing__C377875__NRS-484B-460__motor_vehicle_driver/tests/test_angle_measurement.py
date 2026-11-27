import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("angle_measurement", ROOT / "angle_measurement.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def packet():
    assignment = "testing__C377875__NRS-484B-460__motor_vehicle_driver"
    return {
        "source_kind": "original_native",
        "assignment_id": assignment,
        "case_id": assignment + "__park_indicated",
        "capture_source_sha256": "a" * 64,
        "device_source_sha256": "b" * 64,
        "frame_map_sha256": "c" * 64,
        "highway_source_review": "reviewed_original",
        "device": {
            "official_status": "reviewed_original",
            "governs_selected_space": True,
            "content_review": "original reviewed device face and governed parking space",
            "indicated_angle_degrees": 45.0,
        },
        "curb_edge_xy": [[0.0, 0.0], [10.0, 0.0]],
        "halt_purpose_review": {"status": "reviewed_original", "category": "park"},
        "frames": [
            {"frame": 100, "halt_observed": False},
            {"frame": 101, "halt_observed": True, "body_yaw_degrees": 45.0},
            {"frame": 102, "halt_observed": True, "body_yaw_degrees": 45.0},
        ],
    }


class AngleMeasurementTests(unittest.TestCase):
    def test_measures_geometry_without_legal_verdict(self):
        out = module.measure(packet())
        self.assertAlmostEqual(out["body_to_curb_angle_mean_degrees"], 45.0)
        self.assertAlmostEqual(out["mean_difference_from_indication_degrees"], 0.0)
        self.assertEqual(out["legal_classification"], "unreviewed")

    def test_offset_is_measurement_not_invented_tolerance(self):
        source = packet()
        source["frames"][1]["body_yaw_degrees"] = 30.0
        source["frames"][2]["body_yaw_degrees"] = 30.0
        out = module.measure(source)
        self.assertAlmostEqual(out["mean_difference_from_indication_degrees"], -15.0)
        self.assertEqual(out["legal_classification"], "unreviewed")

    def test_unreviewed_device_and_scope_rejected(self):
        source = packet()
        source["device"]["official_status"] = "expected"
        with self.assertRaisesRegex(ValueError, "official-device"):
            module.measure(source)
        source = packet()
        source["device"]["governs_selected_space"] = False
        with self.assertRaisesRegex(ValueError, "scope"):
            module.measure(source)

    def test_source_continuity_and_halt_required(self):
        source = packet()
        source["frames"][2]["frame"] = 104
        with self.assertRaisesRegex(ValueError, "noncontiguous"):
            module.measure(source)
        source = packet()
        source["frames"][2]["halt_observed"] = False
        with self.assertRaisesRegex(ValueError, "at least two"):
            module.measure(source)

    def test_cli_rejects_changed_source_bytes(self):
        with tempfile.TemporaryDirectory(dir=".runtime-work") as tmp:
            p = Path(tmp) / "source.json"
            p.write_text(json.dumps(packet()))
            output = Path(tmp) / "output.json"
            run = subprocess.run([sys.executable, str(ROOT / "angle_measurement.py"),
                                  "--source", str(p), "--source-sha256", "0" * 64,
                                  "--output", str(output)], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("original source hash mismatch", run.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
