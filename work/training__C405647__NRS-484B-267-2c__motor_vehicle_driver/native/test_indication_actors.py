"""Exercise Native walker calls using CPU fake actors."""

import types
import unittest

from indication_actors import apply_indication, spawn_indication_actor


class Carla:
    class Location:
        def __init__(self, **values):
            self.__dict__.update(values)

    class Rotation:
        def __init__(self, **values):
            self.__dict__.update(values)

    class Transform:
        def __init__(self, location=None, rotation=None):
            self.location = location
            self.rotation = rotation

    class WalkerBoneControlIn:
        def __init__(self, rows):
            self.bone_transforms = rows


class Walker:
    def __init__(self, drop_hand=False):
        self.drop_hand = drop_hand
        self.calls = []

    def set_bones(self, control):
        self.calls.append(("set_bones", control))

    def show_pose(self):
        self.calls.append(("show_pose", None))

    def get_bones(self):
        rows = self.calls[0][1].bone_transforms
        if self.drop_hand:
            rows = rows[:-1]
        return types.SimpleNamespace(bone_transforms=rows)


class IndicationActors(unittest.TestCase):
    def test_hand_signal_calls_and_native_readback(self):
        walker = Walker()
        result = apply_indication(Carla, walker, "R")
        self.assertEqual([name for name, _ in walker.calls], ["set_bones", "show_pose"])
        self.assertIn("crl_hand__R", result["requested_bones"])
        self.assertTrue(result["native_bones_read_back"])
        self.assertFalse(result["original_pixel_visibility_verified"])

    def test_missing_original_bone_rejected(self):
        with self.assertRaisesRegex(ValueError, "bones absent"):
            apply_indication(Carla, Walker(drop_hand=True), "R")

    def test_source_driver_proxy_uses_authored_geometry(self):
        calls = []
        world = types.SimpleNamespace(
            get_blueprint_library=lambda: types.SimpleNamespace(find=lambda name: name),
            try_spawn_actor=lambda blueprint, pose: calls.append((blueprint, pose)) or Walker())
        source = types.SimpleNamespace(get_location=lambda: types.SimpleNamespace(x=15, y=5))
        spawn_indication_actor(Carla, world, "walker.pedestrian.0001", [15, -8.25, 1.5], source)
        self.assertEqual(calls[0][0], "walker.pedestrian.0001")
        self.assertEqual((calls[0][1].location.x, calls[0][1].location.y), (15, 8.25))

    def test_unrelated_source_driver_proxy_rejected(self):
        source = types.SimpleNamespace(get_location=lambda: types.SimpleNamespace(x=15, y=5))
        with self.assertRaisesRegex(ValueError, "not beside"):
            spawn_indication_actor(Carla, None, "walker.pedestrian.0001", [30, -8.25, 1.5], source)

    def test_nonwalker_rejected(self):
        with self.assertRaisesRegex(ValueError, "walker skeleton"):
            spawn_indication_actor(Carla, None, "vehicle.tesla.model3", [15, -8.25, 1.5])


if __name__ == "__main__":
    unittest.main()
