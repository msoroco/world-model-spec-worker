import copy,json,pathlib,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from contracts import validate_output,measured_target,summarize,route_contained
from recording import Resources
class Contracts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.video_temp=tempfile.TemporaryDirectory();cls.video=pathlib.Path(cls.video_temp.name)/'fixture.webm'
  subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=16x16:r=20','-frames:v','2','-c:v','libvpx-vp9','-pix_fmt','yuv420p',str(cls.video)],check=True)
 @classmethod
 def tearDownClass(cls):cls.video_temp.cleanup()
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=pathlib.Path(self.temp.name);(self.root/'video.webm').write_bytes(self.video.read_bytes());self.desc={'channels':[{'name':'kin.speed','sampling_rate_hz':20}],'context_inputs':[{'name':'context'}]}
  self.trace=[dict(frame=i,time_s=i*.05,position={'x':i,'y':0,'z':0},heading_deg=0,speed_mps=1) for i in range(2)]
  self.put('trace.jsonl',self.trace);self.put('frames.jsonl',[dict(video_frame=i,carla_frame=i,time_s=i*.05) for i in range(2)]);self.put('speed.jsonl',[dict(time_s=i*.05,value=1) for i in range(2)]);(self.root/'context.json').write_text(json.dumps({'context':{'authored':True}}))
  self.put('participants.jsonl',[dict(time_s=i*.05,participants=[{'actor_id':1}]) for i in range(2)]);self.put('body.jsonl',[dict(time_s=i*.05,vertices=[[0,0],[1,0],[1,1],[0,1]]) for i in range(2)])
  self.result=dict(setup_confirmed=True,behavior_attempted=True,maneuver_completed=True,physical_failure_flags=[],video_references=['video.webm'],trace_reference='trace.jsonl',video_frame_map_reference='frames.jsonl',target_checks=[measured_target('speed',1,1,.1,'actual fixture speed','speed.jsonl')],recording_evidence=[dict(name='kin.speed',reference='speed.jsonl'),dict(name='context',reference='context.json')],required_participant_ids=[1],participant_history_reference='participants.jsonl',footprint_reference='body.jsonl',driving_polygons=[[[-1,-1],[2,-1],[2,2],[-1,2]]],realized_observables={'kin.speed':dict(value=1,statistic='mean',sample_window_s=[0,.05],reference='speed.jsonl')})
 def put(self,name,records):(self.root/name).write_text(''.join(json.dumps(r)+'\n' for r in records))
 def validate(self):return validate_output(self.root,self.result,self.desc)
 def test_success_real_encoded_fixture(self):self.assertTrue(self.validate())
 def test_target_mismatch(self):self.result['target_checks'][0]['matched']=False;self.assertRaises(ValueError,self.validate)
 def test_missing_physical_cause(self):self.result['target_checks'][0]['physical_cause_confirmed']=False;self.assertRaises(ValueError,self.validate)
 def test_null_channel(self):self.put('speed.jsonl',[dict(time_s=i*.05,value=None) for i in range(2)]);self.assertRaises(ValueError,self.validate)
 def test_png_directory(self):self.result['video_references']=['.'];self.assertRaises(ValueError,self.validate)
 def test_fake_encoded_file(self):(self.root/'video.webm').write_bytes(b'not encoded');self.assertRaises(ValueError,self.validate)
 def test_timestamp_mismatch(self):self.put('frames.jsonl',[dict(video_frame=i,carla_frame=i,time_s=i*.1) for i in range(2)]);self.assertRaises(ValueError,self.validate)
 def test_missing_participant(self):self.put('participants.jsonl',[dict(time_s=i*.05,participants=[]) for i in range(2)]);self.assertRaises(ValueError,self.validate)
 def test_departure(self):self.put('body.jsonl',[dict(time_s=i*.05,vertices=[[99,0]]) for i in range(2)]);self.assertRaises(ValueError,self.validate)
 def test_summary_uses_actual_window(self):self.result['realized_observables']['kin.speed']['value']=2;self.assertRaises(ValueError,self.validate)
 def test_missing_context(self):(self.root/'context.json').write_text('{}');self.assertRaises(ValueError,self.validate)
 def test_setup_not_confirmed(self):self.result['setup_confirmed']=False;self.assertRaises(ValueError,self.validate)
 def test_cleanup_independent_failure(self):
  seen=[];r=Resources();r.own(lambda:seen.append('settings'));r.own(lambda:(_ for _ in ()).throw(ValueError('capture')));r.own(lambda:seen.append('actors'));self.assertEqual(len(r.close()),1);self.assertEqual(seen,['actors','settings']);self.assertEqual(r.close(),[])
 def test_boundary_inside(self):self.assertTrue(route_contained([[0,0]],[[0,0],[2,0],[2,2],[0,2]]))
 def test_measured_targets_not_requested_values(self):self.assertFalse(measured_target('speed',5,3,.1,'observed','speed.jsonl')['matched'])
 def test_summary_no_samples(self):self.assertRaises(ValueError,summarize,[],0,1)

class OriginalPacketProjection(unittest.TestCase):
 def session(self,frame=4):
  import io
  from recording import Recording
  r=Recording.__new__(Recording);r.channels={'kin.speed':io.StringIO()};r.evidence_reader=io.StringIO(json.dumps({'original_frame':frame,'observed':7})+'\n');r.cameras=[];r.encoders=[];r.frame_map=io.StringIO();r.frames=0
  class Capture:
   def capture(self,frame,time_s,extra=None):return dict(frame=frame,time_s=time_s,speed_mps=3)
  r.capture=Capture();return r
 def test_callback_receives_original_packet(self):
  r=self.session();r.tick(4,.2,lambda row,event:{'kin.speed':row['speed_mps']+event['observed']});self.assertEqual(json.loads(r.channels['kin.speed'].getvalue())['value'],10);self.assertEqual(r.frames,1)
 def test_packet_frame_mismatch_fails(self):
  r=self.session(3);self.assertRaises(RuntimeError,r.tick,4,.2,{'kin.speed':3})
 def test_missing_projected_value_fails(self):
  r=self.session();self.assertRaises(ValueError,r.tick,4,.2,lambda row,event:{'kin.speed':None})

import importlib.util
spec=importlib.util.spec_from_file_location('owned_runner',pathlib.Path(__file__).resolve().parents[1]/'runner.py');runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class Geometry(unittest.TestCase):
 def test_all_configured_routes(self):runner.check()
 def test_curved_path_controller(self):
  c=runner.command((0,0),0,4,[[i,i*.2] for i in range(40)],5);self.assertGreater(c['steer'],0);self.assertGreater(c['throttle'],0)
 def test_actual_speed_not_setpoint(self):
  class V:x=3;y=4;z=0
  self.assertEqual(runner.speed(V()),5)
 def test_brake_overspeed(self):self.assertGreater(runner.command((0,0),0,10,[[i,0] for i in range(40)],3)['brake'],0)
 def test_authored_cross_surface(self):
  self.assertTrue(runner.footprint_inside([[-30,1],[1,4],[3,20]]));self.assertFalse(runner.footprint_inside([[30,30]]))
 def test_raw_observation_values(self):
  s=dict(actor_id=1,time_s=1,position_m=[1,2,0],heading_deg=0,speed_mps=4,body_vertices_m=[[0,1,0],[2,1,0]],native_lane={'road_id':1,'lane_id':-1},lamp_bits=0,blueprint='vehicle.tesla.model3')
  names=['kin.speed','kin.position','drv.turning','drv.yields_to','rel.surface_gap','st.centre_line','sig.turn_indicator','ru.trailer_or_combination'];o=runner.atom_measurements(names,s,[s],{},[])
  self.assertEqual(set(o),set(names));self.assertEqual(o['kin.speed'],4);self.assertIn('no qualitative predicate',o['drv.yields_to']['method']);self.assertTrue(all(v is not None for v in o.values()))
