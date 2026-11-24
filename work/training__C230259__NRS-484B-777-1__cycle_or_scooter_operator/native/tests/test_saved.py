"""Exact draft saved-source tests; synthetic input cannot be original evidence."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from prove_right_edge import sample, hashes
from runner import check, process_saved


class SavedSourceTest(unittest.TestCase):
    def test_exact_config(self):
        self.assertTrue(check()['saved_source_path_checked'])

    def test_synthetic_rejected_as_original(self):
        with tempfile.TemporaryDirectory(dir=Path(__import__('os').environ['TMPDIR']).resolve()) as tmp:
            folder = Path(tmp) / 'reference'
            sample(folder, 'reference')
            with self.assertRaisesRegex(ValueError, 'source differs'):
                process_saved(folder, hashes(folder))


if __name__ == '__main__':
    unittest.main()

class NativeMapSurveyTest(unittest.TestCase):
    def test_original_map_readback(self):
        from capture import _survey
        from geometry import open_drive
        class Location:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z
        class Carla:
            class LaneType:
                Driving = 'driving'
        Carla.Location = Location
        class Map:
            def to_opendrive(self):
                return open_drive()
            def get_waypoint(self, location, project_to_road, lane_type):
                if not project_to_road or lane_type != 'driving':
                    raise AssertionError('Wrong Native lane query')
                class Waypoint:
                    road_id = 1
                    lane_id = -1
                    transform = type('T', (), {'location': type('P', (), {'y': -1.75})()})()
                return Waypoint()
        row = _survey(Map(), Carla)
        self.assertEqual(row['right_roadway_edge_y_m'], -3.5)
        self.assertEqual(len(row['native_waypoint_samples']), 4)

    def test_changed_native_width_rejected(self):
        from capture import _survey
        from geometry import open_drive
        class Map:
            def to_opendrive(self):
                return open_drive().replace('a="3.5"', 'a="4.0"', 1)
        with self.assertRaisesRegex(RuntimeError, 'width readback'):
            _survey(Map(), object())
