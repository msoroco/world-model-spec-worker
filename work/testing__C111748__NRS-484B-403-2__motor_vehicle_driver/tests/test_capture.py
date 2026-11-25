import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
CASE = "testing__C111748__NRS-484B-403-2__motor_vehicle_driver__prohibited_attempt"


def site():
    return {"case_id": CASE, "map_name": "Town01", "map_sha256": "reviewed-map",
            "highway_status": {"source_sha256": "reviewed-highway"},
            "ego_blueprint": "vehicle.test", "ego_spawn": [1, 2], "ego_id": 42,
            "device_blueprint": "static.prop.sign",
            "u_turn_route": [{"road_id": 1, "lane_id": 1},
                             {"road_id": 1, "lane_id": 1, "junction_id": 1},
                             {"road_id": 1, "lane_id": -1}],
            "camera_plan_sha256": "reviewed-cameras",
            "device": {"device_id": 77, "authority_source_sha256": "reviewed-authority",
                       "legal_consistency_source_sha256": "reviewed-law",
                       "display_source_sha256": "reviewed-display",
                       "governed_approach": "A", "position_xy_m": [1, 2],
                       "prohibits_u_turn": True}}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        raw = json.dumps(site()).encode()
        self.source = self.base / "site.json"
        self.source.write_bytes(raw)
        self.sha = hashlib.sha256(raw).hexdigest()
        self.output = self.base / "native.json"
        self.count = 0
        self.braked = 0

    def run_capture(self, *, bad_camera=False, bad_display=False, bad_time=False, bad_source=False):
        def tick():
            i = self.count
            self.count += 1
            return 100 + i, (i / 20 + (0.1 if bad_time and i == 2 else 0))

        def sample(frame):
            i = frame - 100
            return {"ego": {"id": 42, "road_id": 1,
                             "lane_id": -1 if i == 3 else 1,
                             "x": i, "y": 0, "yaw_deg": 180 if i == 3 else 0,
                             "approach_id": "A", "u_turn_in_progress": i == 2},
                    "device_readback": {"device_id": 77,
                                        "prohibits_u_turn": not bad_display,
                                        "visible_to_ego": i >= 1},
                    "cameras": {name: frame + (1 if bad_camera and name == "approach" else 0)
                                for name in capture.CAMERAS}}

        return capture.capture(self.source, "wrong" if bad_source else self.sha,
                               CASE, self.output, tick=tick,
                               apply_control=lambda i, s: None, sample=sample,
                               brake=lambda: setattr(self, "braked", self.braked + 1),
                               frames=4, diagnostic=True)

    def test_source_bound_four_camera_capture(self):
        result = self.run_capture()
        self.assertEqual(result["frame_count"], 4)
        self.assertTrue(result["measurement"]["turn_observed"])
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), result["native_sha256"])
        self.assertEqual(self.braked, 1)
        self.assertFalse(result["actual_pixels"])
        self.assertTrue(json.loads(self.output.read_text())["diagnostic"])

    def test_reject_camera_frame_mismatch_and_brake(self):
        with self.assertRaisesRegex(capture.CaptureError, "camera original frame"):
            self.run_capture(bad_camera=True)
        self.assertEqual(self.braked, 1)
        self.assertFalse(self.output.exists())

    def test_reject_display_drift_and_brake(self):
        with self.assertRaisesRegex(capture.CaptureError, "live display"):
            self.run_capture(bad_display=True)
        self.assertEqual(self.braked, 1)

    def test_reject_time_drift_and_brake(self):
        with self.assertRaisesRegex(capture.CaptureError, "20 Hz"):
            self.run_capture(bad_time=True)
        self.assertEqual(self.braked, 1)

    def test_reject_source_drift_before_control(self):
        with self.assertRaisesRegex(ValueError, "source hash"):
            self.run_capture(bad_source=True)
        self.assertEqual(self.count, 0)

    def test_short_capture_requires_diagnostic(self):
        with self.assertRaisesRegex(capture.CaptureError, "diagnostic"):
            capture.capture(self.source, self.sha, CASE, self.output,
                            tick=lambda: (1, 0), apply_control=lambda i, s: None,
                            sample=lambda f: {}, brake=lambda: None, frames=4)
