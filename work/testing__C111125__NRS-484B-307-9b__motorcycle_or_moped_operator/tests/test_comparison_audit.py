import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('comparison_audit', Path(__file__).resolve().parents[1] / 'comparison_audit.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ComparisonTest(unittest.TestCase):
    def record(self, suffix):
        row = {'case_suffix': suffix, 'initial_composite_phase': True,
               'entry_frame': 200, 'stopped_frame': 10, 'full_cycles_after_stop': 2,
               'unchanged_signal_cause': 'failed_detection', 'other_user_region': 'clear',
               'legal_permission_verdict': None, 'right_of_way_verdict': None,
               'original_sources': [{'path': 'sealed.json', 'sha256': 'a'*64}]}
        for key in ('map_sha256', 'route_sha256', 'signal_sha256', 'stop_sha256',
                    'crosswalk_sha256', 'camera_profile_sha256'):
            row[key] = 'a'*64
        row.update(duration_frames=900, official_head_id='head-17',
                   ego_approach_id='approach-west', actor_type_id='vehicle.motorcycle')
        return row

    def test_each_declared_difference_and_fixed_conditions(self):
        changes = {'one_cycle_entry': ('full_cycles_after_stop', 1),
                   'rolling_entry': ('stopped_frame', None),
                   'no_causal_record': ('unchanged_signal_cause', 'not_established'),
                   'pedestrian_crosswalk': ('other_user_region', 'adjacent_crosswalk'),
                   'lawful_traffic': ('other_user_region', 'intersection')}
        for name, (_, suffix, _, _) in audit.PAIRS.items():
            with self.subTest(name=name):
                left, right = self.record('two_cycles_clear'), self.record(suffix)
                key, value = changes[suffix]
                right[key] = value
                self.assertEqual(audit.audit_pair(name, left, right)['comparison_id'], name)
                right['map_sha256'] = 'b'*64
                with self.assertRaisesRegex(audit.ComparisonError, 'fixed condition'):
                    audit.audit_pair(name, left, right)

    def test_rejects_missing_difference_and_unsupported_verdict(self):
        left, right = self.record('two_cycles_clear'), self.record('one_cycle_entry')
        with self.assertRaisesRegex(audit.ComparisonError, 'difference not measured'):
            audit.audit_pair('complete_cycle_count', left, right)
        right['full_cycles_after_stop'] = 1
        right['legal_permission_verdict'] = True
        with self.assertRaisesRegex(audit.ComparisonError, 'unsupported legal'):
            audit.audit_pair('complete_cycle_count', left, right)


if __name__ == '__main__': unittest.main()
