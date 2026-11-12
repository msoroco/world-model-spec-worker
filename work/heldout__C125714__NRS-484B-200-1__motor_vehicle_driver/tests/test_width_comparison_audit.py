import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from width_comparison_audit import audit


class WidthComparisonTests(unittest.TestCase):
    def test_fixed_path_and_narrower_width(self):
        with tempfile.TemporaryDirectory() as directory:
            left,narrow=Path(directory)/'left',Path(directory)/'narrow'
            for root,label,config in ((left,'left','left-probe-config.json'),
                                      (narrow,'narrow','narrow-probe-config.json')):
                root.mkdir()
                diagnostic=json.loads((ROOT/(label+'-diagnostic.json')).read_text())
                for name in ('video_frames.jsonl','trace.jsonl','directed_roadway_footprints.jsonl'):
                    (root/name).write_text(diagnostic['files'][name])
                (root/'config.json').write_text((ROOT/config).read_text())
            self.assertEqual(audit(left,narrow)['measured_roadway_width_m']['narrow'],4.4)
            path=narrow/'directed_roadway_footprints.jsonl'
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['ego_corners'][0][0]+=1
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'non-width original'):
                audit(left,narrow)


if __name__=='__main__':
    unittest.main()
