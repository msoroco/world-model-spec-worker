import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from three_lane_allocation_finalizer import measure_allocation_sources
from three_lane_runner_allocation import check_config

HERE=Path(__file__).resolve().parents[1]


class AllocationTests(unittest.TestCase):
    def materialize(self,root,posted):
        slug='center-allocated-posted' if posted else 'center-allocated-unposted'
        data=json.loads((HERE/(slug+'-diagnostic.json')).read_text())
        for name,content in data['files'].items():
            path=root/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content)
        config=json.loads(json.loads((HERE/('construction-'+slug+'.json')).read_text())['files'][1]['content'])
        (root/'config.json').write_text(json.dumps(config))
        return root

    def test_both_candidate_sources_measure_without_legal_judgment(self):
        for posted in (True,False):
            with TemporaryDirectory() as temporary:
                root=self.materialize(Path(temporary),posted)
                value=measure_allocation_sources(root)
                self.assertEqual(value['posted_sign_candidate'],posted)
                self.assertIsNone(value['legal_allocation_verified'])
                check_config(json.loads((root/'config.json').read_text()))

    def test_invalid_sign_blueprint_rank_rejected(self):
        config=json.loads(json.loads((HERE/'construction-center-allocated-posted.json').read_text())['files'][1]['content'])
        config['sign_blueprint_rank']=3
        with self.assertRaisesRegex(ValueError,'rank invalid'):
            check_config(config)

    def test_missing_and_forged_sign_geometry_rejected(self):
        with TemporaryDirectory() as temporary:
            root=self.materialize(Path(temporary),True)
            (root/'allocation_frames.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing required source'):
                measure_allocation_sources(root)
        with TemporaryDirectory() as temporary:
            root=self.materialize(Path(temporary),True)
            path=root/'allocation_frames.jsonl'
            rows=[json.loads(line) for line in path.read_text().splitlines()]
            rows[0]['sign_body_vertices_xyz']=[]
            path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'candidate sign differs'):
                measure_allocation_sources(root)


if __name__=='__main__':unittest.main()
