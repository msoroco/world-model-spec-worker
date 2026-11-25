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

    def test_opposite_motion_and_full_right_footprint(self):
        rows = list(requested_rows('1.00'))
        self.assertEqual(len(rows), FRAMES)
        self.assertEqual(rows[0]['ego_center_xyz_m'][1], -1.0)
        self.assertEqual(rows[0]['requested_ego_right_half_body_fraction'], 1.0)
        self.assertEqual(rows[0]['oncoming_lane_id'], 1)

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
