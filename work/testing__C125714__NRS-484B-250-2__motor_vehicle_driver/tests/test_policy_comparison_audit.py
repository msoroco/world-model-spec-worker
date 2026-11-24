"""Source-bound controlled-policy comparison CPU fixtures."""
import json
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


if __name__=='__main__':unittest.main()
