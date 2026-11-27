"""Complete same-lane following versus accidental overlap from source rows."""
import json
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'native'))
from measure_follow import measure

spec = importlib.util.spec_from_file_location('prove_measurement', ROOT / 'prove-measurement.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
make, rectangle = module.make, module.rectangle


class Following(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch, prefix='c146108-follow-')
        self.root = Path(self.temp.name) / 'source'
        make(self.root)
        self.path = self.root / 'participant-poses.jsonl'
        rows = [json.loads(line) for line in self.path.read_text().splitlines()]
        for i, row in enumerate(rows):
            row['rider_body_xy_m'] = rectangle(-80 + 3 * i / 20, -4.7, 1.2, .4)
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_following_keeps_body_gap(self):
        result = measure(self.root)
        self.assertEqual(result['longitudinal_overlap_frames'], 0)
        self.assertGreater(result['minimum_longitudinal_body_gap_m'], 0)
        self.assertFalse(result['legal_verdict_claimed'])

    def test_overlap_rejected(self):
        rows = [json.loads(line) for line in self.path.read_text().splitlines()]
        rows[300]['rider_body_xy_m'] = rectangle(-50 + 3 * 15, -4.7, 1.2, .4)
        self.path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'longitudinal overlap'):
            measure(self.root)

    def test_missing_pose_rejected(self):
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source'):
            measure(self.root)


if __name__ == '__main__':
    unittest.main()
