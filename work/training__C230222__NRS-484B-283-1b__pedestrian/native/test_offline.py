import json
from pathlib import Path
import tempfile
import unittest

from curb import measure
from engineering import candidate
from geometry import check as check_geometry
from runner import check as check_runner
from vehicle_policy import BrakingPolicy, cpu_probe

HERE = Path(__file__).resolve().parent.parent


class CurbOffline(unittest.TestCase):
    def test_exact_runner_preflight(self):
        config = json.loads((HERE / 'config.json').read_text())
        result = check_runner(config)
        self.assertEqual(result['frames'], 240)
        self.assertEqual(len(result['cameras']), 4)
        self.assertFalse(result['native_imported'])
        self.assertFalse(result['impossibility_to_yield_proven'])

    def test_authored_curb_and_vehicle_path(self):
        geometry = check_geometry(HERE / 'road.xodr')
        self.assertEqual((geometry['curb_edge_x_m'], geometry['vehicle_lane_center_x_m']), (-3.5, -1.75))
        self.assertFalse(geometry['legal_road_and_safety_place_status_verified'])

    def test_controlled_departure_request(self):
        config = json.loads((HERE / 'config.json').read_text())
        plan = candidate(config['case_suffix'], config['candidate_id'])
        self.assertEqual(plan['engineering']['pedestrian_departure_s'],
                         .5 if config['case_suffix'] == 'probe_1' else 3.5)
        self.assertEqual(plan['engineering']['vehicle_target_speed_mps'], 4)

    def test_common_driver_response_policy(self):
        early, late = cpu_probe(.5), cpu_probe(3.5)
        self.assertEqual(early['brake_command_onset_s'], 1.3)
        self.assertEqual(late['brake_command_onset_s'], 4.3)
        self.assertAlmostEqual(early['brake_command_onset_s']-early['departure_observed_s'], .8)
        self.assertAlmostEqual(late['brake_command_onset_s']-late['departure_observed_s'], .8)
        self.assertFalse(early['physical_braking_measured'])
        self.assertFalse(late['physical_braking_measured'])
        policy = BrakingPolicy()
        self.assertEqual(policy.command(0), 'hold_approach_speed')
        policy.observe(.5, 3)
        self.assertEqual(policy.command(1.25), 'hold_approach_speed')
        self.assertEqual(policy.command(1.3), 'full_brake')

    def test_missing_measurement_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Missing required source: curb-samples.jsonl'):
                measure(Path(folder) / 'curb-samples.jsonl', Path(folder) / 'curb-context.json')


if __name__ == '__main__':
    unittest.main()
