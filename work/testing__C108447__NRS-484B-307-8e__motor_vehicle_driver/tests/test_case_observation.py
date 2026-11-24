import importlib.util
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
for name in ('property_route', 'case_observation'):
    spec = importlib.util.spec_from_file_location(name, BASE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
route = sys.modules['property_route']
case_audit = sys.modules['case_observation']
PREFIX = 'testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__'


def source_case(suffix):
    packet = {'source': {'kind': 'original_native_map_and_property_authority',
                         'path': '/source', 'sha256': 'a' * 64},
              'coordinate_frame': 'native-xy', 'intersecting_street_id': 'cross',
              'properties': [{'id': 'lot', 'status': 'private', 'authority': 'source',
                              'polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]]}]}
    samples = [{'frame': frame, 'x': x, 'y': 5} for frame, x in [(1, -2), (2, 5), (3, 12), (4, 14)]]
    trace = {'coordinate_frame': 'native-xy', 'actor_class': 'vehicle',
             'actor_source': {'source': 'Native registry'}, 'ego': samples,
             'approach_signal_history': [], 'destination_signal_history': [],
             'destination_street_id': 'cross', 'destination_entry_frame': 3,
             'purpose': {'source': 'separate intent declaration', 'value': 'avoid_red'}}
    for frame in range(1, 5):
        trace['approach_signal_history'].append({'frame': frame, 'device_id': 'A',
            'source': 'Native light A', 'facing_ego': True, 'state': 'red_alone'})
        trace['destination_signal_history'].append({'frame': frame, 'device_id': 'B',
            'source': 'Native light B', 'facing_ego': False, 'state': 'green'})
    trace['approach_signal'] = trace['approach_signal_history'][0]
    trace['destination_signal'] = trace['destination_signal_history'][2]
    if suffix == 'public_bypass':
        packet['properties'][0]['status'] = 'public'
    elif suffix == 'ordinary_crossing':
        for sample in samples:
            sample['y'] = -2
    elif suffix == 'no_approach_red':
        for row in trace['approach_signal_history']:
            row['state'] = 'green'
    elif suffix == 'destination_red':
        for row in trace['destination_signal_history']:
            row['state'] = 'red_alone'
    elif suffix == 'other_purpose':
        trace['purpose']['value'] = 'other'
    case = {'case_id': PREFIX + suffix}
    return packet, trace, case


class CaseObservationTests(unittest.TestCase):
    def test_all_six_source_shaped_case_contrasts(self):
        for suffix in case_audit.SUFFIXES:
            with self.subTest(suffix=suffix):
                packet, trace, case = source_case(suffix)
                observed = route.analyze(packet, trace, case)
                audited = case_audit.audit_case(observed, trace, case)
                self.assertEqual(audited['planned_case'], suffix)
                self.assertFalse(audited['physical_acceptance_claimed'])

    def test_wrong_deliberate_difference_rejected(self):
        packet, trace, case = source_case('private_bypass')
        observed = route.analyze(packet, trace, case)
        case['case_id'] = PREFIX + 'public_bypass'
        observed['case_id'] = case['case_id']
        with self.assertRaisesRegex(ValueError, 'property traversal differs'):
            case_audit.audit_case(observed, trace, case)
        case['case_id'] = PREFIX + 'no_approach_red'
        observed['case_id'] = case['case_id']
        with self.assertRaisesRegex(ValueError, 'non-red approach'):
            case_audit.audit_case(observed, trace, case)
        case['case_id'] = PREFIX + 'destination_red'
        observed['case_id'] = case['case_id']
        with self.assertRaisesRegex(ValueError, 'red destination'):
            case_audit.audit_case(observed, trace, case)
        case['case_id'] = PREFIX + 'other_purpose'
        observed['case_id'] = case['case_id']
        with self.assertRaisesRegex(ValueError, 'purpose differs'):
            case_audit.audit_case(observed, trace, case)

    def test_foreign_case_with_same_suffix_rejected(self):
        packet, trace, case = source_case('private_bypass')
        observed = route.analyze(packet, trace, case)
        case['case_id'] = 'foreign_assignment__private_bypass'
        observed['case_id'] = case['case_id']
        with self.assertRaisesRegex(ValueError, 'planned exact case suffix'):
            case_audit.audit_case(observed, trace, case)

    def test_post_entry_phase_change_does_not_rewrite_movement(self):
        packet, trace, case = source_case('private_bypass')
        trace['approach_signal_history'][-1]['state'] = 'green'
        observed = route.analyze(packet, trace, case)
        self.assertTrue(observed['approach_red_alone_facing_ego'])
        self.assertEqual(case_audit.audit_case(observed, trace, case)['approach_state_window'], [1, 3])

    def test_pre_entry_phase_change_rejected(self):
        packet, trace, case = source_case('private_bypass')
        trace['approach_signal_history'][1]['state'] = 'green'
        observed = route.analyze(packet, trace, case)
        with self.assertRaisesRegex(ValueError, 'steady red alone approach'):
            case_audit.audit_case(observed, trace, case)


if __name__ == '__main__':
    unittest.main()
