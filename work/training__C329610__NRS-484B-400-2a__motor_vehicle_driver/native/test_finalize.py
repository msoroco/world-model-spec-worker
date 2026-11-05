import json
from pathlib import Path
import tempfile
import unittest

from finalize import verify_original_joins


class SavedJoinTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);(self.root/'capture').mkdir()
        corners=[[-2,-1],[2,-1],[2,1],[-2,1]]
        body=[[x,y,z] for x,y in corners for z in (0,1.5)]
        streams={
          'trace.jsonl':[{'frame':100+i,'time_s':.05*(i+1)} for i in range(3)],
          'capture/evidence.jsonl':[{'original_frame':100+i,'recording_time_s':.05*(i+1),
              'ego':{'body_vertices_m':body}} for i in range(3)],
          'video_frames.jsonl':[{'video_frame':i,'native_frame':100+i,'time_s':.05*(i+1)} for i in range(3)],
          'native_samples.jsonl':[{'native_frame':100+i,'time_s':.05*(i+1),
              'native_body_xy_m':corners} for i in range(3)],
          'body_history.jsonl':[{'frame':100+i,'time_s':.05*(i+1),
              'body_vertices_m':body} for i in range(3)]}
        for name,data in streams.items():
            (self.root/name).write_text('\n'.join(json.dumps(r) for r in data)+'\n')
        (self.root/'capture/manifest.json').write_text(json.dumps({'extraction_confirmed':True,'frames':3}))

    def test_original_frame_body_and_time_joins(self):
        report=verify_original_joins(self.root,3)
        self.assertEqual((report['first_frame'],report['last_frame']),(100,102))
        self.assertEqual(set(report['source_hashes']),{'trace.jsonl','capture/evidence.jsonl',
            'video_frames.jsonl','native_samples.jsonl','body_history.jsonl','capture/manifest.json'})

    def test_frame_mismatch_rejected(self):
        path=self.root/'native_samples.jsonl'
        data=[json.loads(s) for s in path.read_text().splitlines()]
        data[1]['native_frame']=999
        path.write_text('\n'.join(json.dumps(r) for r in data)+'\n')
        with self.assertRaisesRegex(ValueError,'Original Native frame join differs'):
            verify_original_joins(self.root,3)

    def test_body_mismatch_rejected(self):
        path=self.root/'body_history.jsonl'
        data=[json.loads(s) for s in path.read_text().splitlines()]
        data[1]['body_vertices_m'][0][0]=50
        path.write_text('\n'.join(json.dumps(r) for r in data)+'\n')
        with self.assertRaisesRegex(ValueError,'Original full body differs'):
            verify_original_joins(self.root,3)

    def test_missing_original_capture_confirmation_rejected(self):
        (self.root/'capture/manifest.json').write_text(json.dumps({'extraction_confirmed':False,'frames':3}))
        with self.assertRaisesRegex(ValueError,'Original capture extraction incomplete'):
            verify_original_joins(self.root,3)


if __name__=='__main__':unittest.main()
