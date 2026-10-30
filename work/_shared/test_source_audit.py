import json,tempfile,unittest
from pathlib import Path
from source_audit import audit,sha,NAMES
class SourceTests(unittest.TestCase):
 def fixture(self,root):
  (root/'config.json').write_text(json.dumps({'selected_case_id':'case','duration_s':.1,'rate_hz':20}))
  rows=[{'video_frame':i,'carla_frame':10+i,'time_s':i*.05} for i in range(2)]
  (root/'video_frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
  for name in (*NAMES,'raw'):(root/(name+'.mkv')).write_bytes(b'diagnostic hash test only')
  receipt={'format':'synchronized-four-view-v1','frames':2,'frame_map_sha256':sha(root/'video_frames.jsonl'),'primary_sha256':sha(root/'raw.mkv'),'sources':{n:sha(root/(n+'.mkv')) for n in NAMES}}
  (root/'four-view-receipt.json').write_text(json.dumps(receipt));(root/'motion.jsonl').write_text(''.join(json.dumps({'frame':10+i,'time_s':i*.05})+'\n' for i in range(2)))
  return {'case_id':'case','frame_sources':[{'path':'motion.jsonl','frame_key':'frame','time_key':'time_s','full_recording':True}],'pixel_review_obligations':['Independently inspect original participant pixels']}
 def test_join(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=self.fixture(r);self.assertTrue(audit(r,s)['passed']);self.assertFalse(audit(r,s)['pixel_visibility_verified'])
 def test_camera_mutation(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=self.fixture(r);(r/'overview.mkv').write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'camera source changed'):audit(r,s)
 def test_missing_tick(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=self.fixture(r);(r/'motion.jsonl').write_text(json.dumps({'frame':10,'time_s':0})+'\n')
   with self.assertRaisesRegex(ValueError,'lost original ticks'):audit(r,s)
 def test_outside_original_frame(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=self.fixture(r);(r/'motion.jsonl').write_text(json.dumps({'frame':999,'time_s':0})+'\n')
   with self.assertRaisesRegex(ValueError,'outside original recording'):audit(r,s)
 def test_short_capture(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);s=self.fixture(r);c=json.loads((r/'config.json').read_text());c['duration_s']=45;(r/'config.json').write_text(json.dumps(c))
   with self.assertRaisesRegex(ValueError,'Full planned duration'):audit(r,s)
 def test_both_observers_on_every_original_tick(self):
  from source_audit import join_sources
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);self.fixture(r);mapping=[json.loads(s) for s in (r/'video_frames.jsonl').read_text().splitlines()]
   rows=[{'frame':f,'approach':side} for f in (10,11) for side in ('ahead','behind')]
   path=r/'rays.jsonl';path.write_text(''.join(json.dumps(x)+'\n' for x in rows))
   spec={'path':'rays.jsonl','frame_key':'frame','full_frame_coverage':True,'frame_group_key':'approach','required_groups':['ahead','behind']}
   self.assertEqual(join_sources(r,[spec],mapping)[0]['rows'],4)
   path.write_text(''.join(json.dumps(x)+'\n' for x in rows[:-1]))
   with self.assertRaisesRegex(ValueError,'observer direction coverage incomplete'):join_sources(r,[spec],mapping)
if __name__=='__main__':unittest.main()
