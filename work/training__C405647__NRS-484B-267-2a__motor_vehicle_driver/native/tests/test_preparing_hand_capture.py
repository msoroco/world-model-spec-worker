"""Exercise prospective driver hand-pose acquisition with synthetic CARLA actors."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[2] / ".runtime-work" / "c405647-hand-fake-native"
sys.path.insert(0, str(ROOT))
import test_fake_native as fake

spec = importlib.util.spec_from_file_location(
    "preparing_hand_capture", ROOT / "preparing_hand_capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class BoneControl:
    def __init__(self):
        self.bone_transforms = []


class Driver(fake.Actor):
    def __init__(self, pose, actor_id):
        super().__init__("driver", pose, actor_id)
        self.speed = 0
        self.poses = []

    def apply_control(self, control):
        self.poses.append(control)

    def show_pose(self):
        pass

    def hide_pose(self):
        pass


class HandWorld(fake.World):
    def try_spawn_actor(self, blueprint, pose):
        role = ("ego", "emergency", "driver")[len(self.actors)]
        if role == "driver":
            actor = Driver(pose, len(self.actors) + 1)
        else:
            actor = fake.Actor(role, pose, len(self.actors) + 1)
            if role == "emergency":
                actor.speed = 0
        self.actors.append(actor)
        return actor


class PreparingHandCaptureTest(unittest.TestCase):
    def test_hand_pose_requested_but_pixels_unconfirmed(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            fake.WORLD = HandWorld()
            bundle = json.loads((ROOT / "preparing/visible_driver_hand_signal/construction.json").read_text())
            config = json.loads(next(item["content"] for item in bundle["files"]
                                     if item["path"] == "config.json"))
            survey = {"source_kind": "original_native_site_survey",
                      "cell": {"layout": "road", "maneuver": "travel",
                               "control": "emergency_vehicle"},
                      "map_name": "synthetic-road", "ego_blueprint": "synthetic-ego",
                      "emergency_blueprint": "synthetic-emergency",
                      "ego_spawn_xyz_yaw_deg": [-100, 0, 0.5, 0],
                      "emergency_spawn_xyz_yaw_deg": [100, 0, 0.5, 0],
                      "emergency_authorization_source_id": "synthetic-authorization",
                      "flashing_equipment_source_id": "synthetic-equipment",
                      "flashing_qualification_source_id": "synthetic-qualification",
                      "road_context_source_id": "synthetic-road",
                      "weather_context_source_id": "synthetic-weather",
                      "officer_direction_source_id": "synthetic-officer",
                      "officer_direction": None,
                      "driver_blueprint": "walker.pedestrian.0001",
                      "driver_spawn_xyz_yaw_deg": [100, 0.5, 0.5, 0],
                      "driver_vehicle_identity_source_id": "synthetic-driver-vehicle",
                      "hand_signal_pose_source_id": "synthetic-pose",
                      "driver_window_visibility_source_id": "synthetic-window",
                      "camera_poses": {view: [0, 0, 2, 0, 0, 0] for view in capture.VIEWS}}
            output = Path(temporary) / "attempt"
            modules = fake.modules()
            modules["carla"].WalkerBoneControl = BoneControl
            modules["carla"].Transform = lambda location=None, rotation=None: fake.Transform(
                location or fake.Vector(), rotation or fake.Rotation())
            with mock.patch.dict(sys.modules, modules), \
                    mock.patch.dict(os.environ, {"SCENARIO_PIPELINE_OUTPUT_ROOT": str(SCRATCH)}):
                capture.execute(config, survey, output, "127.0.0.1", 2000,
                                diagnostic_fixture=True)
            rows = [json.loads(line) for line in
                    (output / "preparing_observations.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 600)
            self.assertTrue(all(not row["hand_signal_pose_requested"] for row in rows[:120]))
            self.assertTrue(all(row["hand_signal_pose_requested"] for row in rows[120:]))
            self.assertTrue(all(not row["visible_driver_hand_signal"] for row in rows))
            self.assertEqual(rows[120]["hand_signal_driver_actor_id"], 3)
            self.assertEqual(len(fake.WORLD.actors[2].poses), 480)
            self.assertTrue(all(actor.destroyed for actor in fake.WORLD.actors + fake.WORLD.sensors))


if __name__ == "__main__":
    unittest.main()
