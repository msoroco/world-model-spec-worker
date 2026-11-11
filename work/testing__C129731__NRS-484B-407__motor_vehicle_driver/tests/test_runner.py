import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
from runner import _other_control, validate_config
from camera_setup import SIZES, source_cameras


class RunnerTests(unittest.TestCase):
    def test_four_source_cameras_are_created_and_released(self):
        calls = []
        class Blueprint:
            def set_attribute(self, key, value):
                calls.append((key, value))
        class Sensor:
            def stop(self): calls.append("stop")
            def destroy(self): calls.append("destroy")
        world = NS(get_blueprint_library=lambda: NS(find=lambda name: Blueprint()),
                   spawn_actor=lambda blueprint, transform, **kw: calls.append(
                       (transform, bool(kw))) or Sensor())
        transforms = {name: name for name in SIZES}
        with source_cameras(world, NS(), transforms) as cameras:
            self.assertEqual(set(cameras), set(SIZES))
        self.assertEqual(calls.count("stop"), 4)
        self.assertEqual(calls.count("destroy"), 4)
        self.assertIn(("overview", False), calls)
        self.assertIn(("driver_reference", True), calls)
        self.assertIn(("image_size_x", "1920"), calls)
        self.assertIn(("image_size_y", "720"), calls)

    def test_exact_cpu_check_and_diagnostic_capture_rejection(self):
        config = json.loads((PACKAGE / "config.json").read_text())
        receipt = subprocess.run([sys.executable, str(PACKAGE / "runner.py"),
                                  "--config", str(PACKAGE / "config.json"), "--check"],
                                 check=True, capture_output=True, text=True)
        data = json.loads(receipt.stdout)
        self.assertEqual(data["frames"], 1100)
        self.assertEqual(len(data["camera_names"]), 4)
        self.assertFalse(data["carla_started"])
        with self.assertRaisesRegex(ValueError, "Diagnostic geometry"):
            validate_config(config, PACKAGE, diagnostic=False)
        bad = copy.deepcopy(config); bad["site_source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Site source missing or changed"):
            validate_config(bad, PACKAGE, diagnostic=True)
        wrong = copy.deepcopy(config); wrong["selected_case_id"] += "_wrong"
        with self.assertRaisesRegex(ValueError, "Exact C129731"):
            validate_config(wrong, PACKAGE, diagnostic=True)

    def test_both_approach_directions_apply_feedback_control(self):
        site = json.loads((PACKAGE / "diagnostic-site.json").read_text())
        carla = NS(VehicleControl=lambda: NS())
        for direction, lane in site["incoming_lanes"].items():
            far = lane["stations"][-1]["xyz_m"]
            yaw = 0 if direction == "approach_a" else 180
            commands = []
            actor = NS(get_transform=lambda: NS(location=NS(x=far[0], y=far[1]),
                                                rotation=NS(yaw=yaw)),
                       get_velocity=lambda: NS(x=0, y=0, z=0),
                       apply_control=lambda control: commands.append(control))
            index, record = _other_control(carla, actor, lane["stations"], 1)
            self.assertEqual(index, 1)
            self.assertFalse(record["near_site_brake"])
            self.assertGreater(commands[0].throttle, 0)


if __name__ == "__main__":
    unittest.main()
