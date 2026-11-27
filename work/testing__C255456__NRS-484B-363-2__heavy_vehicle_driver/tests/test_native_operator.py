"""Native adapter source gates and exact geometry helpers without CARLA import."""

import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_operator import CrossingOperator, _transform


class Actors:
    def find(self, identifier):
        return None


class World:
    def get_actors(self):
        return Actors()


class NativeOperatorTest(unittest.TestCase):
    def site(self):
        return {
            "native_vehicle_spawn": {"x": 0, "y": 0, "z": 1, "yaw": 0},
            "native_camera_mounts": {name: {"x": 0, "y": 0, "z": 2, "yaw": 0}
                                     for name in ("overview", "approach", "reference_corner", "driver_reference")},
            "native_child_spawns": [], "children_xy_m": [],
            "native_beacon_lamp_actor_ids": [101, 102],
            "beacon_yellow_lamp_count": 2, "native_sign_actor_id": 201,
        }

    def test_missing_reviewed_beacon_actor_rejected(self):
        with self.assertRaisesRegex(ValueError, "beacon actor absent"):
            CrossingOperator(World(), self.site(), "case")

    def test_missing_reviewed_camera_mount_rejected(self):
        site = self.site()
        site["native_camera_mounts"].pop("overview")
        with self.assertRaisesRegex(ValueError, "camera mounts"):
            CrossingOperator(World(), site, "case")

    def test_native_transform_rejects_nonfinite(self):
        fake = types.SimpleNamespace(Location=lambda **kwargs: kwargs,
                                     Rotation=lambda **kwargs: kwargs,
                                     Transform=lambda location, rotation: (location, rotation))
        good = _transform(fake, {"x": 1, "y": 2, "z": 3, "yaw": 4})
        self.assertEqual(good[0]["x"], 1)
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            _transform(fake, {"x": float("nan"), "y": 2, "z": 3, "yaw": 4})


if __name__ == "__main__":
    unittest.main()
