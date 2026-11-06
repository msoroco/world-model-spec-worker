"""Check distinct unselected plans and measured-trigger rejection semantics."""
import unittest

from engineering import CANDIDATES, TRIGGERS, ego_velocity_request, parameters, trigger


class EngineeringTests(unittest.TestCase):
    def test_distinct_policies_and_fixed_comparison(self):
        for case in ('condition_a', 'condition_b'):
            plans = [parameters(case, candidate) for candidate in CANDIDATES]
            self.assertEqual(len({(p['ego_start_x_m'], p['controller_lookahead_m'],
                                   p['camera_horizontal_fov_deg']) for p in plans}), 4)
            self.assertEqual({p['law_id'] for p in plans}, {'NRS-484B-127-1'})
            self.assertEqual({p['target_bumper_gap_m'] for p in plans},
                             {10.0 if case == 'condition_a' else 25.0})

    def test_original_source_and_thresholds(self):
        for candidate, spec in TRIGGERS.items():
            metric = spec['metric']
            source = spec['source']
            with self.assertRaises(ValueError):
                trigger(candidate, {'source': 'synthetic expectation', metric: 0})
            self.assertFalse(trigger(candidate, {'source': source, metric: spec['threshold']}))
            measured = spec['threshold']-.01 if candidate != 'fallback2' else spec['threshold']+.01
            self.assertTrue(trigger(candidate, {'source': source, metric: measured}))

    def test_lookahead_changes_actual_request(self):
        primary = parameters('condition_a', 'primary')
        fallback = parameters('condition_a', 'fallback2')
        self.assertEqual(ego_velocity_request(primary, 10), 8)
        self.assertGreater(ego_velocity_request(fallback, 12), ego_velocity_request(primary, 12))
        self.assertLess(ego_velocity_request(fallback, 8), ego_velocity_request(primary, 8))
        with self.assertRaises(ValueError):
            ego_velocity_request(primary, 0)


if __name__ == '__main__':
    unittest.main()
