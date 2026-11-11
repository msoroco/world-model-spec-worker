import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'headlamp_follow_measurement.py'
SPEC = importlib.util.spec_from_file_location('headlamp_follow_measurement', MODULE)
measurement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measurement)


def square(x):
    return [[x - .5, -.5], [x + .5, -.5], [x + .5, .5], [x - .5, .5]]


def row(frame, gap_ft, lead_heading=(1, 0)):
    return {'frame': frame, 'time_s': frame * .05, 'ego_id': 'ego-1',
            'lead_id': 'lead-2', 'ego_corners_xy': square(0),
            'lead_corners_xy': square(gap_ft * .3048 + 1),
            'ego_heading_xy': [1, 0], 'lead_heading_xy': list(lead_heading)}


class HeadlampFollowTests(unittest.TestCase):
    def measure(self, footprint_rows, lamps, context=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            footprint = root / 'following_footprints.jsonl'
            lamp = root / 'headlamp_readbacks.jsonl'
            premise = root / 'lighting_context.json'
            footprint.write_text(''.join(json.dumps(item) + '\n' for item in footprint_rows))
            lamp.write_text(''.join(json.dumps(item) + '\n' for item in lamps))
            premise.write_text(json.dumps(context or {'lighting_time_applies': True,
                                                      'time_source': 'original clock and cited NRS 484D.100(1) premise'}))
            return measurement.measure(footprint, lamp, premise)

    def test_299_300_301_foot_measurement_and_readback(self):
        rows = [row(i, gap) for i, gap in enumerate((299, 300, 301))]
        lamps = [{'frame': i, 'time_s': i * .05,
                  'uppermost_distribution': value,
                  'low_beam_readback': not value} for i, value in enumerate((False, True, True))]
        report = self.measure(rows, lamps)
        self.assertEqual([item['below_300ft'] for item in report['observations']], [True, False, False])
        self.assertEqual([item['at_300ft'] for item in report['observations']], [False, True, False])
        self.assertAlmostEqual(report['minimum_surface_gap_ft'], 299)
        self.assertIsNone(report['legal_headlamp_judgment'])

    def test_opposite_direction_is_not_following(self):
        rows = [row(i, 299, (-1, 0)) for i in range(2)]
        lamps = [{'frame': i, 'time_s': i * .05, 'uppermost_distribution': False,
                  'low_beam_readback': True} for i in range(2)]
        report = self.measure(rows, lamps)
        self.assertFalse(report['observations'][0]['following_geometry'])

    def test_stale_lamp_and_missing_time_source_rejected(self):
        rows = [row(i, 299) for i in range(2)]
        lamps = [{'frame': i, 'time_s': i * .05, 'uppermost_distribution': False,
                  'low_beam_readback': True} for i in range(2)]
        lamps[1]['frame'] = 9
        with self.assertRaisesRegex(ValueError, 'frame join'):
            self.measure(rows, lamps)
        lamps[1]['frame'] = 1
        with self.assertRaisesRegex(ValueError, 'cited source'):
            self.measure(rows, lamps, {'lighting_time_applies': True})

    def test_no_beam_is_distinct_from_non_uppermost_beam(self):
        rows = [row(i, 299) for i in range(2)]
        lamps = [{'frame': i, 'time_s': i * .05,
                  'uppermost_distribution': False, 'low_beam_readback': False}
                 for i in range(2)]
        report = self.measure(rows, lamps)
        self.assertTrue(report['observations'][0]['no_beam_readback'])
        lamps[1].pop('low_beam_readback')
        with self.assertRaisesRegex(ValueError, 'Both high and low'):
            self.measure(rows, lamps)


if __name__ == '__main__':
    unittest.main()
