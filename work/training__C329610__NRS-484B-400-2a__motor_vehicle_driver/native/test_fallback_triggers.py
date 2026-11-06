import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from fallback_triggers import evaluate


class TriggerTests(unittest.TestCase):
    @staticmethod
    def sealed_route(samples, geometry, **changes):
        route = {"source_kind": "native_map_readback", "connected_lane_link": True,
                 "full_body_destination_exit_observed_by_24s": True,
                 "native_samples_sha256": hashlib.sha256(samples.read_bytes()).hexdigest(),
                 "road_geometry_sha256": hashlib.sha256(geometry.read_bytes()).hexdigest(),
                 "native_map_sha256": "0" * 64}
        route.update(changes)
        return route

    def test_thresholds_and_independent_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            samples = folder / "native_samples.jsonl"
            geometry = folder / "road_geometry.json"
            route = folder / "native_route_audit.json"
            pixels = folder / "original_pixel_audit.json"
            samples.write_text(json.dumps({"native_center_xy_m": [-20, -1.75]}) + "\n")
            geometry.write_text(json.dumps({"native_map_sha256": "0" * 64}))
            good_route = self.sealed_route(samples, geometry)
            good_pixels = {"source_kind": "original_camera_pixels",
                           "body_and_centerline_visible_frames": 95, "approach_frames": 100}
            route.write_text(json.dumps(good_route)); pixels.write_text(json.dumps(good_pixels))
            self.assertEqual([evaluate(samples, geometry, route, pixels, -1.75)[key]
                              for key in ("fallback1", "fallback2", "fallback3")],
                             [False, False, False])
            route.write_text(json.dumps(dict(good_route, connected_lane_link=False)))
            self.assertTrue(evaluate(samples, geometry, route, pixels, -1.75)["fallback1"])
            route.write_text(json.dumps(good_route))
            samples.write_text(json.dumps({"native_center_xy_m": [-20, -2.11]}) + "\n")
            route.write_text(json.dumps(self.sealed_route(samples, geometry)))
            self.assertTrue(evaluate(samples, geometry, route, pixels, -1.75)["fallback2"])
            samples.write_text(json.dumps({"native_center_xy_m": [-20, -1.75]}) + "\n")
            route.write_text(json.dumps(self.sealed_route(samples, geometry)))
            pixels.write_text(json.dumps(dict(good_pixels, body_and_centerline_visible_frames=94)))
            self.assertTrue(evaluate(samples, geometry, route, pixels, -1.75)["fallback3"])

    def test_unobserved_source_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            samples = folder / "native_samples.jsonl"
            geometry = folder / "road_geometry.json"
            route = folder / "native_route_audit.json"
            pixels = folder / "original_pixel_audit.json"
            samples.write_text(json.dumps({"native_center_xy_m": [-20, -1.75]}) + "\n")
            geometry.write_text(json.dumps({"native_map_sha256": "0" * 64}))
            route.write_text(json.dumps(self.sealed_route(samples, geometry,
                                          source_kind="authored_request")))
            pixels.write_text(json.dumps({"source_kind": "original_camera_pixels",
                                          "body_and_centerline_visible_frames": 1, "approach_frames": 1}))
            with self.assertRaisesRegex(ValueError, "original-source"):
                evaluate(samples, geometry, route, pixels, -1.75)

    def test_changed_sources_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            samples = folder / "native_samples.jsonl"
            geometry = folder / "road_geometry.json"
            route = folder / "route_audit.json"
            pixels = folder / "pixel_audit.json"
            samples.write_text(json.dumps({"native_center_xy_m": [-20, -1.75]}) + "\n")
            geometry.write_text(json.dumps({"native_map_sha256": "0" * 64}))
            route.write_text(json.dumps(self.sealed_route(samples, geometry)))
            pixels.write_text(json.dumps({"source_kind": "original_camera_pixels",
                                          "body_and_centerline_visible_frames": 1,
                                          "approach_frames": 1}))
            samples.write_text(json.dumps({"native_center_xy_m": [-20, -2.0]}) + "\n")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                evaluate(samples, geometry, route, pixels, -1.75)
            samples.write_text(json.dumps({"native_center_xy_m": [-20, -1.75]}) + "\n")
            geometry.write_text(json.dumps({"native_map_sha256": "1" * 64}))
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                evaluate(samples, geometry, route, pixels, -1.75)


if __name__ == "__main__":
    unittest.main()
