import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake_native_plan import CASE, control, prepare, verify_loaded_site
from runner import CAMERA_SETUP, Cameras


class NativePlanTests(unittest.TestCase):
    def site(self, root):
        site = {"map_name": "CPU survey test", "road_kind": "road",
                "ego_start_xy_m": [0., 0.], "overtaker_start_xy_m": [-10., 3.],
                "forward_xy": [1., 0.], "ego_road_id": 1, "ego_lane_id": -1,
                "overtaker_road_id": 1, "overtaker_lane_id": -2,
                "ego_right_clearance_m": 2.}
        path = root / "site.json"
        path.write_text(json.dumps(site))
        return path, hashlib.sha256(path.read_bytes()).hexdigest(), site

    def test_hashed_site_selects_two_targets_and_loaded_waypoints(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest, _ = self.site(Path(directory))
            plan = prepare(CASE, path, digest)
            self.assertEqual(plan["ego_target_xy_m"], [22., -.6])
            self.assertEqual(plan["overtaker_target_xy_m"], [35., 3.])
            class Map:
                name = "CPU survey test"
                def get_waypoint(self, location, **_):
                    lane = -1 if location.x == 0 else -2
                    return SimpleNamespace(road_id=1, lane_id=lane,
                        transform=SimpleNamespace(location=location))
            self.assertEqual(len(verify_loaded_site(Map(), plan, "driving", SimpleNamespace)), 2)
            self.assertFalse(plan["physical_completion_claimed"])

    def test_rejects_changed_site_and_bad_relative_start(self):
        with tempfile.TemporaryDirectory() as directory:
            path, digest, site = self.site(Path(directory))
            path.write_text(path.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                prepare(CASE, path, digest)
            site["overtaker_start_xy_m"] = [3., 3.]
            path.write_text(json.dumps(site))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "behind and to the left"):
                prepare(CASE, path, digest)

    def test_controller_steers_to_rightward_target_and_brakes(self):
        value = control((0., 0.), (1., 0.), (4., 0.), (20., -1.), 4.)
        self.assertLess(value["steer"], 0)
        self.assertEqual(value["throttle"], 0.)
        self.assertEqual(control((20., -1.), (1., 0.), (0., 0.), (20., -1.), 4.)["brake"], 1.)

    def test_four_native_cameras_are_constructed_and_joined(self):
        class Blueprint:
            def __init__(self): self.attributes = {}
            def set_attribute(self, key, value): self.attributes[key] = value
        class Sensor:
            def listen(self, callback): self.callback = callback
            def stop(self): pass
            def destroy(self): pass
        class World:
            def __init__(self): self.blueprints = []; self.sensors = []
            def get_blueprint_library(self): return self
            def find(self, name):
                self.asserted_name = name
                item = Blueprint(); self.blueprints.append(item); return item
            def spawn_actor(self, blueprint, transform, attach_to):
                self.assertEqualAttach = attach_to
                sensor = Sensor(); self.sensors.append(sensor); return sensor
        world = World()
        carla = SimpleNamespace(Transform=lambda *parts: parts,
            Location=lambda *parts: parts, Rotation=lambda *parts: parts)
        observed = []
        cameras = Cameras(world, carla, "ego", lambda name, image: observed.append(name))
        self.assertEqual(world.assertEqualAttach, "ego")
        self.assertEqual(len(world.sensors), 4)
        for sensor, (name, spec) in zip(world.sensors, CAMERA_SETUP.items()):
            blueprint = world.blueprints[list(CAMERA_SETUP).index(name)]
            self.assertEqual(blueprint.attributes["image_size_x"], str(spec[2][0]))
            self.assertEqual(blueprint.attributes["sensor_tick"], "0.05")
            image = SimpleNamespace(frame=10, width=spec[2][0], height=spec[2][1])
            sensor.callback(image)
        cameras.wait(10, timeout_s=.01)
        cameras.verify([10])
        self.assertEqual(observed, list(CAMERA_SETUP))
        cameras.close()


if __name__ == "__main__":
    unittest.main()
