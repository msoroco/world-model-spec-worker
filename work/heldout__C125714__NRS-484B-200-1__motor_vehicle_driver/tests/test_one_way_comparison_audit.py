import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from one_way_comparison_audit import audit


class OneWayComparisonTests(unittest.TestCase):
    def test_fixed_body_path_and_changed_lane_topology(self):
        with tempfile.TemporaryDirectory() as directory:
            left,one=Path(directory)/'left',Path(directory)/'one'
            for root,label,config in ((left,'left','left-probe-config.json'),
                                      (one,'one-way','one-way-probe-config.json')):
                root.mkdir()
                source=json.loads((ROOT/(label+'-diagnostic.json')).read_text())
                for name in ('video_frames.jsonl','trace.jsonl','directed_roadway_footprints.jsonl',
                             'one_way_roadway.jsonl','one_way_sign.jsonl'):
                    if name in source['files']:
                        (root/name).write_text(source['files'][name])
                (root/'config.json').write_text((ROOT/config).read_text())
            self.assertEqual(audit(left,one)['comparison_id'],'one-way')
            path=one/'one_way_roadway.jsonl'
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['ego_corners'][0][0]+=1
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'fixed original'):
                audit(left,one)


if __name__=='__main__':
    unittest.main()
