"""Exact materialized bundle static checks; no CARLA connection."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from runner import check


class ExactSignalBundle(unittest.TestCase):
    def test_case_road_camera_and_duration(self):
        result = check(Path.cwd())
        self.assertEqual((result['frames'], result['rate_hz']), (600, 20))
        self.assertFalse(result['native_executed'])
        self.assertFalse(result['area_class_originally_verified'])
        self.assertIsNone(result['legal_verdict'])

    def test_reject_changed_selected_request(self):
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as temp:
            bundle = Path(temp)
            for name in ('config.json', 'road.xodr', 'assignment-source.json'):
                shutil.copyfile(name, bundle / name)
            config = json.loads((bundle / 'config.json').read_text())
            config['signal_onset_odometer_m'] += 1
            (bundle / 'config.json').write_text(json.dumps(config) + '\n')
            with self.assertRaisesRegex(ValueError, 'signal and lane-change request'):
                check(bundle)


if __name__ == '__main__':
    unittest.main()
