import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_entry import _device_actors, _camera_sensors
from carla_readback import CameraFrames


class NativeEntryTests(unittest.TestCase):
    def test_reviewed_device_pose_joins_distinct_original_actors(self):
        class Actor:
            type_id = "traffic.traffic_light"
            def __init__(self, ident, x):
                self.id, self.x = ident, x
            def get_location(self):
                return type("Position", (), {"x": self.x, "y": 0, "z": 0})()
        class Actors(list):
            def filter(self, query):
                return self
        class World:
            def get_actors(self):
                return Actors([Actor(11, 0), Actor(22, 100)])
        packet = {"devices": [{"device_id": "west-signal"},
                              {"device_id": "east-signal"}]}
        inventory = {"devices": [{"device_id": "west-signal",
            "location_xyz_m": [0, 0, 0], "type_id": "traffic.traffic_light"},
            {"device_id": "east-signal", "location_xyz_m": [100, 0, 0],
             "type_id": "traffic.traffic_light"}]}
        bound = _device_actors(World(), packet, inventory)
        self.assertEqual({name: actor.id for name, actor in bound.items()},
                         {"west-signal": 11, "east-signal": 22})
        inventory["devices"][1]["location_xyz_m"] = [0, 0, 0]
        with self.assertRaisesRegex(ValueError, "reused a Native actor"):
            _device_actors(World(), packet, inventory)

    def test_missing_camera_placement_rejected_before_spawn(self):
        with self.assertRaisesRegex(ValueError, "four reviewed original camera"):
            _camera_sensors(object(), object(), {"cameras": {}}, CameraFrames())


if __name__ == "__main__":
    unittest.main()
