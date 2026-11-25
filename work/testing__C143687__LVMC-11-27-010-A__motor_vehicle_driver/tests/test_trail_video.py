import importlib.util
import unittest
from pathlib import Path

from test_trail import site_for, trail


MODULE = Path(__file__).resolve().parents[1] / 'trail_video.py'
spec = importlib.util.spec_from_file_location('trail_video', MODULE)
video = importlib.util.module_from_spec(spec)
spec.loader.exec_module(video)


class Image:
    def __init__(self, frame, width=2, height=2):
        self.frame, self.width, self.height = frame, width, height
        self.raw_data = b'\0' * (width * height * 4)


class TrailVideoTests(unittest.TestCase):
    def test_four_original_views_and_time_join(self):
        names = tuple(video.CAMERA_SPECS)
        self.assertEqual(names, ('overview', 'approach', 'reference_corner', 'driver_reference'))
        join = video.FourViewJoin({name: (2, 2) for name in names})
        sample = {'case_id': 'case', 'frame': 100, 'time_s': 5.0, 'vehicle_id': 42}
        images = {name: Image(100) for name in names}
        receipt = join.append(sample, images)
        self.assertEqual(set(receipt['cameras']), set(names))
        sample = dict(sample, frame=101, time_s=5.05)
        images = {name: Image(101) for name in names}
        join.append(sample, images)
        images = {name: Image(102) for name in names}
        images['overview'] = Image(101)
        with self.assertRaisesRegex(ValueError, 'overview original camera frame'):
            join.append(dict(sample, frame=102, time_s=5.10), images)
        with self.assertRaisesRegex(ValueError, 'frame/time discontinuity'):
            join.append(dict(sample, frame=104, time_s=5.15), images)

    def test_placements_target_trail_and_sign(self):
        site = site_for(trail.CASES[0])
        positions = video.placements(site)
        self.assertEqual(set(positions), set(video.CAMERA_SPECS))
        self.assertEqual(positions['overview']['target_xyz_m'], (10.0, 2.5, 1.0))
        self.assertNotEqual(positions['approach']['location_xyz_m'],
                            positions['reference_corner']['location_xyz_m'])


if __name__ == '__main__':
    unittest.main()
