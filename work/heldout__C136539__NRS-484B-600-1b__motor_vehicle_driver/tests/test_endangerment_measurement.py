import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULE = Path(__file__).resolve().parents[1] / 'endangerment_measurement.py'
SPEC = importlib.util.spec_from_file_location('endangerment_measurement', MODULE)
measurement = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(measurement)


def square(x):
    return [[x - .5, -.5], [x + .5, -.5], [x + .5, .5], [x - .5, .5]]


def sample(frame, other_x):
    return {'frame': frame, 'time_s': frame * .05, 'ego_id': 'ego-1',
            'exposed_id': 'walker-2', 'exposed_kind': 'pedestrian',
            'ego_corners_xy': square(0), 'exposed_corners_xy': square(other_x),
            'ego_velocity_xy_mps': [4, 0], 'exposed_velocity_xy_mps': [0, 0]}


class ExposureTests(unittest.TestCase):
    def measure(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'exposed_actor_footprints.jsonl'
            path.write_text(''.join(json.dumps(item) + '\n' for item in rows))
            return measurement.measure(path)

    def test_gap_closing_time_and_contact_are_observations(self):
        report = self.measure([sample(0, 3), sample(1, .5)])
        self.assertAlmostEqual(report['observations'][0]['surface_gap_m'], 2)
        self.assertAlmostEqual(report['observations'][0]['radial_gap_closing_time_s'], .5)
        self.assertTrue(report['any_contact'])
        self.assertIsNone(report['endangerment_legal_judgment'])

    def test_receding_exposure_has_no_closing_time(self):
        first, second = sample(0, 3), sample(1, 3)
        for item in (first, second):
            item['ego_velocity_xy_mps'] = [-4, 0]
        report = self.measure([first, second])
        self.assertIsNone(report['observations'][0]['radial_gap_closing_time_s'])

    def test_stale_subject_and_frame_rejected(self):
        wrong = sample(1, 3)
        wrong['exposed_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            self.measure([sample(0, 3), wrong])
        wrong['exposed_id'] = 'walker-2'
        wrong['time_s'] = .1
        with self.assertRaisesRegex(ValueError, '20 Hz'):
            self.measure([sample(0, 3), wrong])

    def test_degenerate_body_rejected(self):
        wrong = sample(1, 3)
        wrong['exposed_corners_xy'] = [[0, 0]] * 4
        with self.assertRaisesRegex(ValueError, 'Degenerate'):
            self.measure([sample(0, 3), wrong])

    def test_nonfinite_original_rejected(self):
        wrong = sample(1, 3)
        wrong['ego_velocity_xy_mps'] = [float('nan'), 0]
        with self.assertRaisesRegex(ValueError, 'Nonfinite original'):
            self.measure([sample(0, 3), wrong])
        wrong = sample(1, 3)
        wrong['time_s'] = float('inf')
        with self.assertRaisesRegex(ValueError, 'frame/time identity'):
            self.measure([sample(0, 3), wrong])


if __name__ == '__main__':
    unittest.main()
