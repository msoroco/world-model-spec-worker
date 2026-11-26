import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_capture import capture
from speed_source_review import measure
import test_posted_site as site_tests


CASE = "testing__C136559__NRS-484B-600-1c__motor_vehicle_driver__above"


class FakeAdapter:
    def __init__(self, bad_frame=False):
        self.index = 0
        self.bad_frame = bad_frame
        self.destroyed = False
        self.closed = False

    def setup(self, config, site):
        self.site = site

    def spawn_ego(self, lane_id, config):
        if lane_id != "lane-a":
            raise AssertionError("wrong travel lane")
        return "ego"

    def attach_cameras(self, ego, cameras):
        return {camera["name"]: camera["name"] for camera in cameras}

    def apply_control(self, ego, throttle, brake):
        if not (0 <= throttle <= 1 and 0 <= brake <= 1):
            raise AssertionError("invalid control")

    def tick_and_read(self, ego, cameras):
        index = self.index
        self.index += 1
        frame = index + (1 if self.bad_frame and index == 1 else 0)
        t = round(index / 20, 2)
        return {"frame": frame, "time_s": t, "speed_mps": 12.0,
                "road_id": "road", "segment_id": "segment", "direction": "forward",
                "on_highway": True, "operating": True,
                "camera_png": {name: b"\x89PNG\r\n\x1a\nsynthetic" for name in cameras},
                "trace": {"frame": frame, "time_s": t, "position": {"x": index},
                          "speed_mps": 12.0},
                "video_frame": {"carla_frame": frame, "time_s": t,
                                "video_frame": index}}

    def finalize_media(self, output, views, mapping):
        media = {}
        for name in (*views, "raw"):
            path = output / (name + ".mkv")
            path.write_bytes(b"synthetic media; decoder must reject this")
            media[name] = path
        return media

    def destroy(self, actor):
        self.destroyed = True

    def close(self):
        self.closed = True
        return True


class NativeCaptureTests(unittest.TestCase):
    def setup_attempt(self, root):
        output = root / "attempt"
        output.mkdir()
        (output / "construction.json").write_text("{}\n")
        (output / "runner.py").write_text("pass\n")
        site = root / "site.json"
        site.write_text(json.dumps(site_tests.PostedSiteTests().packet()) + "\n")
        config = {"selected_case_id": CASE, "frame_count": 900,
                  "case": {"draft_variables": {"rate_relation": "above",
                                              "travel_direction": "forward"}},
                  "control": {"tracking_gain": 0.3},
                  "cameras": [{"name": name} for name in
                              ("overview", "approach", "reference_corner", "driver_reference")]}
        return output, site, hashlib.sha256(site.read_bytes()).hexdigest(), config

    def test_exact_capture_is_sealed_and_source_measurable(self):
        with tempfile.TemporaryDirectory() as directory:
            output, site, digest, config = self.setup_attempt(Path(directory))
            adapter = FakeAdapter()
            receipt = capture(adapter, config, site, digest, output)
            self.assertEqual(receipt["frame_count"], 900)
            inventory = json.loads((output / "original-attempt/inventory.json").read_text())
            self.assertEqual(measure(output / "original-attempt", inventory, CASE)["original_frames"], 900)
            self.assertTrue(adapter.destroyed and adapter.closed)

    def test_frame_gap_restores_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            output, site, digest, config = self.setup_attempt(Path(directory))
            adapter = FakeAdapter(bad_frame=True)
            with self.assertRaisesRegex(ValueError, "frame/time gap"):
                capture(adapter, config, site, digest, output)
            self.assertTrue(adapter.destroyed and adapter.closed)
