"""Independent comparison audit protocol fixtures, not physical evidence."""
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('c125714_comparison', ROOT / 'comparison_audit.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def records():
    result = []
    for case, value in zip(m.ORDER, (-2.85, -.05, 2.8)):
        result.append({'format': 'worker-c125714-selected-diagnostic-v1',
                       'assignment_id': m.BASE, 'case_id': case,
                       'measurement': 'intersection_entry_time_difference_s',
                       'measured_value_s': value, 'legal_verdict_claimed': False,
                       'crossing_id': 'crossing A', 'roadway_id': 'roadway A',
                       'ego_side': 'left', 'other_side': 'right',
                       'approach_relation': 'crossing',
                       'official_device_controls_intersection': False,
                       'other_left_turn_intent': False,
                       'subsection_4_context_reviewed': True,
                       'original_frame_count': 1100,
                       'source_sha256': {'road.xodr': 'fixture map hash',
                                         'site-context.json': case,
                                         'ego-body-history.jsonl': case + ' ego',
                                         'other-body-history.jsonl': case + ' other'}})
    return result


class ComparisonTest(unittest.TestCase):
    def test_measured_order_and_fixed_context(self):
        d = records()
        self.assertEqual(m.audit(d)['measured_entry_differences_s'], [-2.85, -.05, 2.8])
        bad = copy.deepcopy(d); bad[1]['roadway_id'] = 'other roadway'
        with self.assertRaisesRegex(ValueError, 'fixed comparison condition'):
            m.audit(bad)
        bad = copy.deepcopy(d); bad[2]['source_sha256']['road.xodr'] = 'other map'
        with self.assertRaisesRegex(ValueError, 'fixed original source'):
            m.audit(bad)

    def test_declared_difference_must_be_real_and_exact(self):
        bad = records(); bad[1]['measured_value_s'] = -3
        with self.assertRaisesRegex(ValueError, 'ordered actual timing'):
            m.audit(bad)
        bad = records(); bad[1]['case_id'] = m.BASE + '__extra'
        with self.assertRaisesRegex(ValueError, 'ordered exact timing'):
            m.audit(bad)


if __name__ == '__main__':
    unittest.main()
