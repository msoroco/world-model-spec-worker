import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('sweep_probe', ROOT / 'sweep_probe.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
envelope_spec = importlib.util.spec_from_file_location('sweep_controller_envelope', ROOT / 'sweep_controller_envelope.py')
envelope = importlib.util.module_from_spec(envelope_spec)
envelope_spec.loader.exec_module(envelope)
dynamics_spec = importlib.util.spec_from_file_location('sweep_dynamics_probe', ROOT / 'sweep_dynamics_probe.py')
dynamics = importlib.util.module_from_spec(dynamics_spec)
dynamics_spec.loader.exec_module(dynamics)


class SweepProbeTests(unittest.TestCase):
    def test_gap_grid_cpu_trajectory_keeps_assumed_bodies_separate(self):
        config = json.loads((ROOT / 'config.json').read_text())
        result = dynamics.probe(config)
        self.assertEqual(result['frames'], 900)
        self.assertFalse(result['physical_feasibility_proven'])
        self.assertFalse(result['legal_threshold_asserted'])
        self.assertEqual([row['requested_engineering_gap_m'] for row in result['points']],
                         [7.0, 8.5, 10.0])
        self.assertTrue(all(row['min_assumed_body_gap_m'] > 0 for row in result['points']))
        means = [row['mean_assumed_body_gap_m'] for row in result['points']]
        self.assertLess(means[0], means[1])
        self.assertLess(means[1], means[2])
        changed = dict(config)
        changed['ego_target_speed_mps'] = 5.0
        with self.assertRaisesRegex(ValueError, 'Reviewed base'):
            dynamics.probe(changed)

    def test_grid_changes_controller_feedback_without_claiming_physical_feasibility(self):
        result = module.probe(json.loads((ROOT / 'config.json').read_text()))
        self.assertEqual([point['requested_engineering_gap_m'] for point in result['points']],
                         [7.0, 8.5, 10.0])
        self.assertFalse(result['physical_feasibility_proven'])
        self.assertFalse(result['legal_threshold_asserted'])
        self.assertEqual([point['target_center_spacing_m'] for point in result['points']],
                         [11.0, 12.5, 14.0])

    def test_unreviewed_base_config_is_rejected(self):
        config = json.loads((ROOT / 'config.json').read_text())
        config['requested_engineering_gap_m'] = 9.0
        with self.assertRaisesRegex(ValueError, 'reviewed base'):
            module.probe(config)

    def test_gap_grid_loses_command_separation_at_larger_spacing(self):
        result = envelope.probe(json.loads((ROOT / 'config.json').read_text()))
        self.assertFalse(result['physical_feasibility_proven'])
        self.assertEqual(result['state_count'], 42)
        rows = {(row['phase'], row['lead_speed_mps'], row['center_spacing_m']): row
                for row in result['states']}
        self.assertTrue(rows['before_lane_change', 3.5, 13.0]['all_three_distinct'])
        self.assertEqual(rows['before_lane_change', 3.5, 16.0]['requested_speed_mps_by_gap'],
                         [4.0, 4.0, 4.0])
        self.assertFalse(rows['after_lane_change', 3.5, 13.0]['all_three_distinct'])
