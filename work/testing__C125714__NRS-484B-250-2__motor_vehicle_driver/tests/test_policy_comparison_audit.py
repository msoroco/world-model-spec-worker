"""Source-bound controlled-policy comparison CPU fixtures."""
import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from policy_comparison_audit import audit


class ComparisonTests(unittest.TestCase):
    def test_pair_and_changed_original_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[]
            for label in ('yield_wait_for_other_clear','advance_at_release'):
                folder=Path(temp)/label;folder.mkdir()
                spec=json.loads((ROOT/'cases'/label/'diagnostic.json').read_text())
                for name in ('site-context.json','controller-history.jsonl',
                             'other-body-history.jsonl','video_frames.jsonl',
                             'original-bindings.json','acquisition-provenance.json'):
                    (folder/name).write_text(spec['files'][name])
                (folder/'road.xodr').write_bytes((ROOT/'candidate-map.xodr').read_bytes())
                paths.append(folder)
            result=audit(*paths)
            self.assertEqual(result['right_of_way_yielding'],'unresolved')
            self.assertTrue(result['diagnostic_fixture'])
            (paths[1]/'controller-history.jsonl').write_text('changed\n')
            with self.assertRaisesRegex(ValueError,'original missing or changed'):
                audit(*paths)

    def test_resealed_joint_frame_gap_still_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            paths=[]
            for label in ('yield_wait_for_other_clear','advance_at_release'):
                folder=Path(temp)/label;folder.mkdir()
                spec=json.loads((ROOT/'cases'/label/'diagnostic.json').read_text())
                for name in ('site-context.json','controller-history.jsonl',
                             'other-body-history.jsonl','video_frames.jsonl',
                             'original-bindings.json','acquisition-provenance.json'):
                    (folder/name).write_text(spec['files'][name])
                (folder/'road.xodr').write_bytes((ROOT/'candidate-map.xodr').read_bytes())
                paths.append(folder)
            changed=paths[1]
            manifest=json.loads((changed/'original-bindings.json').read_text())
            for name in ('controller-history.jsonl','other-body-history.jsonl',
                         'video_frames.jsonl'):
                rows=[json.loads(line) for line in (changed/name).read_text().splitlines()]
                # Preserve the cross-source join while skipping one Native tick.
                for row in rows[2:]:
                    row['time_s']+=.05
                    if 'frame' in row:row['frame']+=1
                    if 'carla_frame' in row:row['carla_frame']+=1
                    if 'native_frame' in row:row['native_frame']+=1
                (changed/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
                manifest[name]['sha256']=hashlib.sha256((changed/name).read_bytes()).hexdigest()
            (changed/'original-bindings.json').write_text(json.dumps(manifest)+'\n')
            with self.assertRaisesRegex(ValueError,'20 Hz cadence'):
                audit(*paths)


if __name__=='__main__':unittest.main()
