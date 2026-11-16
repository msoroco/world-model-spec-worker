"""Positive and negative source probes for the tour-bus passenger actor."""
import unittest
from passenger_activity import derive


def rows(moving=True, count=80):
    ego = []
    walker = []
    for i in range(count):
        y = -10 + min(max(i - 20, 0), 40) * .05 if moving else -10
        ego.append({'frame': i, 'time_s': (i + 1) / 20,
                    'source_kind': 'synthetic_native_sample',
                    'ego_center_native_xy_m': [40, -6.8]})
        walker.append({'frame': i, 'source_kind': 'synthetic_native_sample',
                       'blueprint': 'walker.pedestrian.0001',
                       'center_native_xy_m': [40, y]})
    return walker, ego


class PassengerActivityProof(unittest.TestCase):
    def test_measured_approach_and_rejections(self):
        walker, ego = rows()
        event = derive(walker, ego, 20)[0]
        self.assertEqual(event['name'], 'passenger_loading')
        self.assertGreater(event['end_time_s'], event['start_time_s'])
        self.assertIn('boarding unverified', event['source'])
        with self.assertRaisesRegex(ValueError, 'No measured passenger approach'):
            derive(*rows(moving=False), 20)
        walker[30]['source_kind'] = 'original_native'
        with self.assertRaisesRegex(ValueError, 'provenance'):
            derive(walker, ego, 20)


if __name__ == '__main__':
    unittest.main()
