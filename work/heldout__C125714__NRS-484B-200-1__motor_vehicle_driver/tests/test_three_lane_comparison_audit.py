import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from three_lane_comparison_audit import audit


class ThreeLaneComparisonTests(unittest.TestCase):
    def test_fixed_body_path_and_added_lane(self):
        with tempfile.TemporaryDirectory() as directory:
            left,three=Path(directory)/'left',Path(directory)/'three'
            for root,label,config in ((left,'left','left-probe-config.json'),
                                      (three,'three-lane','three-lane-probe-config.json')):
                root.mkdir();source=json.loads((ROOT/(label+'-diagnostic.json')).read_text())
                for name in ('video_frames.jsonl','trace.jsonl','directed_roadway_footprints.jsonl',
                             'three_lane_roadway.jsonl'):
                    if name in source['files']:(root/name).write_text(source['files'][name])
                (root/'config.json').write_text((ROOT/config).read_text())
            self.assertEqual(audit(left,three)['comparison_id'],'three-lane')
            path=three/'three_lane_roadway.jsonl'
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['ego_corners'][0][0]+=1
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'fixed original'):
                audit(left,three)
            path.unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                audit(left,three)


if __name__=='__main__':
    unittest.main()
