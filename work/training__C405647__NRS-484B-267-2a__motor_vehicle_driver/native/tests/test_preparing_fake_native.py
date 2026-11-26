"""Run the visible-movement capture path through synthetic CARLA substitutes."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT.parents[2] / ".runtime-work" / "c405647-preparing-fake-native"
import test_fake_native as fake

spec = importlib.util.spec_from_file_location(
    "preparing_movement_capture", ROOT / "preparing_movement_capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class MovementActor(fake.Actor):
    def __init__(self, role, pose, actor_id):
        super().__init__(role, pose, actor_id)
        if role == "emergency":
            self.speed = 0

    def apply_control(self, control):
        if self.role == "emergency":
            self.speed = 1 if control.throttle > 0 else 0
        else:
            super().apply_control(control)


class MovementWorld(fake.World):
    def try_spawn_actor(self, blueprint, pose):
        role = "ego" if not self.actors else "emergency"
        actor = MovementActor(role, pose, len(self.actors) + 1)
        self.actors.append(actor)
        return actor


class PreparingFakeNativeTest(unittest.TestCase):
    def test_original_shape_stays_stationary_then_moves(self):
        SCRATCH.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            fake.WORLD = MovementWorld()
            bundle = json.loads((ROOT / "preparing/visible_vehicle_movement/construction.json").read_text())
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
                      "camera_poses": {view: [0, 0, 2, 0, 0, 0] for view in capture.VIEWS}}
            output = Path(temporary) / "attempt"
            with mock.patch.dict(sys.modules, fake.modules()), \
                    mock.patch.dict(os.environ, {"SCENARIO_PIPELINE_OUTPUT_ROOT": str(SCRATCH)}):
                capture.execute(config, survey, output, "127.0.0.1", 2000,
                                diagnostic_fixture=True)
            rows = [json.loads(line) for line in
                    (output / "preparing_observations.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 600)
            self.assertTrue(all(row["qualifying_vehicle"]["speed_mps"] == 0
                                for row in rows[:120]))
            self.assertTrue(any(row["visible_vehicle_movement"] for row in rows[120:]))
            self.assertTrue(all(row["source_kind"] == "synthetic_cpu_fixture" for row in rows))
            self.assertTrue(all(actor.destroyed for actor in fake.WORLD.actors + fake.WORLD.sensors))
            self.assertTrue(all(sensor.stopped for sensor in fake.WORLD.sensors))


if __name__ == "__main__":
    unittest.main()
