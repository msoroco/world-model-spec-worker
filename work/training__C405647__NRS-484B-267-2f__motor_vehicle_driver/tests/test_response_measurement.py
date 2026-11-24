"""Source-shaped CPU checks for the referred subsection 1 response."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from measure_approach import measure

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


class ResponseMeasurementTests(unittest.TestCase):
    def test_both_exact_case_responses(self):
        first = measure(HERE / 'current-fixture/controlled_1')
        second = measure(HERE / 'current-fixture/controlled_2')
        self.assertTrue(first['right_edge_stop_until_passed_observed'])
        self.assertEqual(first['ego_speed_after_mps'], 0)
        self.assertGreater(first['emergency_pass_frame'], 220)
        self.assertFalse(second['right_edge_stop_until_passed_observed'])
        self.assertEqual(second['ego_speed_after_mps'], 3)

    def test_rejects_missing_right_edge_and_early_restart(self):
        source = HERE / 'current-fixture/controlled_1'
        scratch = ROOT / '.runtime-work/c405647-267-2f/tmp'
        with tempfile.TemporaryDirectory(dir=scratch) as temp:
            target = Path(temp)
            for name in ('video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json'):
                shutil.copyfile(source / name, target / name)
            rows = [json.loads(line) for line in (target / 'vehicle_poses.jsonl').read_text().splitlines()]
            rows[160]['ego']['y_m'] = -1.75
            (target / 'vehicle_poses.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'Right-edge position'):
                measure(target)
            rows[160]['ego']['y_m'] = -2.5
            rows[220]['ego']['speed_mps'] = 1.0
            (target / 'vehicle_poses.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'stop-until-passed'):
                measure(target)


if __name__ == '__main__':
    unittest.main()
