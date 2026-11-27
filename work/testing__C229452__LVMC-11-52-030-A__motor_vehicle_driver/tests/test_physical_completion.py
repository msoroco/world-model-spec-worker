"""Physical source and lifecycle rejection tests."""

import importlib.util
from pathlib import Path
import unittest


path = Path(__file__).resolve().parents[1] / 'physical_completion.py'
spec = importlib.util.spec_from_file_location('physical_completion', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PhysicalCompletionTests(unittest.TestCase):
    def rows(self, speed=0):
        return [{'case_id': 'case', 'frame': i + 1, 'speed_mps': speed,
                 'inside_red_curb': True, 'trace_source_sha256': 'trace',
                 'curb_source_sha256': 'curb', 'camera_frame_map_sha256': 'map'}
                for i in range(120)]

    def test_three_measured_outcomes(self):
        self.assertEqual(module.evaluate(self.rows(), 'case')['physical_checks']['maneuver']['status'], 'met')
        self.assertEqual(module.evaluate(self.rows(2), 'case')['physical_checks']['maneuver']['status'], 'not_met')
        missing = self.rows()
        missing[-1].pop('curb_source_sha256')
        self.assertEqual(module.evaluate(missing, 'case')['physical_checks']['maneuver']['status'], 'unverified')

    def test_duplicate_frame_rejected(self):
        rows = self.rows()
        rows[-1]['frame'] = rows[-2]['frame']
        self.assertEqual(module.evaluate(rows, 'case')['physical_checks']['maneuver']['status'], 'unverified')

    def test_native_lifecycle_order(self):
        self.assertEqual(module.lifecycle(module.EVENTS)['exit_code'], 0)
        with self.assertRaisesRegex(ValueError, 'ownership closure'):
            module.lifecycle(('saved_processing_started',) + module.EVENTS[:-1])


if __name__ == '__main__':
    unittest.main()
