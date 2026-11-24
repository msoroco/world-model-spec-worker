import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from device_timeline import observe_timeline


def timeline(modes, in_highway):
    facts = []
    for i, (mode, present) in enumerate(zip(modes, in_highway)):
        facts.append({'frame': 100 + i, 'other_device_mode': mode,
                      'other_device_countdown': 3 - i if mode == 'flashing_countdown' else None,
                      'in_highway': present, 'in_crosswalk': present})
    return {'frame_count': len(facts), 'measurements': facts}


class DeviceTimelineTests(unittest.TestCase):
    def test_flashing_countdown_entry_and_clearance_before_zero(self):
        measured = timeline(['walk', 'flashing_countdown', 'flashing_countdown',
                             'flashing_countdown', 'steady'],
                            [False, True, True, False, False])
        result = observe_timeline(measured)
        self.assertEqual(result['entry_device_mode'], 'flashing_countdown')
        self.assertEqual(result['first_countdown_zero_frame'], 103)
        self.assertFalse(result['cleared_before_countdown_zero_observed'])
        self.assertTrue(result['cleared_before_steady_observed'])
        self.assertIsNone(result['entered_lawfully'])
        self.assertIsNone(result['legal_verdict'])

    def test_no_entry_and_walk_to_steady_continuation_facts(self):
        measured = timeline(['walk', 'steady', 'steady'], [False, False, False])
        self.assertIsNone(observe_timeline(measured)['entry_frame'])
        measured = timeline(['walk', 'walk', 'steady', 'steady'],
                            [False, True, True, False])
        result = observe_timeline(measured)
        self.assertEqual(result['entry_device_mode'], 'walk')
        self.assertFalse(result['cleared_before_steady_observed'])

    def test_rejects_gap_invalid_countdown_and_reentry(self):
        measured = timeline(['walk', 'walk', 'steady'], [False, True, False])
        measured['measurements'][2]['frame'] += 1
        with self.assertRaisesRegex(ValueError, 'frame gap'):
            observe_timeline(measured)
        measured = timeline(['walk', 'flashing_countdown', 'steady'],
                            [False, True, False])
        measured['measurements'][1]['other_device_countdown'] = None
        with self.assertRaisesRegex(ValueError, 'countdown invalid'):
            observe_timeline(measured)
        measured = timeline(['walk', 'walk', 'steady', 'steady'],
                            [False, True, False, True])
        with self.assertRaisesRegex(ValueError, 'multiple observed'):
            observe_timeline(measured)


if __name__ == '__main__':
    unittest.main()
