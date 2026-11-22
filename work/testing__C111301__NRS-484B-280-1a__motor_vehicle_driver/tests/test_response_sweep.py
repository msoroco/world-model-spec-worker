import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from response_sweep import sweep


class ResponseSweepTests(unittest.TestCase):
    def test_crossing_boundary_and_clear_path_at_two_speeds(self):
        result = sweep()
        self.assertEqual(len(result['records']), 12)
        self.assertEqual({row['brake'] for row in result['records']}, {0.0, 1.0})
        self.assertTrue(all(row['legal_due_care_verdict'] is None
                            for row in result['records']))

    def test_rejects_invalid_controller_boundary(self):
        from runner import load_scene
        scene = load_scene()
        scene['engineering_ttc_brake_s'] = 0
        with self.assertRaisesRegex(ValueError, 'engineering response'):
            sweep(scene)


if __name__ == '__main__':
    unittest.main()
