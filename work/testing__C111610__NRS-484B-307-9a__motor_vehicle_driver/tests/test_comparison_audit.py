import importlib.util
import unittest
from pathlib import Path


spec = importlib.util.spec_from_file_location('comparison_c111610', Path(__file__).resolve().parents[1] / 'comparison_audit.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def row(suffix):
    result = {key: key for key in ('map_sha256', 'ego_signal_sha256', 'opposing_signal_sha256',
             'crosswalk_sha256', 'camera_profile_sha256', 'arrow_direction',
             'pedestrian_permission_sha256')}
    result.update(case_suffix=suffix, duration_frames=600, original_signal_frames=600,
                  first_ego_entry={'frame': 300}, actual_route='arrow_turn',
                  pedestrian_lawfully_inside_at_approach=suffix in ('yield_pedestrian', 'continue_pedestrian'),
                  held_until_clear=suffix == 'yield_pedestrian')
    result['other_traffic_lawfully_in_intersection_at_approach'] = suffix in ('yield_other_traffic', 'continue_other_traffic')
    result['held_until_clear'] = suffix in ('yield_pedestrian', 'yield_other_traffic')
    if suffix == 'wrong_movement':
        result['actual_route'] = 'straight'
    return result


class AuditTests(unittest.TestCase):
    def test_all_pairs_and_negative_conditions(self):
        for name, (left, right) in mod.PAIRS.items():
            a, b = row(left), row(right)
            self.assertFalse(mod.audit_pair(name, a, b)['physical_acceptance'])
            b['map_sha256'] = 'different'
            with self.assertRaisesRegex(mod.ComparisonError, 'fixed source differs'):
                mod.audit_pair(name, a, b)

    def test_missing_measurement_and_unrealized_difference(self):
        a, b = row('yield_pedestrian'), row('continue_pedestrian')
        b['first_ego_entry'] = None
        with self.assertRaisesRegex(mod.ComparisonError, 'entry not measured'):
            mod.audit_pair('pedestrian_yield', a, b)
        b['first_ego_entry'] = {'frame': 300}
        b['held_until_clear'] = True
        with self.assertRaisesRegex(mod.ComparisonError, 'yield difference'):
            mod.audit_pair('pedestrian_yield', a, b)


if __name__ == '__main__':
    unittest.main()
