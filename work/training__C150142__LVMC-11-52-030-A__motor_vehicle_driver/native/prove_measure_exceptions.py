"""CPU probes for source-derived exception observations and rejection paths."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_exceptions import measure


def context(service='tour_bus', sign=True, mailbox=False):
    return {'source_kind': 'synthetic_native_sample',
            'red_curb': {'paint_color': 'red', 'start_x_m': 30,
                         'end_x_m': 50, 'curb_y_m': -7},
            'sign_readback': {'present': sign,
                              'center_x_m': 40 if sign else None,
                              'displayed_classes': ['tour_bus', 'shuttle_bus', 'limo']
                              if sign else []},
            'vehicle_readback': {'native_blueprint': 'vehicle.test.bus',
                                 'declared_service_class': service},
            'mailbox_readback': {'present': mailbox,
                                 'center_x_m': 40, 'center_y_m': -7.4}}


def frames(count, x=40, gap=None):
    for i in range(count):
        t = i / 20 if gap is None or i < gap else (i + 1) / 20
        yield {'source_kind': 'synthetic_native_sample', 'frame': i,
               'time_s': t,
               'ego_body_native_xy_m': [[x - 1, -7], [x + 1, -7],
                                        [x + 1, -6], [x - 1, -6]],
               'velocity_native_xyz_mps': [0, 0, 0]}


class ExceptionSourceProof(unittest.TestCase):
    def test_signed_passenger_loading_boundary(self):
        observed = {}
        for label, count in [('below', 36000), ('at', 36001), ('above', 36002)]:
            result = measure(frames(count), context(),
                             [{'source_kind': 'synthetic_native_sample',
                               'name': 'passenger_loading', 'start_time_s': 1,
                               'end_time_s': 2, 'source': 'recorded_actor_event'}])
            self.assertEqual(result['duration_relative_to_30_minutes'], label)
            self.assertEqual(result['frames'], count)
            self.assertIn('tour_bus', result['displayed_sign_classes'])
            self.assertTrue(result['sign_over_red_extent'])
            self.assertIsNone(result['statutory_exception_applies'])
            observed[label] = result['red_curb_stationary_duration_s']
        self.assertEqual(observed, {'below': 1799.95, 'at': 1800.0,
                                    'above': 1800.05})

    def test_distinct_exception_context_is_reported(self):
        rtc = context('rtc_bus')
        rtc['sign_readback']['displayed_classes'] = ['rtc_bus']
        armored = context('armored_car', sign=False)
        mail = context('ordinary', sign=False, mailbox=True)
        for setting, expected in [(rtc, 'rtc_bus'), (armored, 'armored_car'),
                                  (mail, 'ordinary')]:
            result = measure(frames(3), setting, [])
            self.assertEqual(result['declared_service_class'], expected)
            self.assertIsNone(result['necessary_business_established'])
            self.assertIsNone(result['expeditious_mail_deposit_established'])
        self.assertEqual(measure(frames(3), mail, [])['mailbox_curb_distance_m'], .4)

    def test_rejects_missing_sources_and_incomplete_duration(self):
        bad = context()
        del bad['sign_readback']
        with self.assertRaisesRegex(ValueError, 'sign readback'):
            measure(frames(3), bad, [])
        bad = context()
        del bad['sign_readback']['center_x_m']
        with self.assertRaisesRegex(ValueError, 'sign x'):
            measure(frames(3), bad, [])
        bad = context(sign=False)
        bad['sign_readback']['displayed_classes'] = ['rtc_bus']
        with self.assertRaisesRegex(ValueError, 'sign readback'):
            measure(frames(3), bad, [])
        with self.assertRaisesRegex(ValueError, 'Incomplete 20 Hz'):
            measure(frames(3, gap=2), context(), [])
        with self.assertRaisesRegex(ValueError, 'Activity outside'):
            measure(frames(3), context(),
                    [{'source_kind': 'synthetic_native_sample',
                      'name': 'mail_deposit', 'start_time_s': 1,
                      'end_time_s': 2, 'source': 'recorded_actor_event'}])
        with self.assertRaisesRegex(ValueError, 'Invalid activity source'):
            measure(frames(3), context(),
                    [{'source_kind': 'synthetic_native_sample',
                      'name': 'mail_deposit', 'start_time_s': 0,
                      'end_time_s': .05}])
        rows = list(frames(3)); rows[1]['source_kind'] = 'native'
        with self.assertRaisesRegex(ValueError, 'Mixed frame provenance'):
            measure(rows, context(), [])
        rows = list(frames(3)); rows[1]['velocity_native_xyz_mps'] = [1, 0, 0]
        with self.assertRaisesRegex(ValueError, 'interval interrupted'):
            measure(rows, context(), [])


if __name__ == '__main__':
    unittest.main()
