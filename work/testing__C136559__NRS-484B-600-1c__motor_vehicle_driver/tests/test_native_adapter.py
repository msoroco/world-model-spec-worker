import hashlib
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_adapter import native_plan, route_readback


class NativeAdapterSourceTests(unittest.TestCase):
    def packet(self):
        pose = {key: 0.0 for key in ("x", "y", "z", "pitch", "yaw", "roll")}
        return {"travel_lanes": {"forward": "1", "opposite": "-1"},
                "native": {"map_opendrive_sha256": hashlib.sha256(b"map").hexdigest(),
                           "vehicle_blueprint_id": "vehicle.test.car",
                           "spawn": pose, "camera_poses": {name: pose for name in
                           ("overview", "approach", "reference_corner", "driver_reference")},
                           "segments": [{"road_id": 4, "segment_id": "governed",
                                         "s_start": 0.0, "s_end": 30.0,
                                         "on_highway": True}]}}

    def test_reviewed_map_and_route_readback(self):
        site = self.packet()
        native = native_plan(site, "map")
        observed = route_readback(SimpleNamespace(road_id=4, lane_id=1, s=12.0), site, native)
        self.assertEqual(observed, {"road_id": "4", "segment_id": "governed",
                                    "direction": "forward", "on_highway": True})
        with self.assertRaisesRegex(ValueError, "unique reviewed"):
            route_readback(SimpleNamespace(road_id=4, lane_id=1, s=31.0), site, native)

    def test_stale_map_and_missing_camera_pose_rejected(self):
        site = self.packet()
        with self.assertRaisesRegex(ValueError, "OpenDRIVE"):
            native_plan(site, "other map")
        site["native"]["camera_poses"].pop("driver_reference")
        with self.assertRaisesRegex(ValueError, "four reviewed"):
            native_plan(site, "map")
