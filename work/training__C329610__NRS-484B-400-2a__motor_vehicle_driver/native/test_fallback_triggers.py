import json
import tempfile
import unittest
from pathlib import Path

from fallback_triggers import evaluate


class TriggerTests(unittest.TestCase):
    def test_thresholds_and_independent_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            samples = folder / "native_samples.jsonl"
            route = folder / "native_route_audit.json"
            pixels = folder / "original_pixel_audit.json"
            samples.write_text(json.dumps({"native_center_xy_m": [-20, 1.75]}) + "\n")
            good_route = {"source_kind": "native_map_readback", "connected_lane_link": True,
                          "full_body_destination_exit_observed_by_24s": True}
            good_pixels = {"source_kind": "original_camera_pixels",
                           "body_and_centerline_visible_frames": 95, "approach_frames": 100}
            route.write_text(json.dumps(good_route)); pixels.write_text(json.dumps(good_pixels))
            self.assertEqual([evaluate(samples, route, pixels, 1.75)[key]
                              for key in ("fallback1", "fallback2", "fallback3")],
                             [False, False, False])
            route.write_text(json.dumps(dict(good_route, connected_lane_link=False)))
            self.assertTrue(evaluate(samples, route, pixels, 1.75)["fallback1"])
            route.write_text(json.dumps(good_route))
            samples.write_text(json.dumps({"native_center_xy_m": [-20, 2.11]}) + "\n")
            self.assertTrue(evaluate(samples, route, pixels, 1.75)["fallback2"])
            samples.write_text(json.dumps({"native_center_xy_m": [-20, 1.75]}) + "\n")
            pixels.write_text(json.dumps(dict(good_pixels, body_and_centerline_visible_frames=94)))
            self.assertTrue(evaluate(samples, route, pixels, 1.75)["fallback3"])

    def test_unobserved_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            samples = folder / "native_samples.jsonl"
            route = folder / "native_route_audit.json"
            pixels = folder / "original_pixel_audit.json"
            samples.write_text(json.dumps({"native_center_xy_m": [-20, 1.75]}) + "\n")
            route.write_text(json.dumps({"source_kind": "authored_request",
                                         "connected_lane_link": True,
                                         "full_body_destination_exit_observed_by_24s": True}))
            pixels.write_text(json.dumps({"source_kind": "original_camera_pixels",
                                          "body_and_centerline_visible_frames": 1, "approach_frames": 1}))
            with self.assertRaisesRegex(ValueError, "original-source"):
                evaluate(samples, route, pixels, 1.75)


if __name__ == "__main__":
    unittest.main()
