import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
CASE=ROOT.name+'__source_verified_base'
def body(x,y):return [[x-1,y-1],[x+1,y-1],[x+1,y+1],[x-1,y+1]]
class Tests(unittest.TestCase):
 def fixture(self,root):
  (root/'capture').mkdir()
  context={'native_map_id':'TownX','highway_id':1,'road_id':7,'following_lane_id':-1,'target_lane_id':-2,'hill_crest_source':'native-elevation-profile','lane_geometry_source':'native-waypoints','surface_source':'weather-and-road-review','traffic_source':'native-actor-inventory','route_source':'native-waypoints','following_forward_xy':[1,0]}
  (root/'road_context.json').write_text(json.dumps(context))
  config={'selected_case_id':CASE,'law_id':'NRS-484B-127-1','duration_s':45,'rate_hz':20,'requested_engineering_gap_m':6.0,'engineering_gap_tolerance_m':1.0,'recording_description':{'channels':[{'name':'kin.speed'},{'name':'kin.position'}]},'physical_completion':json.loads((ROOT/'config.json').read_text())['physical_completion']}
  (root/'config.json').write_text(json.dumps(config))
  history=[]
  for i,(x,y,change) in enumerate(((0,0,False),(2,0,False),(4,4,True))):
   history.append({'frame':100+i,'time_s':1+i*.05,'road_id':7,'ego':{'actor_id':11,'lane_id':-2 if change else -1,'body_vertices_xy_m':body(x,y),'velocity_mps':[5,0,0],'speed_source':'actor.get_velocity'},'lead':{'actor_id':22,'lane_id':-1,'body_vertices_xy_m':body(x+8,0),'velocity_mps':[4,0,0],'speed_source':'actor.get_velocity'},'surface_condition':'dry','traffic_actor_ids':[11,22],'lane_change_started':change})
  frames=[{'video_frame':i,'carla_frame':row['frame'],'time_s':row['time_s']} for i,row in enumerate(history)]
  for name,rows in [('vehicle_history.jsonl',history),('video_frames.jsonl',frames),('trace.jsonl',[{'frame':r['frame'],'time_s':r['time_s'],'position_m':[i*2,0,0],'velocity_mps':[5,0,0]} for i,r in enumerate(history)])]:
   (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
  (root/'capture/evidence.jsonl').write_text('{"frame":100}\n')
  for name in ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'):(root/name).write_bytes(b'textual placeholder')
 def run_finalizer(self,root):
  env=dict(os.environ);env['PYTHONPATH']=str(REPO/'runtime/scenario_pipeline')
  return subprocess.run([sys.executable,str(ROOT/'finalizer.py'),'--attempt',str(root),'--output',str(root/'analysis-report.json')],env=env,capture_output=True,text=True)
 def test_saved_only_finalizer_sources_and_no_legal_verdict(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);source_hash=hashlib.sha256((root/'vehicle_history.jsonl').read_bytes()).hexdigest()
   run=self.run_finalizer(root);self.assertEqual(run.returncode,0,run.stderr)
   result=json.loads((root/'result.json').read_text());report=json.loads((root/'analysis-report.json').read_text())
   self.assertEqual(result['measured_values']['minimum_sampled_body_gap_m'],6)
   self.assertTrue(result['measured_values']['following_end_before_lane_change'])
   self.assertEqual(report['measurements']['minimum_sampled_body_gap_m']['sources']['vehicle_history.jsonl'],source_hash)
   self.assertTrue(result['maneuver_completed']);self.assertEqual(result['physical_checks']['maneuver']['status'],'met');self.assertNotIn('legal_verdict',result)
   sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
   from worker_exchange.measurement_contract import validate,verify_report
   contract=json.loads((ROOT/'measurement-contract.json').read_text())
   plan=json.loads((ROOT/'case-plan.json').read_text())
   validate(contract,plan['requirement_dispositions'],(ROOT/'finalizer.py').read_text(),CASE)
   self.assertEqual(len(verify_report(contract,report,root)),3)
 def test_missing_raw_history_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root);(root/'vehicle_history.jsonl').unlink()
   run=self.run_finalizer(root);self.assertNotEqual(run.returncode,0)
   self.assertIn('Missing required source: vehicle_history.jsonl',run.stderr)
   self.assertFalse((root/'result.json').exists())
if __name__=='__main__':unittest.main()
