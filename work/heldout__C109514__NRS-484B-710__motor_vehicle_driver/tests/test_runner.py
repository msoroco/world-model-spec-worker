import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

folder = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(folder))
spec = importlib.util.spec_from_file_location("fire_runner", folder / "runner.py")
runner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = runner
spec.loader.exec_module(runner)


class RunnerTests(unittest.TestCase):
    def test_static_check_has_no_native_import(self):
        completed = subprocess.run([sys.executable, str(folder / "runner.py"), "--check"],
                                   capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_static_check_rejects_wrong_materialized_case(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "config.json").write_text(json.dumps({"selected_case_id": "wrong"}))
            completed = subprocess.run([sys.executable, str(folder / "runner.py"), "--check"],
                                       cwd=temp, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("traveling 500 ft exact case", completed.stderr)

    def test_selected_case_and_sourced_context_required(self):
        config = {"selected_case_id": "heldout__C109514__NRS-484B-710__motor_vehicle_driver__traveling_follow_500ft",
                  "law_id": "NRS-484B-710", "cell_id": "C109514",
                  "actor": "motor_vehicle_driver", "fire_branch": "traveling_follow",
                  "target_distance_ft": 500,
                  "fire_context": {"alarm_response_source": "authored dispatch fixture",
                                   "apparatus_answered_alarm": True,
                                   "subject_authorized_emergency": False,
                                   "subject_official_business": False},
                  "case": {"recording_description": {"purpose": "source measurement"}}}
        self.assertTrue(runner.check_config(config))
        config["target_distance_ft"] = 499
        with self.assertRaisesRegex(ValueError, "branch or construction"):
            runner.check_config(config)

    def test_missing_siren_readback_stays_unknown(self):
        class Lights:
            Special1 = 1
            Special2 = 2
        apparatus = SimpleNamespace(get_light_state=lambda: 1)
        self.assertEqual(runner._device_readbacks(apparatus,
                         SimpleNamespace(VehicleLightState=Lights)), (True, None))

    def test_ego_steers_along_intersection_continuation(self):
        chain = [SimpleNamespace(transform=SimpleNamespace(
            location=SimpleNamespace(x=x, y=y)))
            for x, y in ((0, 0), (5, 0), (10, 1), (15, 2))]
        ego = SimpleNamespace(get_transform=lambda: SimpleNamespace(
            location=SimpleNamespace(x=5, y=0),
            rotation=SimpleNamespace(yaw=0)))
        self.assertGreater(runner._ego_steer(chain, ego), 0)
        divergent = SimpleNamespace(get_transform=lambda: SimpleNamespace(
            location=SimpleNamespace(x=5, y=0),
            rotation=SimpleNamespace(yaw=180)))
        with self.assertRaisesRegex(ValueError, "diverged"):
            runner._ego_steer(chain, divergent)


if __name__ == "__main__":
    unittest.main()
