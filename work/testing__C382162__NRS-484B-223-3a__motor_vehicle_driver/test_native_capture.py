import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from native_capture import ASSIGNMENT, VIEWS, camera_reader, capture_original
from test_center_lane_site import packet


class Image:
    def __init__(self, frame):
        self.frame, self.width, self.height = frame, 2, 2
        self.raw_data = bytes([0, 10, 20, 255] * 4)


class NativeCaptureTests(unittest.TestCase):
    def test_source_sealed_three_frame_fixture_and_negative_source(self):
        scratch = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work/c382162-owner"))
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            root = Path(tmp)
            native = "original OpenDRIVE"
            case = ASSIGNMENT + "__turn_from_highway"
            site = packet("turn_from_highway")
            values = {
                "map.json": {"opendrive_sha256": hashlib.sha256(native.encode()).hexdigest()},
                "review.json": {"public_highway_confirmed": True,
                                "single_bidirectional_turn_only_center_lane": True,
                                "highway_road_id": "H"},
                "intent.json": {"case_id": case, "route_relationship": "from_highway",
                                "declared_purpose": "left_turn_from_highway",
                                "source_ref": "intent.json", "declared_before_frame": 9}}
            bindings = {}
            for name, value in values.items():
                path = root / name
                path.write_text(json.dumps(value) + "\n")
                bindings[name] = {"path": name,
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            site["native_map_source"] = bindings["map.json"]
            site["highway_review_source"] = bindings["review.json"]

            def read(i):
                return {"original_frame": 10 + i, "time_s": i * .05,
                        "road_id": "S" if i == 2 else "H",
                        "lane_id": ("E", "C", "S")[i],
                        "maneuver": "left_turn" if i == 2 else "travel",
                        "driver_id": "ego", "source_ref": "native/original",
                        "actor_id": 3, "body_vertices_m": [[float(v), 0.0, 0.0] for v in range(8)],
                        "vehicle_blueprint": "vehicle.tesla.model3",
                        "x": float(i), "y": 0.0, "z": 0.0,
                        "heading_x": 1.0, "heading_y": 0.0, "speed_mps": 2.0,
                        "camera_images": {view: Image(10 + i) for view in VIEWS}}

            wrapped = camera_reader(root, read, {view: (2, 2) for view in VIEWS})
            measured = capture_original(root, case, site, bindings["intent.json"], native,
                                        wrapped, count=3)
            self.assertEqual(measured["center_lane_occupancy_frames"], [11])
            self.assertEqual(len(json.loads((root / "native/frame-map.json").read_text())), 3)
            self.assertFalse(json.loads((root / "native/inventory.json").read_text())["physical_acceptance_claimed"])
            (root / "review.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                capture_original(root, case, site, bindings["intent.json"], native,
                                 lambda i: None, count=3)


if __name__ == "__main__":
    unittest.main()
