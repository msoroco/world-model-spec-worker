import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geometry import check, open_drive
from finalize import bounds
from runner import source_check, FRAMES, CAMERAS


class PrivateWayNativeTests(unittest.TestCase):
    def test_road_and_camera_contract(self):
        self.assertEqual(check()['road_ids'], [1, 2])
        self.assertIn('C177626-private-entry', open_drive())
        self.assertEqual(FRAMES, 600)
        self.assertEqual(len(CAMERAS), 4)

    def test_exact_materialized_case(self):
        config = source_check(Path(__file__).resolve().parents[1])
        self.assertTrue(config['case_id'].endswith(('__probe_a', '__probe_b')))

    def test_original_body_validation(self):
        self.assertEqual(bounds([[0, 0], [0, 1], [2, 0], [2, 1]]), (0, 2, 0, 1))
        with self.assertRaisesRegex(ValueError, 'body incomplete'):
            bounds([[0, 0]])


if __name__ == '__main__':
    unittest.main()
