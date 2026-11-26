import json
from pathlib import Path
import tempfile
import unittest

from check import check
from route import FRAMES, requested_rows


class MeetingRequestTests(unittest.TestCase):
    def test_exact_materialized_request(self):
        receipt = check(Path.cwd())
        self.assertEqual(receipt['frames'], 600)
        self.assertFalse(receipt['native_observed'])

    def test_fixed_opposing_track_and_lateral_contrast(self):
        right = list(requested_rows('witness_1'))
        left = list(requested_rows('witness_2'))
        self.assertEqual(len(right), FRAMES)
        self.assertEqual(len(left), FRAMES)
        self.assertEqual([r['oncoming_center_xyz_m'] for r in right],
                         [r['oncoming_center_xyz_m'] for r in left])
        self.assertEqual([r['ego_center_xyz_m'][0] for r in right],
                         [r['ego_center_xyz_m'][0] for r in left])
        self.assertNotEqual(right[240]['ego_center_xyz_m'][1],
                            left[240]['ego_center_xyz_m'][1])

    def test_missing_opposite_direction_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for file in ('road.xodr', 'config.json', 'request.jsonl'):
                (root / file).write_text((Path.cwd() / file).read_text())
            rows = [json.loads(s) for s in (root / 'request.jsonl').read_text().splitlines()]
            rows[240]['oncoming_heading_deg'] = 0
            (root / 'request.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'opposite-direction'):
                check(root)


if __name__ == '__main__':
    unittest.main()
