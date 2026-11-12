"""Check the new timing-sweep capture branch without importing CARLA."""
import json
import unittest
from pathlib import Path

from traffic_timing_sweep import TrafficLaunch
from traffic_timing_sweep_runner import check

HERE = Path(__file__).resolve().parent.parent


class TrafficTimingSweepTest(unittest.TestCase):
    def test_exact_candidate_configs_and_authored_geometry(self):
        manifest = json.loads((HERE / "draft-traffic-branch-execution-manifest.json").read_text())
        entry = next(case for case in manifest["cases"]
                     if case["case_id"].endswith("__traffic_yield_wait"))
        for candidate in (entry, *entry["candidates"]):
            construction = json.loads((HERE / candidate["construction"]).read_text())
            config = json.loads(next(file["content"] for file in construction["files"]
                                     if file["path"] == "config.json"))
            config.update(case_id="C110919-right-of-way-0000",
                          sweep_id="C110919-right-of-way", traffic_launch_frame=30)
            result = check(config)
            self.assertEqual(result["camera_count"], 4)
            self.assertEqual(result["traffic_launch_frame"], 30)
            self.assertFalse(result["native_imported"])

    def test_launch_boundary_and_invalid_scope(self):
        launch = TrafficLaunch(30)
        self.assertEqual(launch.command(29)["brake"], 1)
        self.assertEqual(launch.command(30)["throttle"], .25)
        self.assertEqual(launch.command(260)["throttle"], .25)
        self.assertTrue(launch.command(261)["hand_brake"])
        for invalid in (-1, 260, 480, 30.5, None):
            with self.assertRaises(ValueError):
                TrafficLaunch(invalid)


if __name__ == "__main__":
    unittest.main()
