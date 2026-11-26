import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("capture_runner", ROOT / "capture_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def config(suffix):
    return json.loads(json.loads((ROOT / ("condition_" + suffix + "-construction.json")).read_text())["files"][0]["content"])


def survey():
    return {"source_kind": "original_native_site_survey", "cell": {"layout": "road", "maneuver": "travel",
            "control": "emergency_vehicle"}, "map_name": "surveyed-map", "ego_blueprint": "vehicle.ego",
            "emergency_blueprint": "vehicle.emergency", "ego_spawn_xyz_yaw_deg": [0, 0, 0.5, 0],
            "emergency_spawn_xyz_yaw_deg": [180, 0, 0.5, 0],
            "emergency_authorization_source_id": "original-actor-registry",
            "flashing_equipment_source_id": "original-equipment-source",
            "flashing_qualification_source_id": "original-qualification-source",
            "road_context_source_id": "original-road-source",
            "weather_context_source_id": "original-weather-source",
            "officer_direction_source_id": "original-scene-source", "officer_direction": None,
            "camera_poses": {name: [0, 0, 2, 0, 0, 0] for name in runner.VIEWS}}


class CapturePlanTest(unittest.TestCase):
    def test_four_original_camera_encode_commands(self):
        for name in runner.VIEWS:
            command = runner.camera_encode_command("/tmp/original-attempt", name)
            self.assertEqual(command[0], "ffmpeg")
            self.assertEqual(command[command.index("-frames:v") + 1], "600")
            self.assertEqual(command[command.index("-framerate") + 1], "20")
            self.assertTrue(any(value.endswith(name + "/%06d.png") for value in command))
            self.assertTrue(command[-1].endswith("/" + name + ".mkv"))

    def test_two_exact_plans(self):
        for suffix in ("a", "b"):
            with self.subTest(suffix=suffix):
                report = runner.check(config(suffix), survey())
                self.assertEqual(report["frames"], 600)
                self.assertFalse(report["native_executed"])

    def test_road_alignment_rejected(self):
        site = survey()
        site["emergency_spawn_xyz_yaw_deg"][0] = -90
        with self.assertRaisesRegex(ValueError, "approach direction"):
            runner.check(config("a"), site)

    def test_missing_authorization_rejected(self):
        site = survey()
        site["emergency_authorization_source_id"] = ""
        with self.assertRaisesRegex(ValueError, "qualification or context"):
            runner.check(config("a"), site)

    def test_officer_exception_rejected(self):
        site = survey()
        site["officer_direction"] = "continue"
        with self.assertRaisesRegex(ValueError, "separate branch"):
            runner.check(config("a"), site)

    def test_controller_brakes_when_above_target(self):
        control = runner.speed_control(7, 14)
        self.assertEqual(control["throttle"], 0)
        self.assertGreater(control["brake"], 0)

    def test_controller_accelerates_when_below_target(self):
        control = runner.speed_control(14, 7)
        self.assertGreater(control["throttle"], 0)
        self.assertEqual(control["brake"], 0)

    def test_controller_rejects_invalid_speed(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            runner.speed_control(float("nan"), 7)


if __name__ == "__main__":
    unittest.main()
