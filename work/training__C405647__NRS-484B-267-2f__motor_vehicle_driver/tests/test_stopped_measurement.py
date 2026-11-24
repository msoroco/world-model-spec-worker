"""Test the stopped referral without guessing NRS 484B.607's duties."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'native'))
from measure_stopped import measure


class StoppedMeasurement(unittest.TestCase):
    def test_source_bound_stop_and_referral(self):
        result = measure(HERE / 'current-fixture/stopped_referral')
        self.assertEqual(result['samples'], 600)
        self.assertTrue(result['stopped_referral_observed'])
        self.assertIsNone(result['emergency_pass_frame'])
        self.assertFalse(result['nrs_484b_607_duty_resolved'])
        self.assertIsNone(result['legal_result'])

    def test_continued_vehicle_motion_is_rejected(self):
        source = HERE / 'current-fixture/stopped_referral'
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work/c405647-267-2f/tmp') as temporary:
            target = Path(temporary)
            for name in ('video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json'):
                (target / name).write_bytes((source / name).read_bytes())
            rows = [json.loads(line) for line in (target / 'vehicle_poses.jsonl').read_text().splitlines()]
            for row in rows[220:300]:
                row['emergency']['speed_mps'] = 2
            (target / 'vehicle_poses.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'Stopped-vehicle referral'):
                measure(target)


if __name__ == '__main__':
    unittest.main()
