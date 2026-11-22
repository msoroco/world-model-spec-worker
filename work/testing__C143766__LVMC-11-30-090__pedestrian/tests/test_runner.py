import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import FRAMES, _trace, check_scene, run_native


class RunnerTests(unittest.TestCase):
    def test_all_three_exact_cpu_checks_do_not_start_carla(self):
        for band in ("roadway", "sidewalk", "shoulder"):
            with self.subTest(band=band):
                path = ROOT/"cases"/(band+"_walk")/"scene.json"
                command = [sys.executable, str(ROOT/"runner.py"), "--check",
                           "--scene", str(path), "--map", str(ROOT/"candidate-corridor.xodr")]
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                value = json.loads(result.stdout)
                self.assertEqual(value["case_id"], check_scene(path, ROOT/"candidate-corridor.xodr")["case_id"])
                self.assertEqual(value["planned_frames"], FRAMES)
                self.assertFalse(value["native_started"])

    def test_changed_map_and_unsafe_attempt_rejected_before_import(self):
        scene_path = ROOT/"cases/roadway_walk/scene.json"
        with tempfile.TemporaryDirectory() as temp:
            modified = Path(temp)/"map.xodr"
            modified.write_bytes((ROOT/"candidate-corridor.xodr").read_bytes()+b" ")
            with self.assertRaisesRegex(ValueError, "source bytes changed"):
                check_scene(scene_path, modified)
        scene = check_scene(scene_path, ROOT/"candidate-corridor.xodr")
        with self.assertRaisesRegex(ValueError, "under .runtime-work"):
            run_native(scene, scene_path, ROOT/"candidate-corridor.xodr",
                       ROOT, "127.0.0.1", 2000)

    def test_original_walker_trace_is_from_readback(self):
        class Vector:
            x = 1.1
            y = 0.0
            z = 0.0
        class Control:
            direction = Vector()
            speed = 1.2
            jump = False
        class Pose:
            location = type("Location", (), {"x": 2.0, "y": 1.5, "z": .2})()
            rotation = type("Rotation", (), {"yaw": 0.0})()
        class Actor:
            def get_transform(self): return Pose()
            def get_velocity(self): return Vector()
            def get_control(self): return Control()
        sample = {"frame": 15, "time_s": .75, "actor_id": 7}
        trace = _trace(Actor(), sample)
        self.assertEqual(trace["position_m"], [2.0, 1.5, .2])
        self.assertEqual(trace["speed_mps"], 1.1)
        self.assertEqual(trace["walker_control"]["requested_speed_mps"], 1.2)
