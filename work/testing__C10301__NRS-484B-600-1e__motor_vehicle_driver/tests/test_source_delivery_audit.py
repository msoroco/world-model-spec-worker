import importlib.util,hashlib,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('source_delivery_audit',ROOT/'source_delivery_audit.py')
audit_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit_module)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
class Tests(unittest.TestCase):
 def fixture(self,root):
  case='testing__C10301__NRS-484B-600-1e__motor_vehicle_driver__source_verified_below_80'
  (root/'capture').mkdir();(root/'config.json').write_text(json.dumps({'selected_case_id':case}))
  motions=[];frames=[];traces=[]
  for i,speed in enumerate((1.,2.)):
   motions.append({'frame':100+i,'time_s':1+i*.05,'speed_source':'actor.get_velocity','velocity_mps':[speed,0,0],'speed_mps':speed})
   frames.append({'video_frame':i,'carla_frame':100+i,'time_s':1+i*.05});traces.append({'frame':100+i,'time_s':1+i*.05,'speed_mps':speed})
  for name,rows in [('subject_motion.jsonl',motions),('video_frames.jsonl',frames),('trace.jsonl',traces)]:
   (root/name).write_text(''.join(json.dumps(r)+'\n' for r in rows))
  (root/'road_context.json').write_text('{}');(root/'capture/evidence.jsonl').write_text('{}\n')
  for name in audit_module.CAMERAS:(root/name).write_bytes(b'camera')
  sources={name:sha(root/name) for name in ('subject_motion.jsonl','video_frames.jsonl','road_context.json')}
  result={'case_id':case,'video_references':list(audit_module.CAMERAS),'measured_values':{'sampled_peak_speed_mph':2/.44704},'recording_evidence':{'source_hashes':sources,'capture_evidence_sha256':sha(root/'capture/evidence.jsonl')}}
  (root/'result.json').write_text(json.dumps(result))
  return case
 def test_positive_and_missing_camera_rejection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);case=self.fixture(root)
   calls=[]
   def media(path,count,**kwargs):calls.append(path.name);return {'passed':True,'frames':count}
   r=audit_module.audit(root,case,media)
   self.assertEqual(r['source_frame_count'],2);self.assertEqual(calls,list(audit_module.CAMERAS));self.assertFalse(r['physical_acceptance_claimed'])
   (root/'driver_reference.mkv').unlink()
   with self.assertRaisesRegex(ValueError,'Missing original source'):audit_module.audit(root,case,media)
 def test_stale_frame_and_changed_velocity_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);case=self.fixture(root);frames=[json.loads(s) for s in (root/'video_frames.jsonl').read_text().splitlines()];frames[1]['carla_frame']=999;(root/'video_frames.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in frames))
   with self.assertRaisesRegex(ValueError,'frame join'):audit_module.audit(root,case,lambda *a,**k:{'passed':True})
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);case=self.fixture(root);motions=[json.loads(s) for s in (root/'subject_motion.jsonl').read_text().splitlines()];motions[1]['velocity_mps']=[3,0,0];(root/'subject_motion.jsonl').write_text(''.join(json.dumps(s)+'\n' for s in motions))
   with self.assertRaisesRegex(ValueError,'speed disagrees'):audit_module.audit(root,case,lambda *a,**k:{'passed':True})
if __name__=='__main__':unittest.main()
