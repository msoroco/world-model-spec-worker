from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_cameras import placements, spawn
from saved_entry import CAMERAS


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class World:
    def __init__(self, fail_at=0):
        self.spawned = []
        self.fail_at = fail_at

    def get_blueprint_library(self):
        return NS(find=lambda name: Blueprint())

    def spawn_actor(self, blueprint, transform):
        if self.fail_at == len(self.spawned) + 1:
            return None
        sensor = NS(blueprint=blueprint, transform=transform, destroyed=False)
        sensor.destroy = lambda: setattr(sensor, "destroyed", True)
        self.spawned.append(sensor)
        return sensor


def scene():
    return {"camera_placement_review": {"complete": True, "source_sha256": "a" * 64},
            "camera_placements": {name: {"location_xyz_m": [i + 1, -8, 5],
                                         "target_xyz_m": [4, 3, 1]}
                                  for i, name in enumerate(CAMERAS)}}


class CameraTests(unittest.TestCase):
    def setUp(self):
        self.carla = NS(Location=lambda **k: NS(**k), Rotation=lambda **k: NS(**k),
                        Transform=lambda location, rotation: NS(location=location, rotation=rotation))

    def test_four_reviewed_sensors_are_spawned_with_aim_and_resolution(self):
        world = World()
        sensors = spawn(world, self.carla, scene())
        self.assertEqual(set(sensors), set(CAMERAS))
        self.assertEqual(sensors["overview"].blueprint.attributes["image_size_x"], "1920")
        self.assertGreater(sensors["overview"].transform.rotation.yaw, 0)

    def test_missing_review_and_degenerate_aim_fail_before_spawning(self):
        exact = scene()
        exact["camera_placement_review"]["complete"] = False
        with self.assertRaisesRegex(ValueError, "review"):
            placements(exact)
        exact = scene()
        exact["camera_placements"]["overview"]["target_xyz_m"] = [1, -8, 1]
        with self.assertRaisesRegex(ValueError, "degenerate"):
            placements(exact)

    def test_partial_camera_spawn_is_destroyed(self):
        world = World(fail_at=3)
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            spawn(world, self.carla, scene())
        self.assertEqual(len(world.spawned), 2)
        self.assertTrue(all(sensor.destroyed for sensor in world.spawned))


if __name__ == "__main__":
    unittest.main()
