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

    def test_opposite_motion_and_fraction_contrast(self):
        low = list(requested_rows('0.45'))
        high = list(requested_rows('0.55'))
        self.assertEqual(len(low), FRAMES)
        self.assertEqual(len(high), FRAMES)
        self.assertEqual([r['oncoming_center_xyz_m'] for r in low],
                         [r['oncoming_center_xyz_m'] for r in high])
        self.assertEqual(low[0]['ego_center_xyz_m'][0], high[0]['ego_center_xyz_m'][0])
        self.assertNotEqual(low[0]['ego_center_xyz_m'][1], high[0]['ego_center_xyz_m'][1])
        self.assertEqual(low[0]['ego_lane_id'], -1)
        self.assertEqual(low[0]['oncoming_lane_id'], 1)

    def test_changed_heading_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            for file in ('road.xodr', 'config.json', 'request.jsonl'):
                (root/file).write_text((Path.cwd()/file).read_text())
            rows = [json.loads(s) for s in (root/'request.jsonl').read_text().splitlines()]
            rows[240]['oncoming_heading_deg'] = 0
            (root/'request.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError, 'opposite-direction'):
                check(root)


if __name__ == '__main__': unittest.main()
