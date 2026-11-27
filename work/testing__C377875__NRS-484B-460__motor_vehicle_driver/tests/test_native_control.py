import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("angle_native", ROOT / "angle_native.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeControlTests(unittest.TestCase):
    def test_steers_toward_requested_target_and_brakes(self):
        command, phase, reached = module.control([0, 0], 0, 1.0, [10, 5], 45, False, 0, "park", 600)
        self.assertEqual(phase, "approach")
        self.assertGreater(command["steer"], 0)
        self.assertFalse(reached)
        brake, phase, reached = module.control([8.7, 5], 45, 0.5, [10, 5], 45, False, 0, "park", 600)
        self.assertEqual(phase, "approach")
        self.assertGreater(brake["brake"], 0)

    def test_hold_and_depart_are_separate_original_states(self):
        command, phase, reached = module.control([10, 5], 45, 0, [10, 5], 45, True, 0, "stand", 600)
        self.assertEqual(phase, "hold")
        self.assertEqual(command["brake"], 1)
        command, phase, reached = module.control([10, 5], 45, 0, [10, 5], 45, True, 160, "stand", 600)
        self.assertEqual(phase, "depart")
        self.assertGreater(command["throttle"], 0)
        command, phase, reached = module.control([10, 5], 45, 0, [10, 5], 45, True, 599, "park", 600)
        self.assertEqual(phase, "hold")
        self.assertTrue(command["hand_brake"])

    def test_runner_check_is_lazy_and_original_source_is_required_for_capture(self):
        check = subprocess.run([sys.executable, str(ROOT / "runner.py"), "--check"],
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertTrue(json.loads(check.stdout)["reviewed_original_site_required_for_native"])
        capture = subprocess.run([sys.executable, str(ROOT / "runner.py"), "--output-dir", ".runtime-work/no-run"],
                                 capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertNotEqual(capture.returncode, 0)
        self.assertIn("reviewed source directory required", capture.stderr)


if __name__ == "__main__":
    unittest.main()
