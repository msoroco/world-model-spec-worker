import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_camera_rig import NativeCameraRig, CAMERAS


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class Sensor:
    def __init__(self, sensor_id):
        self.id = sensor_id
        self.callback = None
        self.stopped = False
        self.destroyed = False

    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.blueprints = []
        self.sensors = []
        self.poses = []

    def get_blueprint_library(self):
        return self

    def find(self, name):
        if name != "sensor.camera.rgb":
            raise ValueError(name)
        blueprint = Blueprint()
        self.blueprints.append(blueprint)
        return blueprint

    def spawn_actor(self, blueprint, pose):
        sensor = Sensor(len(self.sensors) + 10)
        self.sensors.append(sensor)
        self.poses.append(pose)
        return sensor


class CameraRigTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3] / ".runtime-work" / "c104081-rig-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.world = World()
        self.carla = SimpleNamespace(
            Location=lambda **kw: SimpleNamespace(**kw),
            Rotation=lambda **kw: SimpleNamespace(**kw),
            Transform=lambda location, rotation: SimpleNamespace(location=location, rotation=rotation))
        self.survey = {
            "source_kind": "original_native_map_survey", "cell_id": "C104081",
            "map_id": "observed-hill", "layout": "hill_crest",
            "surfaces": {name: {"surveyed": True} for name in
                         ("sidewalk", "intervening_area", "designated_bicycle_lane",
                          "immediately_adjacent_highway")},
            "local_to_world": {"x": 3.0, "y": 5.0, "yaw_degrees": 90.0},
            "camera_views": {name: {"x": float(i), "y": 0.0, "z": 2.0,
                                    "yaw": 0.0, "pitch": -5.0, "roll": 0.0}
                             for i, name in enumerate(CAMERAS)},
        }

    def make_rig(self):
        raw = (json.dumps(self.survey) + "\n").encode()
        path = self.root / "survey.json"
        path.write_bytes(raw)
        rig = NativeCameraRig(self.world, self.carla, path, hashlib.sha256(raw).hexdigest(),
                              self.root / "encoding", dimensions={name: (2, 2) for name in CAMERAS},
                              timeout_s=.01)
        self.addCleanup(rig.close)
        return rig

    def test_owned_actors_and_original_tick_join(self):
        rig = self.make_rig()
        self.assertEqual(len(self.world.sensors), 4)
        self.assertEqual(self.world.blueprints[0].attributes["sensor_tick"], "0.05")
        self.assertAlmostEqual(self.world.poses[1].location.y, 6.0)
        for sensor in self.world.sensors:
            sensor.callback(SimpleNamespace(frame=42, width=2, height=2,
                                             raw_data=bytes([sensor.id] * 16)))
        self.assertEqual(rig.sync(42), {name: 42 for name in CAMERAS})
        rig.close()
        self.assertTrue(all(s.stopped and s.destroyed for s in self.world.sensors))

    def test_missing_or_stale_callback_rejected(self):
        rig = self.make_rig()
        with self.assertRaisesRegex(ValueError, "missing original camera callback"):
            rig.sync(42)
        self.world.sensors[0].callback(SimpleNamespace(frame=41, width=2, height=2,
                                                       raw_data=bytes(16)))
        with self.assertRaisesRegex(ValueError, "stale or mismatched"):
            rig.sync(42)

    def test_unobserved_pose_rejected_before_spawn(self):
        self.survey["camera_views"].pop("approach")
        with self.assertRaisesRegex(ValueError, "four original surveyed"):
            self.make_rig()
        self.assertFalse(self.world.sensors)


if __name__ == "__main__":
    unittest.main()
