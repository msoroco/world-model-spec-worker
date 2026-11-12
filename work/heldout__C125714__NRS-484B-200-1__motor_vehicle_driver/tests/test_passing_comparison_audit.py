import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from passing_comparison_audit import audit


class PassingComparisonTests(unittest.TestCase):
    def test_source_comparison_and_fixed_width_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            left_root, passing_root = Path(directory)/'left', Path(directory)/'passing'
            for root, label, config in ((left_root, 'left', 'left-probe-config.json'),
                                        (passing_root, 'passing', 'passing-probe-config.json')):
                root.mkdir()
                diagnostic = json.loads((ROOT/(label+'-diagnostic.json')).read_text())
                for name in ('video_frames.jsonl','trace.jsonl',
                             'directed_roadway_footprints.jsonl','passing_actors.jsonl'):
                    if name in diagnostic['files']:
                        (root/name).write_text(diagnostic['files'][name])
                (root/'config.json').write_text((ROOT/config).read_text())
            self.assertEqual(audit(left_root, passing_root)['comparison_id'], 'passing')
            path = passing_root/'directed_roadway_footprints.jsonl'
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['subject_lane_width_m'] = 4.0
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'roadway condition differs'):
                audit(left_root, passing_root)


if __name__ == '__main__':
    unittest.main()
