import json
from pathlib import Path
import unittest

from engineering import parameters
from runner import check
from signal_control import left_signal_requested


class ExactBundleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=json.loads(Path("config.json").read_text())

    def test_exact_request_and_offline_preflight(self):
        report=check(self.config)
        self.assertFalse(report["physical_success_claimed"])
        self.assertFalse(report["native_imported"])
        self.assertGreater(report["route_points"],1600)

    def test_station_straddles_and_identity(self):
        p=parameters(self.config)
        station=p["signal_start_x_m"]
        self.assertFalse(left_signal_requested(station-.001,station))
        self.assertTrue(left_signal_requested(station,station))
        self.assertTrue(left_signal_requested(0,station))
        self.assertAlmostEqual(-station/.3048,p["signal_start_ft"],places=4)
        self.assertEqual(len(self.config["cameras"]),4)

    def test_negative_request_mutations(self):
        altered=json.loads(json.dumps(self.config))
        altered["native_request"]["map_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"OpenDRIVE"):
            check(altered)
        altered=json.loads(json.dumps(self.config))
        altered["native_request"]["signal_start_station_m"]+=1
        with self.assertRaisesRegex(ValueError,"Signal onset"):
            check(altered)


if __name__=="__main__":unittest.main()
