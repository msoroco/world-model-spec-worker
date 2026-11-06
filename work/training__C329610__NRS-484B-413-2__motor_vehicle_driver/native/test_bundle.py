import json
from pathlib import Path
import unittest

from engineering import parameters
from runner import check
from signal_control import left_signal_requested


class ExactBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(Path("config.json").read_text())

    def test_exact_request_and_native_preflight(self):
        report = check(self.config)
        self.assertFalse(report["physical_success_claimed"])
        self.assertFalse(report["native_imported"])
        p = parameters(self.config)
        self.assertEqual(p["target_signal_distance_ft"], self.config["native_request"]["target_signal_distance_ft"])
        self.assertEqual(p["start_x_m"], p["authored_route_xy_m"][0][0])
        self.assertGreater(len(p["native_route_xy_m"]), 1000)

    def test_signal_station_straddling_and_invalid_pose(self):
        station = self.config["native_request"]["signal_onset_x_m"]
        self.assertFalse(left_signal_requested(station - .001, station))
        self.assertTrue(left_signal_requested(station, station))
        self.assertTrue(left_signal_requested(-7, station))
        with self.assertRaises(ValueError):
            left_signal_requested(float("nan"), station)

    def test_law_preserving_capture_contract(self):
        request = self.config["native_request"]
        self.assertEqual((request["rate_hz"], request["duration_s"]), (20, 40))
        self.assertEqual((request["law_id"], request["cell_id"], request["actor"]),
                         ("NRS-484B-413-2", "C329610", "motor_vehicle_driver"))
        self.assertLess(abs((-7 - request["signal_onset_x_m"]) / .3048 -
                            request["target_signal_distance_ft"]), 1e-8)


if __name__ == "__main__":
    unittest.main()
